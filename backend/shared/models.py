from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class StandardResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
    timestamp: datetime = datetime.utcnow()

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int
