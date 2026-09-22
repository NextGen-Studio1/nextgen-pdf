from typing import Optional
from pydantic import BaseModel, Field

class CompressOptions(BaseModel):
    level: str = Field(default="balanced", description="best, balanced, smallest")

class SplitOptions(BaseModel):
    pages: Optional[str] = Field(default=None, description="Page ranges, e.g. 1-3,5,8-10")

class ProtectOptions(BaseModel):
    password: str = Field(..., min_length=1, description="Password to lock the PDF")

class RotateOptions(BaseModel):
    angle: int = Field(default=90, description="90, 180, 270")
