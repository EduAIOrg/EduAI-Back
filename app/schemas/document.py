"""Document schemas."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.document import DocumentStatus


class DocumentCreate(BaseModel):
    """Document creation request."""
    title: str = Field(..., min_length=1, max_length=500, description="Document title")


class DocumentResponse(BaseModel):
    """Document response model."""
    id: UUID = Field(..., description="Document ID")
    user_id: UUID = Field(..., description="Owner user ID")
    title: str = Field(..., description="Document title")
    filename: str = Field(..., description="File path on disk")
    file_size: int = Field(..., description="File size in bytes")
    page_count: int = Field(..., description="Number of pages")
    status: DocumentStatus = Field(..., description="Processing status")
    summary: str | None = Field(None, description="Document summary")
    chroma_collection_id: str | None = Field(None, description="ChromaDB collection ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = {
        "from_attributes": True
    }


class DocumentStatusResponse(BaseModel):
    """Document status response."""
    status: DocumentStatus = Field(..., description="Processing status")
    progress_message: str = Field(..., description="Human-readable progress message")


class DocumentSummaryResponse(BaseModel):
    """Document summary response."""
    summary: str | None = Field(None, description="Document summary")
    status: DocumentStatus = Field(..., description="Processing status")
