"""Document processing service."""
import logging
from pathlib import Path
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document, DocumentStatus
from app.utils.pdf_utils import PDFProcessor
from app.utils.text_utils import TextProcessor
from app.ai.vector_store import vector_store_manager
from app.ai.llm_factory import LLMFactory
from app.ai.prompts import get_summary_prompt
from app.config import settings
from app.config import settings

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document processing operations."""
    
    @staticmethod
    async def process_document(document_id: UUID, db: AsyncSession) -> None:
        """
        Process a document: extract text, create embeddings, generate summary.
        
        Args:
            document_id: Document UUID
            db: Database session
            
        Raises:
            Exception: If processing fails
        """
        try:
            # Get document from database
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                raise ValueError(f"Document {document_id} not found")
            
            logger.info(f"Processing document {document_id}: {document.title}")
            
            # Update status to processing
            document.status = DocumentStatus.PROCESSING
            await db.commit()
            
            # Step 1: Extract text from PDF
            is_url = document.filename.startswith("http://") or document.filename.startswith("https://")
            
            if is_url:
                logger.info(f"Downloading remote document from Supabase: {document.filename}")
                from app.services.storage_service import StorageService
                file_bytes = await StorageService.download_file(document.filename)
                
                # Save to a temporary local file
                temp_filename = f"temp_process_{document.id}.pdf"
                temp_path = Path(settings.UPLOADS_DIR) / temp_filename
                with open(temp_path, "wb") as f:
                    f.write(file_bytes)
                
                logger.info(f"Extracting text from downloaded temp PDF: {temp_path}")
                try:
                    text, page_count = PDFProcessor.extract_text_from_pdf(str(temp_path))
                finally:
                    # Always clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()
            else:
                logger.info(f"Extracting text from local PDF: {document.filename}")
                text, page_count = PDFProcessor.extract_text_from_pdf(document.filename)
            
            if not text or len(text.strip()) < 100:
                raise ValueError("Insufficient text extracted from PDF")
            
            # Update page count
            document.page_count = page_count
            await db.commit()
            
            # Step 2: Clean text
            logger.info("Cleaning extracted text")
            cleaned_text = TextProcessor.clean_text(text)
            cleaned_text = TextProcessor.remove_headers_footers(cleaned_text)
            
            # Step 3: Chunk text
            logger.info("Chunking text")
            chunks = TextProcessor.chunk_text(
                cleaned_text,
                chunk_size=1000,
                chunk_overlap=200
            )
            
            if not chunks:
                raise ValueError("No chunks created from text")
            
            # Step 4: Create vector store and embeddings
            logger.info(f"Creating embeddings for {len(chunks)} chunks")
            metadatas = [
                {
                    "chunk_index": i,
                    "document_id": str(document_id),
                    "page_count": page_count,
                }
                for i in range(len(chunks))
            ]
            
            collection_name = vector_store_manager.create_collection(
                document_id=document_id,
                documents=chunks,
                metadatas=metadatas
            )
            
            document.chroma_collection_id = collection_name
            await db.commit()
            
            # Step 5: Generate summary
            logger.info("Generating document summary")
            summary = await DocumentService._generate_summary(cleaned_text)
            
            document.summary = summary
            document.status = DocumentStatus.READY
            await db.commit()
            
            logger.info(f"Document {document_id} processed successfully")
            
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
            
            # Update status to error
            try:
                result = await db.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()
                if document:
                    document.status = DocumentStatus.ERROR
                    await db.commit()
            except Exception as db_error:
                logger.error(f"Error updating document status: {db_error}")
            
            raise
    
    @staticmethod
    async def _generate_summary(text: str, max_words: int = 500) -> str:
        """
        Generate a summary of the document text.
        
        Args:
            text: Document text
            max_words: Maximum words in summary
            
        Returns:
            str: Generated summary
        """
        try:
            # Truncate text if too long (to avoid token limits)
            max_chars = 15000
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
            
            # Create LLM and prompt
            llm = LLMFactory.create_summary_llm()
            prompt = get_summary_prompt()
            
            # Generate summary
            chain = prompt | llm
            response = await chain.ainvoke({
                "document_content": text
            })
            
            summary = response.content.strip()
            
            # Ensure summary is not too long
            if len(summary.split()) > max_words:
                summary = TextProcessor.truncate_text(summary, max_words * 6)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Résumé non disponible en raison d'une erreur de traitement."
    
    @staticmethod
    async def delete_document_files(document: Document) -> None:
        """
        Delete document files and vector store.
        
        Args:
            document: Document instance
        """
        try:
            # Delete physical file
            file_path = Path(document.filename)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {document.filename}")
            
            # Delete vector store collection
            if document.chroma_collection_id:
                vector_store_manager.delete_collection(document.id)
                logger.info(f"Deleted vector store for document {document.id}")
                
        except Exception as e:
            logger.error(f"Error deleting document files: {e}")
