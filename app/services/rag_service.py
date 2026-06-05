"""RAG (Retrieval-Augmented Generation) service."""
import logging
import time
import json
from typing import AsyncGenerator, List, Any, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from langchain.schema import HumanMessage, AIMessage, SystemMessage

from app.ai.vector_store import vector_store_manager
from app.ai.llm_factory import LLMFactory
from app.ai.prompts import get_rag_prompt, get_general_chat_prompt, get_context_verification_prompt
from app.models.chat import Message, MessageRole, ChatSession, ChatMessage, ChatSummary
from app.utils.security_utils import PromptInjectionDetector, ContextSanitizer
from app.services.observability_service import AIObservabilityService

logger = logging.getLogger(__name__)


async def retrieve_context(
    db: AsyncSession,
    question: str,
    document_id: UUID | None
) -> tuple[str, List[Dict[str, Any]], float]:
    """Retrieve relevant context and build source citations."""
    logger.info(
        f"RETRIEVE DEBUG | Entry | document_id received={document_id} | question received='{question}'"
    )
    sources = []
    relevant_docs = []
    if document_id:
        logger.info(f"RETRIEVE DEBUG | Calling similarity_search on vector store for doc {document_id}")
        relevant_docs = await vector_store_manager.similarity_search(
            db=db,
            document_id=document_id,
            query=question,
            k=5
        )
        logger.info(f"RETRIEVE DEBUG | Similarity search returned {len(relevant_docs)} raw documents")
        
        if not relevant_docs:
            context = "Aucun contexte pertinent trouvé dans le document."
        else:
            # Sort relevant docs explicitly by score descending
            sorted_docs = sorted(relevant_docs, key=lambda d: d.metadata.get("score", 0.0), reverse=True)
            
            sanitized_chunks = []
            used_contents = set()
            total_chars = 0
            MAX_CHARS = 3000
            
            for doc in sorted_docs:
                clean_text = ContextSanitizer.sanitize(doc.page_content)
                
                # De-duplicate chunks
                if clean_text in used_contents:
                    continue
                
                # Check if adding this chunk exceeds 3000 characters
                if total_chars + len(clean_text) + (2 if sanitized_chunks else 0) > MAX_CHARS:
                    # Truncate to fit within the limit exactly
                    remaining = MAX_CHARS - total_chars - (2 if sanitized_chunks else 0)
                    if remaining >= 50:
                        truncated_text = clean_text[:remaining]
                        sanitized_chunks.append(truncated_text)
                        used_contents.add(truncated_text)
                        total_chars += len(truncated_text) + (2 if len(sanitized_chunks) > 1 else 0)
                        sources.append({
                            "document": doc.metadata.get("document_name", "Document"),
                            "page": doc.metadata.get("page"),
                            "score": doc.metadata.get("score"),
                            "content": truncated_text
                        })
                    break
                
                sanitized_chunks.append(clean_text)
                used_contents.add(clean_text)
                total_chars += len(clean_text) + (2 if len(sanitized_chunks) > 1 else 0)
                
                sources.append({
                    "document": doc.metadata.get("document_name", "Document"),
                    "page": doc.metadata.get("page"),
                    "score": doc.metadata.get("score"),
                    "content": clean_text
                })
                
            # Sort sources by score descending
            sources = sorted(sources, key=lambda x: x.get("score", 0.0), reverse=True)
            context = "\n\n".join(sanitized_chunks)
            
            # Log metrics
            logger.info(
                f"RAG Context Metrics: context_length={len(context)}, "
                f"chunks_used={len(sanitized_chunks)}, "
                f"scores={[s['score'] for s in sources]}"
            )
    else:
        context = ""
        
    rel_docs_count = len(relevant_docs)
    logger.info(
        f"RETRIEVE DEBUG | retrieve_context | document_id={document_id} | "
        f"relevant_docs count={rel_docs_count} | final context size={len(context)} | "
        f"number of sources={len(sources)} | preview of first 500 chars='{context[:500]}'"
    )
    
    best_score = max(
        [s.get("score", 0.0) for s in sources],
        default=0.0
    )
    
    return context, sources, best_score


class RAGService:
    """Service for RAG-based chat operations."""
    
    @staticmethod
    async def query_document(
        db: AsyncSession,
        question: str,
        document_id: UUID | None,
        conversation_history: List[Message],
        stream: bool = True,
        user_id: UUID | None = None,
        session_id: UUID | None = None
    ) -> AsyncGenerator[Any, None]:
        """
        Query a document using RAG or general chat.
        
        Args:
            db: Database session
            question: User question
            document_id: Optional document ID for RAG
            conversation_history: Previous messages in conversation
            stream: Whether to stream the response
            user_id: Optional authenticated user UUID
            session_id: Optional session UUID for database memory persistence
            
        Yields:
            dict or str: Sources dictionary first, then response tokens
        """
        # Security: Prompt Injection Check
        if PromptInjectionDetector.is_injection(question):
            logger.warning(f"Blocking prompt injection: {question}")
            yield {"sources": []}
            yield "Désolé, votre requête contient une tentative d'injection de prompt détectée par nos systèmes de sécurité."
            return

        logger.info(
            f"RAG DEBUG | document_id={document_id}"
        )

        start_time = time.time()
        prompt_tokens = len(question.split()) # Simple heuristic for prompt tokens
        completion_tokens = 0
        status = "success"
        error_msg = None
        
        try:
            # Create LLM
            llm = LLMFactory.create_chat_llm(streaming=stream)
            
            # Handle short/long term DB memory if session_id is provided
            chat_history = []
            
            if session_id:
                # Retrieve last 10 messages from ChatMessage database
                msg_stmt = (
                    select(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(10)
                )
                msg_res = await db.execute(msg_stmt)
                db_messages = list(reversed(msg_res.scalars().all()))
                
                for msg in db_messages:
                    if msg.role == MessageRole.USER or msg.role == "user":
                        chat_history.append(HumanMessage(content=msg.content))
                    elif msg.role == MessageRole.ASSISTANT or msg.role == "assistant":
                        chat_history.append(AIMessage(content=msg.content))
                
                # Fetch rolling ChatSummary
                sum_stmt = select(ChatSummary).where(ChatSummary.session_id == session_id)
                sum_res = await db.execute(sum_stmt)
                db_summary = sum_res.scalar_one_or_none()
                if db_summary and db_summary.summary:
                    summary_msg = SystemMessage(
                        content=f"Voici le résumé des conversations précédentes de l'étudiant à garder en mémoire :\n{db_summary.summary}"
                    )
                    chat_history.insert(0, summary_msg)
            else:
                chat_history = RAGService._prepare_chat_history(conversation_history)
            
            # Retrieve context directly (Retrieve step)
            context, sources, best_score = await retrieve_context(
                db=db,
                question=question,
                document_id=document_id
            )
            
            logger.info(
                f"RAG DEBUG | query_document received document_id={document_id}"
            )
            logger.info(
                f"CONTEXT DEBUG | query_document | context length transmitted to prompt={len(context)}"
            )
            
            # Block questions without relevant context if a document is queried
            if document_id:
                MIN_CONTEXT_SCORE = 0.80
                
                # Check score threshold
                if best_score < MIN_CONTEXT_SCORE:
                    logger.info(
                        f"RAG VALIDATION | best_score={best_score:.3f} < {MIN_CONTEXT_SCORE} | "
                        f"Blocking generation: low relevance score"
                    )
                    yield {"sources": sources}
                    yield "Cette information n'est pas présente dans le document fourni."
                    
                    try:
                        latency_ms = (time.time() - start_time) * 1000
                        from app.config import settings
                        await AIObservabilityService.log_llm_request(
                            db=db,
                            model=settings.HF_LLM_MODEL,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=0,
                            latency_ms=latency_ms,
                            status="success",
                            user_id=user_id,
                            error_message="Blocked: relevance score too low"
                        )
                    except Exception as obs_err:
                        logger.error(f"Non-blocking observability error: {obs_err}")
                    return

                # Prompt-based Context Verification step
                verifier_prompt = get_context_verification_prompt()
                verifier_llm = LLMFactory.create_chat_llm(streaming=False)
                verifier_chain = verifier_prompt | verifier_llm
                
                logger.info("RAG VALIDATION | Running context verification step...")
                verification_res = await verifier_chain.ainvoke({
                    "question": question,
                    "context": context
                })
                verification_text = verification_res.content if hasattr(verification_res, 'content') else str(verification_res)
                verification_clean = verification_text.strip().upper()
                
                logger.info(f"RAG VALIDATION | verifier response: {verification_clean}")
                
                if "NO" in verification_clean or "YES" not in verification_clean:
                    logger.info(
                        f"RAG VALIDATION | best_score={best_score:.3f} | verifier=NO | "
                        f"Blocking generation: context does not answer question"
                    )
                    yield {"sources": sources}
                    yield "Cette information n'est pas présente dans le document fourni."
                    
                    try:
                        latency_ms = (time.time() - start_time) * 1000
                        from app.config import settings
                        await AIObservabilityService.log_llm_request(
                            db=db,
                            model=settings.HF_LLM_MODEL,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=0,
                            latency_ms=latency_ms,
                            status="success",
                            user_id=user_id,
                            error_message="Blocked: verification prompt returned NO"
                        )
                    except Exception as obs_err:
                        logger.error(f"Non-blocking observability error: {obs_err}")
                    return

                logger.info(
                    f"RAG VALIDATION | best_score={best_score:.3f}\n"
                    f"RAG VALIDATION | verifier=YES\n"
                    f"RAG VALIDATION | chunks_used={len(sources)}"
                )

            # Send citations first
            yield {"sources": sources}
            
            response_content = []
            
            if stream:
                if context:
                    prompt = get_rag_prompt()
                    chain = prompt | llm
                    async for chunk in chain.astream({
                        "context": context,
                        "chat_history": chat_history,
                        "question": question
                    }):
                        token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                        response_content.append(token)
                        completion_tokens += 1
                        yield token
                else:
                    prompt = get_general_chat_prompt()
                    chain = prompt | llm
                    async for chunk in chain.astream({
                        "chat_history": chat_history,
                        "question": question
                    }):
                        token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                        response_content.append(token)
                        completion_tokens += 1
                        yield token
            else:
                # Direct non-streaming invocation
                if context:
                    prompt = get_rag_prompt()
                    chain = prompt | llm
                    response = await chain.ainvoke({
                        "context": context,
                        "chat_history": chat_history,
                        "question": question
                    })
                else:
                    prompt = get_general_chat_prompt()
                    chain = prompt | llm
                    response = await chain.ainvoke({
                        "chat_history": chat_history,
                        "question": question
                    })
                resp = response.content if hasattr(response, 'content') else str(response)
                response_content.append(resp)
                completion_tokens = len(resp.split())
                yield resp
                
            # Log LLM request performance
            try:
                latency_ms = (time.time() - start_time) * 1000
                from app.config import settings
                await AIObservabilityService.log_llm_request(
                    db=db,
                    model=settings.HF_LLM_MODEL,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency_ms,
                    status=status,
                    user_id=user_id,
                    error_message=error_msg
                )
            except Exception as obs_err:
                logger.error(f"Non-blocking observability error (LLM success): {obs_err}")
            
            # Trigger auto-summarization if session is active
            if session_id:
                import asyncio
                # Spawn auto-summarization check in background
                asyncio.create_task(RAGService.summarize_session_async(session_id))
                
        except Exception as e:
            status = "error"
            error_msg = str(e)
            logger.error(f"Error in RAG query: {e}")
            try:
                latency_ms = (time.time() - start_time) * 1000
                await AIObservabilityService.log_llm_request(
                    db=db,
                    model=LLMFactory.ACTIVE_MODEL,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=0,
                    latency_ms=latency_ms,
                    status=status,
                    user_id=user_id,
                    error_message=error_msg
                )
            except Exception as obs_err:
                logger.error(f"Non-blocking observability error (LLM error): {obs_err}")
            yield f"Désolé, une erreur s'est produite: {str(e)}"
    
    @staticmethod
    def _prepare_chat_history(messages: List[Message]) -> List:
        """Prepare chat history for LangChain."""
        chat_history = []
        recent_messages = messages[-10:] if len(messages) > 10 else messages
        
        for msg in recent_messages:
            if msg.role == MessageRole.USER or msg.role == "user":
                chat_history.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT or msg.role == "assistant":
                chat_history.append(AIMessage(content=msg.content))
        
        return chat_history
    
    @staticmethod
    async def summarize_session_async(session_id: UUID) -> None:
        """
        Asynchronously summarize session in background without blocking the main thread or
        request db session. Uses rules:
        - summarize if message count >= 20 and message count % 20 == 0
        - or if 30 minutes elapsed since last summary and at least 1 new message exists
        """
        try:
            from app.database import AsyncSessionLocal
            from datetime import datetime, timezone
            
            async with AsyncSessionLocal() as db:
                # Count total messages
                count_stmt = select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
                count_res = await db.execute(count_stmt)
                message_count = count_res.scalar() or 0
                
                if message_count == 0:
                    return
                
                # Fetch rolling ChatSummary
                sum_stmt = select(ChatSummary).where(ChatSummary.session_id == session_id)
                sum_res = await db.execute(sum_stmt)
                chat_summary = sum_res.scalar_one_or_none()
                
                should_summarize = False
                
                if not chat_summary:
                    # Summarize on first 20 messages (or if user requests it, let's trigger it at >= 20)
                    if message_count >= 20:
                        should_summarize = True
                else:
                    # Check how many messages have been added since last summary
                    # Or check elapsed time: 30 minutes
                    last_summary_time = chat_summary.last_summary_at
                    if last_summary_time.tzinfo is None:
                        last_summary_time = last_summary_time.replace(tzinfo=timezone.utc)
                    
                    now = datetime.now(timezone.utc)
                    elapsed_minutes = (now - last_summary_time).total_seconds() / 60.0
                    
                    # Count messages created after the last summary
                    new_msg_stmt = select(func.count(ChatMessage.id)).where(
                        ChatMessage.session_id == session_id,
                        ChatMessage.created_at > chat_summary.last_summary_at
                    )
                    new_msg_res = await db.execute(new_msg_stmt)
                    new_msg_count = new_msg_res.scalar() or 0
                    
                    if new_msg_count >= 20:
                        should_summarize = True
                    elif elapsed_minutes >= 30.0 and new_msg_count > 0:
                        should_summarize = True
                
                if should_summarize:
                    logger.info(f"Summarizing session {session_id} (non-blocking task)...")
                    # Fetch all messages to generate full summary
                    msg_stmt = (
                        select(ChatMessage)
                        .where(ChatMessage.session_id == session_id)
                        .order_by(ChatMessage.created_at.asc())
                    )
                    msg_res = await db.execute(msg_stmt)
                    messages = msg_res.scalars().all()
                    
                    chat_text = "\n".join([f"{m.role}: {m.content}" for m in messages])
                    
                    # Generate summary using HF model
                    llm = LLMFactory.create_chat_llm(streaming=False)
                    summary_prompt = f"Résume brièvement les points clés de la conversation suivante en français en moins de 3 phrases :\n\n{chat_text}"
                    response = await llm.ainvoke(summary_prompt)
                    summary_content = response.content if hasattr(response, 'content') else str(response)
                    
                    if chat_summary:
                        chat_summary.summary = summary_content
                        chat_summary.last_summary_at = func.now()
                    else:
                        chat_summary = ChatSummary(
                            session_id=session_id,
                            summary=summary_content,
                            last_summary_at=func.now()
                        )
                        db.add(chat_summary)
                    
                    await db.commit()
                    logger.info(f"Auto-summarization complete for session {session_id}")
        except Exception as e:
            logger.error(f"Error in non-blocking auto-summarization for session {session_id}: {e}", exc_info=True)
            
    @staticmethod
    async def generate_response(
        db: AsyncSession,
        question: str,
        document_id: UUID | None,
        conversation_history: List[Message],
        user_id: UUID | None = None,
        session_id: UUID | None = None
    ) -> str:
        """Generate a complete response (non-streaming)."""
        response_parts = []
        
        async for chunk in RAGService.query_document(
            db=db,
            question=question,
            document_id=document_id,
            conversation_history=conversation_history,
            stream=False,
            user_id=user_id,
            session_id=session_id
        ):
            if isinstance(chunk, str):
                response_parts.append(chunk)
        
        return "".join(response_parts)
