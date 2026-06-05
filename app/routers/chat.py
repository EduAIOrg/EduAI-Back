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
        
        return ConversationResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            document_id=conversation.document_id,
            title=conversation.title,
            created_at=conversation.created_at,
            messages=[]
        )
        
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
        
        return [
            MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                role=msg.role,
                content=msg.content,
                sources=msg.sources,
                created_at=msg.created_at
            )
            for msg in messages
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages"
        )


from sse_starlette.sse import EventSourceResponse
from app.services.quota_service import QuotaService
from app.models.chat import ChatSession, ChatMessage


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
        EventSourceResponse: SSE stream of AI response
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
        
        logger.info(
            f"CHAT DEBUG | conversation_id={conversation.id} | document_id={conversation.document_id}"
        )
        
        if conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
            
        # Check SaaS daily Quota limits
        if not await QuotaService.check_quota(db, current_user, "chat"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Quota journalier de messages dépassé pour votre forfait."
            )
            
        # Register a ChatSession in database if not exists
        chat_sess_result = await db.execute(
            select(ChatSession).where(ChatSession.conversation_id == conversation_id)
        )
        chat_sess = chat_sess_result.scalar_one_or_none()
        if not chat_sess:
            chat_sess = ChatSession(
                conversation_id=conversation_id,
                user_id=current_user.id,
                document_id=conversation.document_id,
                title=conversation.title
            )
            db.add(chat_sess)
            await db.commit()
            await db.refresh(chat_sess)
        
        # Save user message to standard messages table
        user_message = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=request.content
        )
        db.add(user_message)
        
        # Save user message to session chat_messages table (memory)
        db_user_message = ChatMessage(
            session_id=chat_sess.id,
            role="user",
            content=request.content
        )
        db.add(db_user_message)
        await db.commit()
        await db.refresh(user_message)
        await db.refresh(db_user_message)
        
        # Log quota usage
        await QuotaService.increment_usage(db, current_user.id, "chat")
        
        # Stream AI response using SSE
        async def generate_sse():
            response_content = []
            sources_to_save = None
            
            try:
                async for chunk in RAGService.query_document(
                    db=db,
                    question=request.content,
                    document_id=conversation.document_id,
                    conversation_history=[], # handled internally by memory session_id
                    stream=True,
                    user_id=current_user.id,
                    session_id=chat_sess.id
                ):
                    if isinstance(chunk, dict) and "sources" in chunk:
                        sources_to_save = chunk["sources"]
                        yield {"data": json.dumps({"sources": chunk["sources"]})}
                    else:
                        response_content.append(chunk)
                        yield {"data": json.dumps({"token": chunk})}
                
                # Save assistant message
                full_response = "".join(response_content)
                
                # Save assistant message to standard messages
                assistant_message = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=full_response,
                    sources=sources_to_save
                )
                db.add(assistant_message)
                
                # Save assistant message to memory chat_messages
                db_assistant_message = ChatMessage(
                    session_id=chat_sess.id,
                    role="assistant",
                    content=full_response,
                    sources=sources_to_save
                )
                db.add(db_assistant_message)
                await db.commit()
                await db.refresh(assistant_message)
                await db.refresh(db_assistant_message)
                
                # Send completion event
                yield {"data": json.dumps({'done': True, 'message_id': str(assistant_message.id)})}
                
            except Exception as e:
                import uuid
                correlation_id = str(uuid.uuid4())
                logger.error(f"Error in SSE stream [Correlation ID: {correlation_id}]: {e}", exc_info=True)
                yield {"data": json.dumps({"error": "Internal generation error"})}
        
        return EventSourceResponse(generate_sse())
        
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


from app.schemas.chat import FeedbackCreate, FeedbackResponse, FeedbackStatsResponse
from app.models.feedback import RAGFeedback


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_rag_feedback(
    request: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> FeedbackResponse:
    """
    Create a feedback rating (like/dislike/comment) on a RAG message answer.
    """
    try:
        feedback = RAGFeedback(
            user_id=current_user.id,
            message_id=request.message_id,
            chat_message_id=request.chat_message_id,
            is_positive=request.is_positive,
            comment=request.comment
        )
        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)
        
        logger.info(f"RAG feedback recorded: {feedback.id}")
        return FeedbackResponse(
            id=feedback.id,
            user_id=feedback.user_id,
            message_id=feedback.message_id,
            chat_message_id=feedback.chat_message_id,
            is_positive=feedback.is_positive,
            comment=feedback.comment,
            created_at=feedback.created_at
        )
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record feedback"
        )


@router.get("/feedback/stats", response_model=FeedbackStatsResponse)
async def get_rag_feedback_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> FeedbackStatsResponse:
    """
    Retrieve aggregate statistics on RAG feedback.
    """
    try:
        # Count totals
        total_stmt = select(func.count(RAGFeedback.id))
        total_res = await db.execute(total_stmt)
        total_count = total_res.scalar() or 0
        
        # Count positive
        positive_stmt = select(func.count(RAGFeedback.id)).where(RAGFeedback.is_positive == True)
        positive_res = await db.execute(positive_stmt)
        like_count = positive_res.scalar() or 0
        
        dislike_count = total_count - like_count
        like_ratio = like_count / total_count if total_count > 0 else 1.0
        
        # Get recent comments
        comments_stmt = (
            select(RAGFeedback.comment)
            .where(RAGFeedback.comment.isnot(None))
            .where(RAGFeedback.comment != "")
            .order_by(RAGFeedback.created_at.desc())
            .limit(10)
        )
        comments_res = await db.execute(comments_stmt)
        recent_comments = [row[0] for row in comments_res.fetchall()]
        
        return FeedbackStatsResponse(
            total_count=total_count,
            like_count=like_count,
            dislike_count=dislike_count,
            like_ratio=round(like_ratio, 2),
            recent_comments=recent_comments
        )
    except Exception as e:
        logger.error(f"Error fetching feedback stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feedback stats"
        )
