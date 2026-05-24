"""Chat schemas."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.chat import MessageRole


class ConversationCreate(BaseModel):
    """Conversation creation request."""
    document_id: UUID | None = Field(None, description="Optional document ID for RAG")
    title: str = Field(default="Nouvelle conversation", description="Conversation title")


class MessageCreate(BaseModel):
    """Message creation request."""
    content: str = Field(..., min_length=1, description="Message content")


class MessageResponse(BaseModel):
    """Message response model."""
    id: UUID = Field(..., description="Message ID")
    conversation_id: UUID = Field(..., description="Conversation ID")
    role: MessageRole = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = {
        "from_attributes": True
    }


class ConversationResponse(BaseModel):
    """Conversation response model."""
    id: UUID = Field(..., description="Conversation ID")
    user_id: UUID = Field(..., description="Owner user ID")
    document_id: UUID | None = Field(None, description="Associated document ID")
    title: str = Field(..., description="Conversation title")
    created_at: datetime = Field(..., description="Creation timestamp")
    messages: list[MessageResponse] = Field(default_factory=list, description="Conversation messages")
    
    model_config = {
        "from_attributes": True
    }


class ConversationListItem(BaseModel):
    """Conversation list item."""
    id: UUID = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_message: str | None = Field(None, description="Last message preview")
    message_count: int = Field(default=0, description="Number of messages")
    
    model_config = {
        "from_attributes": True
    }
