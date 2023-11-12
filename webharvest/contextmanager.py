"""Driver context manager for the web scrapper.

This module contains the driver context manager for the web scrapper. It is the base class for the driver context manager. It populates the producer queue with the input data and handles the data collected by the consumer threads and processes it
"""
import abc
import logging
import functools
import threading
from typing import List

from webharvest.schemas import ContextStatusSchema

class DriverContextManager(abc.ABC):
    """Base class for the driver context manager.

    This class is the base class for the driver context manager. It populates the producer queue with the input data and handles the data collected by the consumer threads and processes it.
    It is an abstract class, so it must be inherited and the methods implemented."""

    def __init__(self, process_id: str = 'webharvest'):
        """Initialize data processor."""

        # Process ID
        self.process_id = process_id
        """Process ID."""

        # status contexts
        self.status_contexts: List[ContextStatusSchema] = list()
        """List of status contexts."""

        self.lock = threading.Lock()
        """Lock for the status contexts list."""

    @functools.cached_property
    def logger(self) -> logging.Logger:
        """Logger."""
        return logging.getLogger(f'{self.process_id}.driver_context_manager')

    @abc.abstractmethod
    def generate_scraping_contexts(self, *args, **kwargs) -> List[ContextStatusSchema]:
        """Create input data for the producer queue.

        Returns:
            List[ContextStatusSchema]: List of initial contexts.
        """
        raise NotImplementedError(
            "generate_scraping_contexts method not implemented")

    @abc.abstractmethod
    def add_context_status(self, context_status: ContextStatusSchema) -> None:
        """Add context status to the status contexts list. Use the lock if necessary.

        Args:
            context_status (ContextStatusSchema): Context status to be added.
        """
        raise NotImplementedError("add_context_status method not implemented")

    @abc.abstractmethod
    def create_process_report(self) -> None:
        """Create process report.

        This method creates the process report.
        """
        raise NotImplementedError(
            "create_process_report method not implemented")

    def stop_handler(self) -> None:
        """Stop signal handler."""
        self.logger.warning(
            f'Stop signal received, but stop_handler method not implemented')
        pass

    def stop_processing(self) -> None:
        """Stop processing.

        This method stops the processing. It is called when the consumer threads finish.
        """
        pass
