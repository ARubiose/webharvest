""" Module to deal with captchas and other annoying things """
import os
import abc
import random
import logging
import threading
from datetime import datetime
from functools import cached_property
from typing import List, Tuple, Optional, Type, Dict, Callable, Generic

import tenacity as tc
from webdriver_manager.core.manager import DriverManager

# Selenium imports
from selenium import webdriver
from selenium.common.exceptions import (
    WebDriverException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.remote.webelement import WebElement as SeleniumWebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By

# Chrome driver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options as ChromeOptions

# Firefox driver
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.options import Options as FirefoxOptions

# Own imports
# from webharvest.captcha import CaptchaSolver  # Disabled for now
from webharvest import config
from webharvest.schemas import (
    DriverOptionsSchema,
    DriverTypeEnum,
    ContextStatusSchema,
    ContextStatusEnum,
    TableDataSchema,
    WebElementLocator,
    AnyWebDriver,
    OutputDataT,
    InputDataT,
    TableHeader,
    TableBody,
)


class DriverState(abc.ABC, Generic[InputDataT, OutputDataT]):
    """Driver state base class. It represents a small sequence of web interactions."""

    def __init__(self, driver_context: "DriverContext") -> None:
        self.driver_context: DriverContext = driver_context

    @cached_property
    def logger(self) -> logging.Logger:
        """Return the logger"""
        return self.driver_context.logger

    @property
    def driver(self) -> AnyWebDriver:
        """Return the driver"""
        return self.driver_context.driver
    
    @property
    def status(self) -> ContextStatusSchema[InputDataT, OutputDataT]:
        """Return the context status"""
        return self.driver_context.status
    
    @property
    def input(self) -> InputDataT:
        """Return the input data of the context run"""
        return self.status.input_data

    @property
    def output(self) -> OutputDataT:
        """Return the output data of the context run"""
        return self.status.output_data

    @abc.abstractmethod
    def run(self) -> None:
        """Run the driver state. This method should be implemented by each driver state."""
        raise NotImplementedError("run method not implemented")

    def retry(self, function, retry_args, **kwargs) -> None:
        return tc.retry(
            before=tc.before_log(self.driver_context.logger, logging.DEBUG),
            **retry_args,
        )(function)(**kwargs)

    def set_run_status(self, status: ContextStatusEnum) -> None:
        """Set the run status of the context"""
        self.status.status = status


class DriverContext(abc.ABC):
    """Class used as context for Selenium webdrivers.

    This class is used to create a webdriver instance and to interact with it.
    """

    RANDOM_VIEWPORTS: List[Tuple[int, int]] = [
        (1920, 1080),
        (1366, 768),
        (1280, 720),
        (1024, 768),
        (800, 600),
    ]
    """List of random viewports to be used by the driver."""

    RANDOM_AGENTS: List[str]
    """List of random user agents to be used by the driver."""

    def __init__(
        self, driver_options: DriverOptionsSchema, process_id: str = "webharvest"
    ) -> None:
        """Initialize randomizer with its custom attributes"""

        # Process ID
        self.process_id = process_id

        # Save driver options
        self.driver_options:DriverOptionsSchema = driver_options
        
        # Initialize webdriver
        self.initialize_driver()

    @cached_property
    def logger(self) -> logging.Logger:
        """Return the logger"""
        return logging.getLogger(
            f"{self.process_id}.driver-{threading.get_native_id()}"
        )

    @property
    def driver(self) -> AnyWebDriver:
        """Return the driver"""
        if hasattr(self, "_driver"):
            return self._driver
        raise AttributeError("Driver not initialized")

    @driver.setter
    def driver(self, driver: AnyWebDriver) -> None:
        """Set the driver"""
        self._driver = driver

    @property
    def status(self) -> ContextStatusSchema:
        """Return the context status"""
        return self.context_status

    @status.setter
    def status(self, status: ContextStatusSchema) -> None:
        """Set the context status"""
        self.context_status = status

    @property
    def manager(self) -> DriverManager:
        """Return the driver manager"""
        return getattr(self, "_manager", self.create_driver_manager())

    @manager.setter
    def manager(self, manager: DriverManager) -> None:
        """Set the driver manager"""
        self._manager = manager

    def set_state(self, state_cls: Type[DriverState]) -> None:
        """Set the driver state"""
        if not issubclass(state_cls, DriverState):
            raise TypeError(f"state must be a subclass of DriverState.")
        self.state = state_cls(driver_context=self)

    @staticmethod
    def get_driver_context_cls(driver_type: DriverTypeEnum) -> Type["DriverContext"]:
        """Get driver manager class from driver type"""

        if driver_type == DriverTypeEnum.CHROME:
            return ChromeDriverContext

        if driver_type == DriverTypeEnum.FIREFOX:
            return FirefoxDriverContext

        raise ValueError(
            f"Invalid driver type {driver_type}. Currently supported drivers are: {DriverTypeEnum.__members__.values()}"
        )

    def clear_context(self) -> None:
        """Quit driver"""
        self.quit()

    @abc.abstractmethod
    def create_webdriver(self) -> AnyWebDriver:
        """Generate a driver"""
        raise NotImplementedError("create_webdriver() method must be implemented")

    @abc.abstractmethod
    def create_driver_manager(self) -> DriverManager:
        """Create the driver manager"""
        raise NotImplementedError("create_driver_manager() method must be implemented")

    def initialize_driver(self):
        """Re/Initialize the driver"""
        self.logger.info(
            f"Initializing driver context with PID: {threading.get_native_id()}"
        )
        self.driver = self.create_webdriver()
        self.logger.info(
            f"Driver context initialized with PID: {threading.get_native_id()}"
        )

    def has_finished(self) -> bool:
        """Check if the driver run has finished"""
        return self.status.status in [
            ContextStatusEnum.SUCCEED,
            ContextStatusEnum.FAILED,
            ContextStatusEnum.CRITICAL,
            ContextStatusEnum.CANCELLED,
        ]

    def run(self) -> None:
        """Run/Execute interactions using the current driver state"""
        self.status.current_state = self.state.__class__.__name__
        self.state.run()

    def randomize(self):
        """Randomize user agent and viewport size of the driver"""
        self.change_user_agent()
        self.change_viewport_size()

    def change_user_agent(self):
        """Change user agent of the driver"""
        user_agent = random.choice(self.RANDOM_AGENTS)
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'userAgent', {get: function(){return '"
            + user_agent
            + "';}});"
        )

    def change_viewport_size(self):
        """Change viewport size of the driver"""
        width, height = random.choice(self.RANDOM_VIEWPORTS)
        self.driver.set_window_size(width, height)

    def quit(self):
        """Close/quit the driver"""
        self.driver.quit()

    # Web driver actions
    # ******************
    def refresh(self):
        """Refresh the driver"""
        self.driver.refresh()

    def take_screenshot(
        self, filename: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.png")
    ) -> bool:
        """Take a screenshot of the driver"""

        # Create screenshot folder if it doesn't exist
        screenshot_folder = config.get_screenshot_directory()
        os.makedirs(screenshot_folder, exist_ok=True)

        # Create screenshot
        file_path = os.path.join(screenshot_folder, filename)
        return self.driver.get_screenshot_as_file(file_path)

    def javascript_click(self, element: SeleniumWebElement) -> None:
        """Click on element using javascript

        Args:
            element (SeleniumWebElement): Element to be clicked
        """
        self.driver.execute_script("arguments[0].click();", element)

    def javascript_set_attribute(
        self, element: SeleniumWebElement, attribute: str, value: str
    ) -> None:
        """Set attribute of element using javascript

        Args:
            element (SeleniumWebElement): Element to be clicked
            attribute (str): Attribute to be set
            value (str): Value to be set
        """
        self.driver.execute_script(
            f"arguments[0].setAttribute('{attribute}', '{value}');", element
        )

    def execute_script(self, script: str) -> None:
        """Execute javascript in the driver

        Ars:
            script (str): Javascript to be executed
        """
        self.driver.execute_script(script)

    def wait_for_element(
        self,
        element_locator: WebElementLocator,
        parent_element=None,
        expected_condition_generator: Callable = EC.visibility_of_element_located,
        ignored_exceptions: Tuple[Type[WebDriverException], ...] = (
            NoSuchElementException,
            StaleElementReferenceException,
        ),
        delay: int = 10,
    ) -> Optional[SeleniumWebElement]:
        """Wait for an element to be available in the page"""

        # Generate expected condition
        expected_condition = expected_condition_generator(element_locator)

        # Default parent element - Driver
        if not parent_element:
            parent_element = self.driver

        try:
            return WebDriverWait(
                driver=parent_element,
                timeout=delay,
                ignored_exceptions=ignored_exceptions,
            ).until(expected_condition)

        except TimeoutException:
            self.logger.debug(f"Element {element_locator} timed out")
            return None

    def wait_for_elements(
        self,
        element_locator: WebElementLocator,
        parent_element=None,
        expected_condition_generator: Callable = EC.visibility_of_element_located,
        ignored_exceptions: Tuple[Type[WebDriverException], ...] = (
            NoSuchElementException,
            StaleElementReferenceException,
        ),
        delay: int = 10,
    ) -> Optional[List[SeleniumWebElement]]:
        """Wait for more than one element to be meet a condition"""

        # Generate expected condition
        expected_condition = expected_condition_generator(element_locator)

        # Default parent element
        if not parent_element:
            parent_element = self.driver

        # Handle timeout exception
        try:
            return WebDriverWait(
                parent_element, delay, ignored_exceptions=ignored_exceptions
            ).until(expected_condition)
        except TimeoutException:
            self.logger.debug(f"Elements {element_locator} timed out")
            return None

    # This functions waits until url is the required one
    def wait_until_url_is(self, driver, url: str, delay: int = 10):
        return WebDriverWait(driver, delay).until(EC.url_to_be(url))

    def switch_to_frame(self, element: SeleniumWebElement) -> None:
        """Switch to a frame in the driver

        Args:
            element (SeleniumWebElement): Frame to be switched to
        """

        return self.driver.switch_to.frame(element)

    def switch_to_default_content(self) -> None:
        """Switch to the default content in the driver"""
        return self.driver.switch_to.default_content()

    def switch_to_tab(self, tab_index: int = 0) -> None:
        """Switch to a tab in the driver

        Args:
            tab_index (int): Tab index to be switched to
        """
        self.driver.switch_to.window(self.driver.window_handles[tab_index])

    def _safe_textContent_getter(self, element: SeleniumWebElement) -> Optional[str]:
        """Get text content of element safely

        Args:
            element (SeleniumWebElement): Element to get text content from

        Returns:
            Optional[str]: Text content of element or None if it doesn't exist
        """
        text_content = element.get_attribute("textContent")
        if isinstance(text_content, str):
            return text_content.strip()
        return None

    def get_simple_table_data(
        self, table_element: SeleniumWebElement
    ) -> TableDataSchema:
        """Get table data from selenium tbody element )

        Args:
            table_element (SeleniumWebElement): Table element to be parsed

        Returns:
            typing.Dict: Dict with table data. Headers(List[str]) and body(List[List[str]]) are keys.
        """

        body:TableBody = []

        # Collect rows
        table_rows = table_element.find_elements(By.XPATH, ".//tr")

        # `find_elements` collects the rows in reverse order. Need to reverse it.
        table_rows.reverse()

        # Get header row - Case #0
        header_row = table_rows.pop()
        headers:TableHeader = [
            self._safe_textContent_getter(cell)
            for cell in header_row.find_elements(By.XPATH, ".//th")
        ]

        if not headers:
            body.append(
                [
                    self._safe_textContent_getter(cell)
                    for cell in header_row.find_elements(By.XPATH, ".//td")
                ]
            )

        # Collect the rest of the rows
        for row in table_rows:
            body.append(
                [
                    self._safe_textContent_getter(cell)
                    for cell in row.find_elements(By.XPATH, ".//td")
                ]
            )

        # Just to have the content ordered
        body.reverse()
        return TableDataSchema(header=headers, body=body)

    def get_simple_list_data(
        self, list_element: SeleniumWebElement
    ) -> List[Optional[str]]:
        """Get list data from selenium ul element )

        Args:
            list_element (SeleniumWebElement): List element to be parsed

        Returns:
            typing.List: List with list data.
        """

        items = []

        # Collect rows
        list_items = list_element.find_elements(By.XPATH, ".//li")

        # `find_elements` collects the items in reverse order. Need to reverse it.
        list_items.reverse()

        for item in list_items:
            items.append(self._safe_textContent_getter(item))

        return items


class FirefoxDriverContext(DriverContext):
    """Firefox Webdriver for Selenium"""

    RANDOM_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:103.0) Gecko/20100101 Firefox/103.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:104.0) Gecko/20100101 Firefox/104.0"
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:99.0) Gecko/20100101 Firefox/99.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0",
    ]
    """List of random user agents for Firefox based Selenium"""

    def create_driver_manager(self) -> DriverManager:
        return GeckoDriverManager()

    def create_webdriver(self) -> webdriver.Firefox:
        """Create the Firefox webdriver"""

        # Create service
        self.service = FirefoxService(executable_path=self.manager.install())

        # Create driver
        return webdriver.Firefox(options=self.getOptions(), service=self.service)

    def getOptions(self) -> FirefoxOptions:
        """Create options for the driver"""
        # Create options
        firefox_options = FirefoxOptions()

        # Add options
        for option in self.driver_options.webdriver_options:
            firefox_options.add_argument(option)

        # Return options
        return firefox_options


class ChromeDriverContext(DriverContext):
    """Chrome Webdriver for Selenium"""

    RANDOM_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36",
    ]
    """List of random user agents for Chrome based Selenium"""

    def create_driver_manager(self) -> DriverManager:
        """Create the driver manager"""
        return ChromeDriverManager()

    def create_webdriver(self) -> webdriver.Chrome:
        """Generate the driver"""

        # Create service
        self.service = ChromeService(self.manager.install())

        # Create driver
        return webdriver.Chrome(service=self.service, options=self.getOptions())

    def getOptions(self) -> ChromeOptions:
        """Create options for the Chrome driver"""
        # Create options
        chrome_options = ChromeOptions()

        # Add options
        for option in self.driver_options.webdriver_options:
            chrome_options.add_argument(option)

        # Add experimental options
        self._add_experimental_options(chrome_options)

        # Add extensions
        for extension in self.driver_options.extensions:
            chrome_options.add_extension(extension)

        # Return options
        return chrome_options

    def _add_experimental_options(self, options: ChromeOptions) -> None:
        """Add experimental options to the Chrome driver"""
        preferences: Dict[str, str] = {
            "download.default_directory": config.get_download_directory(),
        }
        options.add_experimental_option("prefs", preferences)
