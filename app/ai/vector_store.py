"""ChromaDB vector store management."""
import logging
from pathlib import Path
from typing import List, Optional
from uuid import UUID
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from app.config import settings
from app.ai.embeddings import EmbeddingsFactory

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manager for ChromaDB vector store operations."""
    
    def __init__(self):
        """Initialize ChromaDB client."""
        # Ensure chroma_db directory exists
        chroma_path = Path(settings.CHROMA_DB_DIR)
        chroma_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize persistent client
        self.client = chromadb.PersistentClient(
            path=str(chroma_path),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )
        
        # Initialize embeddings
        self.embeddings = EmbeddingsFactory.create_embeddings()
        
        logger.info(f"ChromaDB initialized at {chroma_path}")
    
    def get_collection_name(self, document_id: UUID) -> str:
        """
        Get collection name for a document.
        
        Args:
            document_id: Document UUID
            
        Returns:
            str: Collection name
        """
        return f"doc_{str(document_id).replace('-', '_')}"
    
    def create_collection(
        self,
        document_id: UUID,
        documents: List[str],
        metadatas: Optional[List[dict]] = None
    ) -> str:
        """
        Create a new collection and add documents.
        
        Args:
            document_id: Document UUID
            documents: List of text chunks
            metadatas: Optional list of metadata dicts
            
        Returns:
            str: Collection name
        """
        collection_name = self.get_collection_name(document_id)
        
        try:
            # Create Document objects for LangChain
            docs = [
                Document(
                    page_content=text,
                    metadata=metadatas[i] if metadatas else {"chunk_index": i}
                )
                for i, text in enumerate(documents)
            ]
            
            # Create Chroma vector store
            vectorstore = Chroma.from_documents(
                documents=docs,
                embedding=self.embeddings,
                collection_name=collection_name,
                client=self.client,
            )
            
            logger.info(f"Created collection {collection_name} with {len(documents)} documents")
            return collection_name
            
        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {e}")
            raise
    
    def get_vectorstore(self, document_id: UUID) -> Optional[Chroma]:
        """
        Get existing vector store for a document.
        
        Args:
            document_id: Document UUID
            
        Returns:
            Chroma: Vector store instance or None if not found
        """
        collection_name = self.get_collection_name(document_id)
        
        try:
            # Check if collection exists
            collections = self.client.list_collections()
            collection_names = [col.name for col in collections]
            
            if collection_name not in collection_names:
                logger.warning(f"Collection {collection_name} not found")
                return None
            
            # Get existing vector store
            vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=self.embeddings,
                client=self.client,
            )
            
            return vectorstore
            
        except Exception as e:
            logger.error(f"Error getting vector store {collection_name}: {e}")
            return None
    
    def similarity_search(
        self,
        document_id: UUID,
        query: str,
        k: int = 5
    ) -> List[Document]:
        """
        Perform similarity search in a document's collection.
        
        Args:
            document_id: Document UUID
            query: Search query
            k: Number of results to return
            
        Returns:
            list: List of Document objects
        """
        vectorstore = self.get_vectorstore(document_id)
        
        if not vectorstore:
            logger.warning(f"Vector store not found for document {document_id}")
            return []
        
        try:
            results = vectorstore.similarity_search(query, k=k)
            logger.info(f"Found {len(results)} similar documents for query")
            return results
            
        except Exception as e:
            logger.error(f"Error performing similarity search: {e}")
            return []
    
    def delete_collection(self, document_id: UUID) -> bool:
        """
        Delete a document's collection.
        
        Args:
            document_id: Document UUID
            
        Returns:
            bool: True if deleted successfully
        """
        collection_name = self.get_collection_name(document_id)
        
        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}")
            return False
    
    def get_random_chunks(
        self,
        document_id: UUID,
        n: int = 10
    ) -> List[str]:
        """
        Get random chunks from a document's collection.
        
        Args:
            document_id: Document UUID
            n: Number of chunks to retrieve
            
        Returns:
            list: List of text chunks
        """
        vectorstore = self.get_vectorstore(document_id)
        
        if not vectorstore:
            logger.warning(f"Vector store not found for document {document_id}")
            return []
        
        try:
            collection_name = self.get_collection_name(document_id)
            collection = self.client.get_collection(name=collection_name)
            
            # Get all documents
            results = collection.get()
            
            if not results or not results.get("documents"):
                return []
            
            documents = results["documents"]
            
            # Return up to n documents
            import random
            if len(documents) <= n:
                return documents
            
            return random.sample(documents, n)
            
        except Exception as e:
            logger.error(f"Error getting random chunks: {e}")
            return []


# Global vector store manager instance
vector_store_manager = VectorStoreManager()
