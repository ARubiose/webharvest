"""Module for defining schemas for the webscrapper app."""
import enum
from typing import Union, Optional, List, Tuple, Dict, TypeAlias, Generic, TypeVar

from pydantic import BaseModel, Field, field_validator
from selenium.webdriver import Chrome, Firefox

# Type aliases
WebElementLocator:TypeAlias = Tuple[str, str]
ExpectedConditionGenerator:TypeAlias = Tuple[str, str, str]
AnyWebDriver:TypeAlias = Union[Chrome, Firefox]
AnyWebDriverManager:TypeAlias = Union[Chrome, Firefox]
TableHeader:TypeAlias = List[Optional[str]]
TableBody:TypeAlias = List[List[Optional[str]]]

# Generics
OutputDataT = TypeVar('OutputDataT', bound=BaseModel)
InputDataT = TypeVar('InputDataT', bound=BaseModel)

class DriverTypeEnum(str, enum.Enum):
    """Driver type enum."""
    CHROME = 'chrome'
    FIREFOX = 'firefox'

class ContextStatusEnum(enum.Enum):
    """Context status enum."""
    INITIALIZED = enum.auto()
    SUCCEED = enum.auto()
    FAILED = enum.auto()
    CRITICAL = enum.auto()
    CANCELLED = enum.auto()

# Schemas
class WebscrapperOptionsSchema(BaseModel):
    """Webscrapper options."""
    threads_num: int = Field(title='Number of threads', description="Number of threads to use for webscrapping", default=1)

class DriverOptionsSchema(BaseModel):
    """Driver options"""
    driver_type: DriverTypeEnum = Field(title='Driver type', description="Type of driver to use for webscrapping", default=DriverTypeEnum.CHROME)
    webdriver_options: List[str] = Field(title='Webdriver options', description="Webdriver options", default_factory=list)
    extensions: List[str] = Field(title='Extensions required', description="Extensions required for the webdriver", default_factory=list)

    @field_validator('driver_type', mode='before')
    def validate_driver_type(cls, value):
        if isinstance(value, str):
            try:
                return DriverTypeEnum(value)
            except KeyError:
                raise KeyError(f"Invalid driver type {value}. Currently supported drivers are: {DriverTypeEnum.__members__.keys()}")
        return value

class ContextStatusSchema(BaseModel, Generic[InputDataT, OutputDataT]):
    """Context status schema for a webscrapping run."""
    status: ContextStatusEnum = Field(title='Status', description="Status of the webscrapping run", default=ContextStatusEnum.INITIALIZED)
    error: Optional[Exception] = Field(None, title='Error', description="Exception if the webscrapping run failed")
    current_state: Optional[str] = Field(None, title='Current state', description="Current state of the webscrapping run")
    input_data: InputDataT = Field(title='Input data', description="Input data for the webscrapping run")
    output_data: OutputDataT = Field(title='Output data', description="Output data for the webscrapping run")
    tmp_data: Dict = Field(title='Temporary data', description="Temporary data for the webscrapping run", default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True


# Data schemas
class TableDataSchema(BaseModel):
    """Table data schema."""
    header: TableHeader = Field(title='Table header', description="Table header")
    body: TableBody = Field(title='Table body', description="Table body")
    