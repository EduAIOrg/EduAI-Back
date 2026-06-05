import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.ai.vector_store import VectorStoreManager
from app.models.document import Document
from app.models.document_chunk import DocumentChunk


@pytest.mark.asyncio
async def test_relevance_project_name():
    """Test retrieving chunk containing 'EduAI Africa' for project name question."""
    mock_db = AsyncMock()
    
    # Mock doc query
    mock_doc = Document(id=uuid4(), filename="eduai_project.pdf")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    
    # Mock chunks return
    chunk1 = DocumentChunk(
        id=uuid4(),
        document_id=mock_doc.id,
        chunk_index=0,
        content="Le projet est nommé EduAI Africa. C'est une plateforme d'intelligence artificielle.",
        embedding=[0.1] * 1024,
        page_number=1
    )
    chunk2 = DocumentChunk(
        id=uuid4(),
        document_id=mock_doc.id,
        chunk_index=1,
        content="Ceci est un autre paragraphe sans importance.",
        embedding=[0.1] * 1024,
        page_number=1
    )
    
    # Mock db.execute to return chunks with similarity score (cosine distance)
    # Cosine distance for chunk1 is lower (closer/more similar), e.g. 0.2 (score = 0.8)
    # Cosine distance for chunk2 is higher, e.g. 0.8 (score = 0.2)
    mock_result.all.return_value = [
        (chunk1, 0.2),  # distance=0.2 => score=0.8
        (chunk2, 0.8)   # distance=0.8 => score=0.2
    ]
    mock_db.execute.return_value = mock_result
    
    # Mock embeddings
    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_query.return_value = [0.1] * 1024
    
    # Vector store manager
    vector_store = VectorStoreManager(embeddings=mock_embeddings)
    
    # Disable reranking to focus on vector similarity
    with patch.object(vector_store.reranker, "rerank", return_value=[]):
        results = await vector_store.similarity_search(
            db=mock_db,
            document_id=mock_doc.id,
            query="Quel est le nom du projet ?",
            k=2
        )
        
        # Verify result contains "EduAI Africa"
        assert len(results) > 0
        assert "EduAI Africa" in results[0].page_content


@pytest.mark.asyncio
async def test_relevance_project_context():
    """Test retrieving chunk containing context details for context question."""
    mock_db = AsyncMock()
    mock_doc = Document(id=uuid4(), filename="eduai_project.pdf")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=mock_doc.id,
        chunk_index=0,
        content="Le projet vise à offrir un accès à des outils éducatifs intelligents pour l'Afrique.",
        embedding=[0.1] * 1024,
        page_number=1
    )
    
    mock_result.all.return_value = [
        (chunk, 0.2)  # score=0.8
    ]
    mock_db.execute.return_value = mock_result
    
    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_query.return_value = [0.1] * 1024
    
    vector_store = VectorStoreManager(embeddings=mock_embeddings)
    
    with patch.object(vector_store.reranker, "rerank", return_value=[]):
        results = await vector_store.similarity_search(
            db=mock_db,
            document_id=mock_doc.id,
            query="Quel est le contexte du projet ?",
            k=1
        )
        
        assert len(results) > 0
        assert "accès à des outils éducatifs intelligents" in results[0].page_content


@pytest.mark.asyncio
async def test_relevance_project_features():
    """Test retrieving chunk containing main features section."""
    mock_db = AsyncMock()
    mock_doc = Document(id=uuid4(), filename="eduai_project.pdf")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=mock_doc.id,
        chunk_index=0,
        content="Les fonctionnalités principales du projet incluent la Gestion des Documents PDF, le Chat IA, la génération de Quiz et la Traduction.",
        embedding=[0.1] * 1024,
        page_number=1
    )
    
    mock_result.all.return_value = [
        (chunk, 0.2)  # score=0.8
    ]
    mock_db.execute.return_value = mock_result
    
    mock_embeddings = AsyncMock()
    mock_embeddings.aembed_query.return_value = [0.1] * 1024
    
    vector_store = VectorStoreManager(embeddings=mock_embeddings)
    
    with patch.object(vector_store.reranker, "rerank", return_value=[]):
        results = await vector_store.similarity_search(
            db=mock_db,
            document_id=mock_doc.id,
            query="Quelles sont les fonctionnalités principales ?",
            k=1
        )
        
        assert len(results) > 0
        content = results[0].page_content
        assert "Gestion des Documents PDF" in content
        assert "Chat IA" in content
        assert "Quiz" in content
        assert "Traduction" in content


from app.services.rag_service import RAGService
from langchain_core.messages import AIMessage

@pytest.mark.asyncio
async def test_rag_low_score_blocking():
    """Test that query_document blocks generation when the context score is below 0.80."""
    mock_db = AsyncMock()
    doc_id = uuid4()
    
    # Mock retrieve_context to return low score (0.75)
    mock_sources = [{"score": 0.75, "document": "doc.pdf", "page": 1, "content": "Some context"}]
    with patch("app.services.rag_service.retrieve_context", return_value=("Some context", mock_sources, 0.75)):
        generator = RAGService.query_document(
            db=mock_db,
            question="What is the answer?",
            document_id=doc_id,
            conversation_history=[],
            stream=False
        )
        
        results = []
        async for chunk in generator:
            results.append(chunk)
            
        assert len(results) == 2
        assert results[0] == {"sources": mock_sources}
        assert results[1] == "Cette information n'est pas présente dans le document fourni."


from langchain_core.language_models.chat_models import SimpleChatModel

class FakeVerificationLLM(SimpleChatModel):
    response: str = "NO"
    
    def _call(self, messages, stop=None, run_manager=None, **kwargs):
        return self.response
        
    async def _acall(self, messages, stop=None, run_manager=None, **kwargs):
        return self.response
        
    @property
    def _llm_type(self) -> str:
        return "fake-verifier"


@pytest.mark.asyncio
async def test_rag_verification_no_blocking():
    """Test that query_document blocks generation when LLM verification returns NO."""
    mock_db = AsyncMock()
    doc_id = uuid4()
    
    # Mock retrieve_context to return high score (0.85)
    mock_sources = [{"score": 0.85, "document": "doc.pdf", "page": 1, "content": "Some context"}]
    
    fake_llm = FakeVerificationLLM(response="NO")
    
    with patch("app.services.rag_service.retrieve_context", return_value=("Some context", mock_sources, 0.85)), \
         patch("app.ai.llm_factory.LLMFactory.create_chat_llm", return_value=fake_llm):
         
        generator = RAGService.query_document(
            db=mock_db,
            question="What is the answer?",
            document_id=doc_id,
            conversation_history=[],
            stream=False
        )
        
        results = []
        async for chunk in generator:
            results.append(chunk)
            
        assert len(results) == 2
        assert results[0] == {"sources": mock_sources}
        assert results[1] == "Cette information n'est pas présente dans le document fourni."

