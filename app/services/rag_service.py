"""RAG (Retrieval-Augmented Generation) service."""
import logging
from typing import AsyncGenerator, List
from uuid import UUID
from langchain.schema import HumanMessage, AIMessage

from app.ai.vector_store import vector_store_manager
from app.ai.llm_factory import LLMFactory
from app.ai.prompts import get_rag_prompt, get_general_chat_prompt
from app.models.chat import Message, MessageRole

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG-based chat operations."""
    
    @staticmethod
    async def query_document(
        question: str,
        document_id: UUID | None,
        conversation_history: List[Message],
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Query a document using RAG or general chat.
        
        Args:
            question: User question
            document_id: Optional document ID for RAG
            conversation_history: Previous messages in conversation
            stream: Whether to stream the response
            
        Yields:
            str: Response tokens
        """
        try:
            # Create LLM
            llm = LLMFactory.create_chat_llm(streaming=stream)
            
            # Prepare chat history
            chat_history = RAGService._prepare_chat_history(conversation_history)
            
            if document_id:
                # RAG mode: retrieve relevant context
                logger.info(f"RAG query for document {document_id}")
                
                # Retrieve relevant chunks
                relevant_docs = vector_store_manager.similarity_search(
                    document_id=document_id,
                    query=question,
                    k=5
                )
                
                if not relevant_docs:
                    context = "Aucun contexte pertinent trouvé dans le document."
                else:
                    context = "\n\n".join([doc.page_content for doc in relevant_docs])
                
                # Use RAG prompt
                prompt = get_rag_prompt()
                
                # Create chain
                chain = prompt | llm
                
                # Stream response
                async for chunk in chain.astream({
                    "context": context,
                    "chat_history": chat_history,
                    "question": question
                }):
                    if hasattr(chunk, 'content'):
                        yield chunk.content
                    else:
                        yield str(chunk)
            else:
                # General chat mode
                logger.info("General chat query")
                
                # Use general chat prompt
                prompt = get_general_chat_prompt()
                
                # Create chain
                chain = prompt | llm
                
                # Stream response
                async for chunk in chain.astream({
                    "chat_history": chat_history,
                    "question": question
                }):
                    if hasattr(chunk, 'content'):
                        yield chunk.content
                    else:
                        yield str(chunk)
                        
        except Exception as e:
            logger.error(f"Error in RAG query: {e}")
            yield f"Désolé, une erreur s'est produite: {str(e)}"
    
    @staticmethod
    def _prepare_chat_history(messages: List[Message]) -> List:
        """
        Prepare chat history for LangChain.
        
        Args:
            messages: List of Message objects
            
        Returns:
            list: List of LangChain message objects
        """
        chat_history = []
        
        # Use last 10 messages for context window
        recent_messages = messages[-10:] if len(messages) > 10 else messages
        
        for msg in recent_messages:
            if msg.role == MessageRole.USER:
                chat_history.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                chat_history.append(AIMessage(content=msg.content))
        
        return chat_history
    
    @staticmethod
    async def generate_response(
        question: str,
        document_id: UUID | None,
        conversation_history: List[Message]
    ) -> str:
        """
        Generate a complete response (non-streaming).
        
        Args:
            question: User question
            document_id: Optional document ID for RAG
            conversation_history: Previous messages
            
        Returns:
            str: Complete response
        """
        response_parts = []
        
        async for chunk in RAGService.query_document(
            question=question,
            document_id=document_id,
            conversation_history=conversation_history,
            stream=True
        ):
            response_parts.append(chunk)
        
        return "".join(response_parts)
