""" Module containing base Webscrapper class """
import os
import sys
import abc
import types
import queue
import signal
import logging
import functools
from datetime import datetime
from typing import List, Dict, Type, Optional

from concurrent.futures import ThreadPoolExecutor, as_completed, Future, CancelledError

# Schemas
from webharvest.schemas import WebscrapperOptionsSchema, DriverOptionsSchema, ContextStatusSchema, ContextStatusEnum

# Base classes
from webharvest.driver import DriverContext, DriverState
from webharvest.contextmanager import DriverContextManager
from webharvest.exceptions import WebScrapperException, InvalidWebdriverException

class Webscrapper(abc.ABC):
    """ Abstract class to be inherited by all Selenium based webscrappers. 
    
    This class is the base class for all Selenium based webscrappers. It handles the driver pool and the webscrapping process.
    """

    def __init__(self,
                 driver_context_manager: DriverContextManager,
                 webscrapper_options: WebscrapperOptionsSchema = WebscrapperOptionsSchema(),
                 driver_options: DriverOptionsSchema = DriverOptionsSchema(),
                 process_id: str = 'webharvest',
                 ) -> None:
        """Initialize webscrapper."""
        
        # Process ID
        self.PID = os.getpid()
        self.process_id = process_id
        self.logger.info(f'Initializing webscrapper with PID: {self.PID}')

        # Data processor
        self.driver_context_manager = driver_context_manager

        # Webscrapper options
        self.webscrapper_options = webscrapper_options

        # Driver save driver options
        self.driver_options = driver_options

        # Driver queue
        self._driver_queue:queue.Queue[DriverContext] = queue.Queue(maxsize=self.webscrapper_options.threads_num)
    
        # Stop signal handler
        signal.signal(signal.SIGINT, self.stop_signal_handler)

    @property
    @abc.abstractmethod
    def initial_state(self) -> Type[DriverState]:
        """Initial state. This property stores the initial state of the driver context."""
        raise NotImplementedError('Initial state must be implemented in the child class')

    @property
    def driver_queue(self) -> queue.Queue[DriverContext]:
        """Driver queue. This property stores the driver queue."""
        return self._driver_queue
    
    @functools.cached_property
    def logger(self) -> logging.Logger:
        """Logger. This property stores the logger."""
        return logging.getLogger(f'{self.process_id}.webscrapper')
    
    # Driver Context Methods
    # ----------------------

    def initialize_driver_pool(self) -> None:
        """Initialize driver pool. This method creates the driver managers and adds them to the driver pool."""

        with ThreadPoolExecutor(max_workers=self.webscrapper_options.threads_num) as executor:
            futures = [executor.submit(self.generate_driver_context) for _ in range(self.webscrapper_options.threads_num)]

        for future in as_completed(futures):
            self.setup_driver_context(future)
        
    def setup_driver_context(self, future: Future) -> None:
        """Setup driver context. This method prepares the driver context for the webscrapping process and adds it to the driver pool"""
        try:
            driver_context:DriverContext = future.result()
            self.driver_queue.put(driver_context) 

        except InvalidWebdriverException as e:
            self.logger.error(e)

        except Exception as e:
            self.logger.error(f'Error initializing driver context: {future.exception()}', exc_info=True)

    def generate_driver_context(self) -> DriverContext:
        """ Producer method to generate driver managers and add them to the driver pool."""

        # Create driver manager and retry if it fails
        driver_context:DriverContext = self._generate_driver_context()

        # Set initial state
        driver_context.set_state(self.initial_state) 

        return driver_context 
    
    def _generate_driver_context(self) -> DriverContext:
        """ Generate driver context. This method creates the driver manager. """

        # Get driver manager class
        driver_context_cls = DriverContext.get_driver_context_cls(self.driver_options.driver_type)

        # Create driver manager
        return driver_context_cls(driver_options=self.driver_options, process_id=self.process_id)

    # Webscrapper Methods
    # -------------------

    def start_scraping(self) -> None:
        """This method starts the scraping process.
            1. Creates the initial context statuses for webscrapping runs.
            2. Create driver pool.
            3. Submits the tasks to the executor
            4. Processes the results.
            5. Clears the driver pool and flushes pending data.
            6. Creates a report when all futures are completed.
        """

        # 1. Create scraping contexts - create blank context statuses
        self.scraping_contexts:List[ContextStatusSchema] = self.generate_scraping_contexts()

        # 2. Create driver pool
        self.initialize_driver_pool()

        # 3. Submit tasks - create futures and save them in a dictionary
        self.create_and_submit_tasks()

        # 4. Process tasks results
        self.process_completed_tasks()

        # 5. Clean driver pool and flush pending data
        self.clear_driver_queue()
        self.driver_context_manager.stop_processing()

        # 6. Create report when all futures are completed
        return self.driver_context_manager.create_process_report()

    def generate_scraping_contexts(self, *args, **kwargs) -> List[ContextStatusSchema]:
        """Wrapper method to create blank context statuses. This method creates the initial context statuses for webscrapping runs."""
        try:
            self.driver_context_manager.logger.info(f'Generating blank context statuses using {self.driver_context_manager.__class__.__name__}')
            return self.driver_context_manager.generate_scraping_contexts(*args, **kwargs)
        
        except Exception as e:
            self.logger.error(f'Error generating blank context statuses: {str(e)}', exc_info=True)
            raise e
        
    def create_and_submit_tasks(self) -> None:
        """Create and submit tasks. This method creates and submits the tasks to the executor."""

        with ThreadPoolExecutor(max_workers=self.webscrapper_options.threads_num) as self.executor:
            self.futures:Dict[Future, ContextStatusSchema] = {
                self.executor.submit(self.scrape_item, input_item): input_item 
                for input_item in self.scraping_contexts
            }
        
    def process_completed_tasks(self) -> None:
        """Process completed tasks."""

        for future in as_completed(self.futures.keys()):
            context_status:ContextStatusSchema = self.process_completed_future(future)
            self.driver_context_manager.add_context_status(context_status)
        
        self.logger.info(f'Executed {len(self.futures)} webscrapping runs.')

    def process_completed_future(self, future: Future) -> ContextStatusSchema:
        """Get future results. This method evaluates the future result and update the context status."""

        try:

            context_status:ContextStatusSchema = future.result()

            # Expected error - set status to failed but continue scraping
            if isinstance(context_status.error, WebScrapperException):  
                context_status.status = ContextStatusEnum.FAILED

            # Unexpected error - set status to critical to stop scraping
            elif isinstance(context_status.error, Exception):
                context_status.status = ContextStatusEnum.CRITICAL
                self.cancel_futures()
            
            return context_status
        
        except CancelledError:
            self.futures[future].status = ContextStatusEnum.CANCELLED
            return self.futures[future]
        

    def scrape_item(self, blank_context_status: ContextStatusSchema) -> ContextStatusSchema:
        """Execute run for the given ticket. This method executes the run method of the driver context."""

        # 1. Get & lock available driver
        driver_context: DriverContext = self.driver_queue.get(block=True, timeout=60)

        # 2. Initialize driver context status
        driver_context.status = blank_context_status

        # 3. Run webscrapping process until it finishes or an exception is raised
        try:
            while not driver_context.has_finished():
                driver_context.run()

        # 3.1. Handle exceptions
        except WebScrapperException as e:
            driver_context.status.error = e
            self.logger.error(f'[{driver_context.status.current_state}] {e}')

        except Exception as e:
            driver_context.status.error = e
            self.logger.error(f'[{driver_context.status.current_state}] {e}', exc_info=True)
            self._take_screenshot(driver_context)
        
        # 3.2. Always release driver
        finally:
            self.driver_queue.put(driver_context)
            self.driver_queue.task_done()
                       
        return driver_context.status
    
    # Helper Methods
    # --------------

    def _take_screenshot(self, driver_context: DriverContext) -> None:
        """Take screenshot if driver is available. This method takes a screenshot if the driver is available."""
        try:
            current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            driver_context.take_screenshot(f'{driver_context.status.current_state}_error-{current_time}.png')
        except Exception as e:
            self.logger.warning('Could not take screenshot', exc_info=True)
            
    def cancel_futures(self) -> None:
        """Cancel futures. This method cancels all pending futures."""
        for future in self.futures.keys():
            future.cancel()

    def clear_driver_queue(self) -> None:
        """Clear driver queue."""

        self.logger.info('Initializing driver queue clearance...')
        num_drivers = self.webscrapper_options.threads_num

        for idx in range(num_drivers):
            try:
                self._clear_driver_context(idx)
            except queue.Empty:
                self.logger.warning(f'Driver queue could not be cleared. {num_drivers - idx} drivers remaining.')
                break
    
    def _clear_driver_context(self, driver_index:int) -> None:
        """Clear driver context."""
        driver_context = self.driver_queue.get(timeout=1000)
        driver_context.clear_context()
        self.driver_queue.task_done()
        self.logger.info(f'Driver {driver_index} cleared.')

    def stop_signal_handler(self, signum:int, frame:Optional[types.FrameType]) -> None:
        """Stop signal handler."""
        self.logger.warning('SIGINT received, indicating threads to stop...')
        self.cancel_futures()
        self.clear_driver_queue()
        self.driver_context_manager.stop_handler()
        sys.exit(0)
