import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.ai.embeddings import HuggingFaceEmbeddings
from app.ai.vector_store import VectorStoreManager, HuggingFaceReranker
from app.models.document_chunk import DocumentChunk


@pytest.mark.asyncio
async def test_hf_embeddings_embed_query():
    """Test embedding queries using mock Hugging Face API."""
    with patch("huggingface_hub.AsyncInferenceClient.feature_extraction") as mock_extract:
        mock_extract.return_value = [0.1] * 1024

        embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large", hf_token="mock-token")
        result = await embeddings.aembed_query("test query")

        assert len(result) == 1024
        assert result[0] == 0.1
        # Check passage prefix injection
        mock_extract.assert_called_once_with("query: test query")


@pytest.mark.asyncio
async def test_hf_embeddings_embed_documents():
    """Test embedding documents using mock Hugging Face API."""
    with patch("huggingface_hub.AsyncInferenceClient.feature_extraction") as mock_extract:
        mock_extract.return_value = [0.2] * 1024

        embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large", hf_token="mock-token")
        result = await embeddings.aembed_documents(["test document"])

        assert len(result) == 1
        assert len(result[0]) == 1024
        assert result[0][0] == 0.2
        # Check passage prefix injection
        mock_extract.assert_called_once_with("passage: test document")


@pytest.mark.asyncio
async def test_vector_store_create_collection():
    """Test adding chunks to pgvector database."""
    mock_db = AsyncMock()
    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_documents.return_value = [[0.3] * 1024]

    vector_store = VectorStoreManager(embeddings=mock_embeddings)
    
    document_id = uuid4()
    chunks = ["Chunk 1 content"]

    result = await vector_store.create_collection(mock_db, document_id, chunks)
    assert result == 1

    # Verify embeddings were generated
    mock_embeddings.aembed_documents.assert_called_once_with(["Chunk 1 content"])
    
    # Verify database insert
    mock_db.add.assert_called_once()
    added_chunk = mock_db.add.call_args[0][0]
    assert isinstance(added_chunk, DocumentChunk)
    assert added_chunk.document_id == document_id
    assert added_chunk.content == "Chunk 1 content"
    assert added_chunk.chunk_index == 0
    assert added_chunk.embedding == [0.3] * 1024
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_hf_reranker_rerank():
    """Test Hugging Face Reranker parsing API response formats."""
    with patch("httpx.AsyncClient.post") as mock_post:
        # Mock Response object
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            [{"label": "LABEL_0", "score": 0.95}],
            [{"label": "LABEL_0", "score": 0.12}]
        ]
        mock_post.return_value = mock_response

        reranker = HuggingFaceReranker(model_name="BAAI/bge-reranker-large", hf_token="mock-token")
        results = await reranker.rerank("query text", ["doc1", "doc2"])

        assert len(results) == 2
        assert results[0] == {"index": 0, "score": 0.95}
        assert results[1] == {"index": 1, "score": 0.12}


@pytest.mark.asyncio
async def test_similarity_search_fallback():
    """Test that similarity search returns an empty list when no relevant chunks are found (no fallback)."""
    mock_db = AsyncMock()
    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_query.return_value = [0.1] * 1024

    mock_first_res = MagicMock()
    mock_first_res.all.return_value = [] # Empty results
    
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: None), # doc query
        mock_first_res # similarity search query (returns empty)
    ]

    vector_store = VectorStoreManager(embeddings=mock_embeddings)
    doc_id = uuid4()
    
    results = await vector_store.similarity_search(mock_db, doc_id, "What is NLP?", k=5)
    
    assert results == []


@pytest.mark.asyncio
async def test_hf_embeddings_validation_failures():
    """Test that validation fails for invalid embeddings (zeros, short, NaN)."""
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large", hf_token="mock-token")
    
    # 1. Zeros vector
    with patch("huggingface_hub.AsyncInferenceClient.feature_extraction", return_value=[0.0] * 1024):
        with pytest.raises(ValueError, match="all values are 0.0"):
            await embeddings.aembed_query("test query")
            
    # 2. Too short vector
    with patch("huggingface_hub.AsyncInferenceClient.feature_extraction", return_value=[0.1] * 50):
        with pytest.raises(ValueError, match="dimension is too short"):
            await embeddings.aembed_query("test query")
            
    # 3. NaN vector
    with patch("huggingface_hub.AsyncInferenceClient.feature_extraction", return_value=[float('nan')] * 1024):
        with pytest.raises(ValueError, match="contains NaN values"):
            await embeddings.aembed_query("test query")


@pytest.mark.asyncio
async def test_hf_embeddings_exception_propagation():
    """Test that API exceptions propagate and are not swallowed."""
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large", hf_token="mock-token")
    
    with patch("huggingface_hub.AsyncInferenceClient.feature_extraction", side_effect=RuntimeError("API error")):
        with pytest.raises(RuntimeError, match="API error"):
            await embeddings.aembed_query("test query")


@pytest.mark.asyncio
async def test_hf_embeddings_retry_success():
    """Test that transient connection errors are successfully retried."""
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large", hf_token="mock-token")
    import httpx
    
    with patch("huggingface_hub.AsyncInferenceClient.feature_extraction") as mock_extract:
        # 1st call raises ConnectError, 2nd call returns valid embedding
        mock_extract.side_effect = [
            httpx.ConnectError("Connection failed"),
            [0.1] * 1024
        ]
        
        # Patch sleep to make test run fast
        with patch("asyncio.sleep", return_value=None):
            result = await embeddings.aembed_query("test query")
            
            assert len(result) == 1024
            assert mock_extract.call_count == 2


@pytest.mark.asyncio
async def test_hf_embeddings_timeout_failure():
    """Test that timeout exception is raised after all retries fail."""
    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large", hf_token="mock-token")
    import httpx
    
    with patch("huggingface_hub.AsyncInferenceClient.feature_extraction") as mock_extract:
        mock_extract.side_effect = httpx.TimeoutException("Request timed out")
        
        with patch("asyncio.sleep", return_value=None):
            with pytest.raises(httpx.TimeoutException):
                await embeddings.aembed_query("test query")
            
            assert mock_extract.call_count == 3


@pytest.mark.asyncio
async def test_similarity_search_sql_ilike_fallback():
    """Test that similarity search falls back to SQL ILIKE search when embeddings fail."""
    mock_db = AsyncMock()
    mock_embeddings = AsyncMock()
    import httpx
    mock_embeddings.aembed_query.side_effect = httpx.ConnectError("HuggingFace is offline")
    
    # Mock Document query return
    mock_doc = MagicMock()
    mock_doc.filename = "test_doc.pdf"
    
    # Mock SQL ILIKE query result
    mock_chunk = DocumentChunk(
        id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        content="This is matching text from the fallback keyword search",
        embedding=[0.1] * 1024,
        page_number=1
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_chunk]
    
    # Mock db.execute side effect for doc fetch, then chunk fetch
    mock_db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: mock_doc),
        mock_result
    ]
    
    vector_store = VectorStoreManager(embeddings=mock_embeddings)
    doc_id = uuid4()
    
    results = await vector_store.similarity_search(mock_db, doc_id, "matching text", k=5)
    
    # Verify we got fallback results with score 0.85
    assert len(results) == 1
    assert results[0].page_content == "This is matching text from the fallback keyword search"
    assert results[0].metadata["score"] == 0.85

