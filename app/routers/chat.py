"""Chat router with SSE streaming."""
import json
import logging
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.chat import Conversation, Message, MessageRole
from app.models.document import Document, DocumentStatus
from app.schemas.chat import (
    ConversationCreate,
    ConversationResponse,
    ConversationListItem,
    MessageCreate,
    MessageResponse
)
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/conversations", response_model=List[ConversationListItem])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[ConversationListItem]:
    """
    List all conversations for the current user.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        list: List of conversations
    """
    try:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == current_user.id)
            .order_by(Conversation.created_at.desc())
        )
        conversations = result.scalars().all()
        
        # Build response with last message
        response = []
        for conv in conversations:
            # Get last message
            msg_result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            last_msg = msg_result.scalar_one_or_none()
            
            # Count messages
            count_result = await db.execute(
                select(func.count(Message.id))
                .where(Message.conversation_id == conv.id)
            )
            message_count = count_result.scalar()
            
            response.append(ConversationListItem(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                last_message=last_msg.content[:100] if last_msg else None,
                message_count=message_count
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list conversations"
        )


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    """
    Create a new conversation.
    
    Args:
        request: Conversation creation request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        ConversationResponse: Created conversation
    """
    try:
        # Validate document if provided
        if request.document_id:
            doc_result = await db.execute(
                select(Document).where(Document.id == request.document_id)
            )
            document = doc_result.scalar_one_or_none()
            
            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found"
                )
            
            if document.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            
            if document.status != DocumentStatus.READY:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Document is not ready yet"
                )
        
        # Create conversation
        conversation = Conversation(
            user_id=current_user.id,
            document_id=request.document_id,
            title=request.title
        )
        
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        
        logger.info(f"Conversation created: {conversation.id}")
        
        return ConversationResponse.model_validate(conversation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation"
        )


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[MessageResponse]:
    """
    Get all messages in a conversation.
    
    Args:
        conversation_id: Conversation UUID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        list: List of messages
    """
    try:
        # Get conversation
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        if conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get messages
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = msg_result.scalars().all()
        
        return [MessageResponse.model_validate(msg) for msg in messages]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages"
        )


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    request: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message and stream the AI response using SSE.
    
    Args:
        conversation_id: Conversation UUID
        request: Message content
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        StreamingResponse: SSE stream of AI response
    """
    try:
        # Get conversation
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        if conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Save user message
        user_message = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=request.content
        )
        db.add(user_message)
        await db.commit()
        await db.refresh(user_message)
        
        # Stream AI response
        async def generate_sse():
            """Generate SSE stream."""
            response_content = []
            
            try:
                # Get conversation history
                history_result = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                )
                history = history_result.scalars().all()
                
                # Stream response
                async for token in RAGService.query_document(
                    question=request.content,
                    document_id=conversation.document_id,
                    conversation_history=history[:-1],  # Exclude the just-added user message
                    stream=True
                ):
                    response_content.append(token)
                    # Send token as SSE
                    yield f"data: {json.dumps({'token': token})}\n\n"
                
                # Save assistant message
                full_response = "".join(response_content)
                assistant_message = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=full_response
                )
                db.add(assistant_message)
                await db.commit()
                await db.refresh(assistant_message)
                
                # Send completion event
                yield f"data: {json.dumps({'done': True, 'message_id': str(assistant_message.id)})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in SSE stream: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a conversation.
    
    Args:
        conversation_id: Conversation UUID
        current_user: Current authenticated user
        db: Database session
    """
    try:
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        if conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        await db.delete(conversation)
        await db.commit()
        
        logger.info(f"Conversation deleted: {conversation_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )
