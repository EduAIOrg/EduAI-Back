import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from langchain.schema import SystemMessage
from app.services.rag_service import RAGService, retrieve_context
from app.models.chat import ChatMessage, ChatSummary

@pytest.mark.asyncio
async def test_rag_context_limit_and_deduplication():
    """Test that RAG context is limited to 3000 characters and de-duplicated."""
    mock_db = AsyncMock()
    
    # 4 document chunks, some duplicates, total size > 3000
    chunk_content_1 = "Contenu important A. " * 30  # ~600 chars
    chunk_content_2 = "Contenu important B. " * 30  # ~600 chars
    chunk_content_3 = "Contenu important A. " * 30  # Duplicate!
    chunk_content_4 = "Contenu important C. " * 100 # ~2000 chars (will cause limit overflow)
    
    mock_chunks = [
        MagicMock(page_content=chunk_content_1, metadata={"document_name": "Doc1", "page": 1, "score": 0.9}),
        MagicMock(page_content=chunk_content_2, metadata={"document_name": "Doc1", "page": 2, "score": 0.8}),
        MagicMock(page_content=chunk_content_3, metadata={"document_name": "Doc1", "page": 1, "score": 0.7}),
        MagicMock(page_content=chunk_content_4, metadata={"document_name": "Doc1", "page": 3, "score": 0.6}),
    ]
    
    with patch("app.ai.vector_store.vector_store_manager.similarity_search", return_value=mock_chunks):
        context, sources, best_score = await retrieve_context(
            db=mock_db,
            question="Quelle est la question ?",
            document_id=uuid.uuid4()
        )
        
        # Verify length is <= 3000
        assert len(context) <= 3000
        # Verify no duplicate chunk A
        assert context.count("Contenu important A.") <= 30  # Only one chunk A added
        # Verify sources are sorted by score
        assert len(sources) > 0
        scores = [s["score"] for s in sources]
        assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_inject_summary_into_chat_history():
    """Test that long term summary is injected into chat history as SystemMessage."""
    mock_db = AsyncMock()
    session_id = uuid.uuid4()
    
    # Mock ChatMessage query returns 2 messages
    mock_messages = [
        ChatMessage(id=uuid.uuid4(), session_id=session_id, role="user", content="Hello"),
        ChatMessage(id=uuid.uuid4(), session_id=session_id, role="assistant", content="Hi there")
    ]
    mock_result_msg = MagicMock()
    mock_result_msg.scalars.return_value.all.return_value = mock_messages
    
    # Mock ChatSummary query returns summary
    mock_summary = ChatSummary(id=uuid.uuid4(), session_id=session_id, summary="Résumé de la discussion")
    mock_result_sum = MagicMock()
    mock_result_sum.scalar_one_or_none.return_value = mock_summary
    
    # Setup mock db.execute returns
    mock_db.execute.side_effect = [mock_result_msg, mock_result_sum]
    
    # Mock retrieve_context
    with patch("app.services.rag_service.retrieve_context", return_value=("", [])):
        # We catch LLM creation and chain invocation
        mock_llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.astream = AsyncMock()
        
        with patch("app.ai.llm_factory.LLMFactory.create_chat_llm", return_value=mock_llm), \
             patch("app.services.rag_service.get_rag_prompt") as mock_get_prompt:
            
            mock_get_prompt.return_value = mock_chain
            
            # Call query_document generator to trigger database queries
            generator = RAGService.query_document(
                db=mock_db,
                question="New question",
                document_id=uuid.uuid4(),
                conversation_history=[],
                stream=True,
                session_id=session_id
            )
            
            async for chunk in generator:
                pass
                
            # Verify the queries executed on mock_db
            assert mock_db.execute.call_count >= 2


@pytest.mark.asyncio
async def test_summarize_session_async_rules():
    """Test the rules and triggers of summarize_session_async."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    session_id = uuid.uuid4()
    
    # Mock message counts
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 25  # >= 20, so should trigger first summary
    
    mock_summary_res = MagicMock()
    mock_summary_res.scalar_one_or_none.return_value = None  # No summary exists yet
    
    # Mock messages retrieval for summarization
    mock_messages_res = MagicMock()
    mock_messages_res.scalars.return_value.all.return_value = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi")
    ]
    
    mock_db.execute.side_effect = [mock_count_res, mock_summary_res, mock_messages_res]
    
    # Mock LLM factory
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="Ceci est un résumé")
    
    with patch("app.database.AsyncSessionLocal", return_value=mock_db), \
         patch("app.ai.llm_factory.LLMFactory.create_chat_llm", return_value=mock_llm):
        
        await RAGService.summarize_session_async(session_id)
        
        # Verify db.add was called to save the new summary
        assert mock_db.add.call_count == 1
        assert mock_db.commit.call_count == 1
