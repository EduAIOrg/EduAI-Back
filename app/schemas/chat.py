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


class SourceCitationResponse(BaseModel):
    """Source citation model."""
    document: str = Field(..., description="Document filename/title")
    page: int | None = Field(None, description="Page number")
    score: float | None = Field(None, description="Relevance score")
    content: str | None = Field(None, description="Text chunk content")


class MessageResponse(BaseModel):
    """Message response model."""
    id: UUID = Field(..., description="Message ID")
    conversation_id: UUID = Field(..., description="Conversation ID")
    role: MessageRole = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    sources: list[SourceCitationResponse] | None = Field(None, description="Sources cited in the response")
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


class FeedbackCreate(BaseModel):
    """Request schema for creating RAG feedback."""
    message_id: UUID | None = Field(None, description="Standard message UUID")
    chat_message_id: UUID | None = Field(None, description="Memory chat message UUID")
    is_positive: bool = Field(..., description="True if positive (like), False if negative (dislike)")
    comment: str | None = Field(None, description="Optional text comment")


class FeedbackResponse(BaseModel):
    """Response schema for RAG feedback."""
    id: UUID = Field(..., description="Feedback UUID")
    user_id: UUID = Field(..., description="User UUID who left feedback")
    message_id: UUID | None = Field(None, description="Message UUID")
    chat_message_id: UUID | None = Field(None, description="Memory message UUID")
    is_positive: bool = Field(..., description="Like/Dislike")
    comment: str | None = Field(None, description="Comment text")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = {
        "from_attributes": True
    }


class FeedbackStatsResponse(BaseModel):
    """Response schema for feedback statistics."""
    total_count: int = Field(..., description="Total feedback count")
    like_count: int = Field(..., description="Total likes")
    dislike_count: int = Field(..., description="Total dislikes")
    like_ratio: float = Field(..., description="Percentage of positive ratings (0 to 1)")
    recent_comments: list[str] = Field(default_factory=list, description="Recent comments left by users")

