from typing import Optional
from pydantic import BaseModel, Field

class InputData(BaseModel):
    """Input data schema"""
    search_item: str = Field(title="Search Item", description="Search item to be scrapped")

class OutputData(BaseModel):
    """Output data schema"""
    data: Optional[str] = Field(None, title="Data", description="Scrapped data")