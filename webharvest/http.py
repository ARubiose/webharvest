import logging
from typing import Dict

import httpx

from webharvest.driver import DriverContext
from webharvest.schemas import AnyWebDriver

class SeleniumHTTPClient:
    """Selenium HTTP client. It handles cookies and headers."""

    def __init__(self, driver_context:DriverContext):
        """Initialize selenium http client."""
        self._driver_context = driver_context

        self.process_id = driver_context.process_id
        self.logger = logging.getLogger(f'{self.process_id}.{self.__class__.__name__}')

        # Client preparation
        self._initialize_client()

    def __del__(self):
        """Close session."""
        self.client.close()
        self.logger.info("Client closed.")

    @property
    def driver(self) -> AnyWebDriver:
        return self._driver_context.driver
    
    @property
    def client(self) -> httpx.Client:
        return self._client
    
    @property
    def cookies(self) -> httpx.Cookies:
        return self._cookies

    @property
    def headers(self) -> httpx.Headers:
        return self._headers

    def _initialize_client(self) -> None:
        """Open session."""
        self._initialize_headers()
        self._initialize_cookies()
        self._client = httpx.Client(headers=self.headers, cookies=self.cookies)
        self.logger.info("Client initialized.")

    def _initialize_headers(self) -> None:
        """Initialize headers."""
        self._headers = httpx.Headers()
        self._headers.update({"User-Agent": self._get_user_agent()})

    def _initialize_cookies(self) -> None:
        """Initialize cookies."""
        self._cookies = httpx.Cookies()
        for cookie in self.driver.get_cookies():
            self.cookies.set(
                name=cookie["name"],
                value=cookie["value"],
                domain=cookie.get("domain", None),
            )
    
    def update_headers(self, headers:Dict[str,str]) -> None:
        """Update headers."""
        self._headers.update(headers)
    
    def _get_user_agent(self) -> str:
        return self.driver.execute_script("return navigator.userAgent;")

    def get(self, url:str, params:dict=dict(), **kwargs) -> httpx.Response:
        """Get request."""
        return self._client.get(url, params=params, **kwargs)
    
    def post(self, url:str, data:dict=dict(), **kwargs) -> httpx.Response:
        """Post request."""
        return self._client.post(url, data=data, **kwargs)