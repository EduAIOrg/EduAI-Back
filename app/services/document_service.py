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
            
            # Step 1: Extract text page by page
            is_url = document.filename.startswith("http://") or document.filename.startswith("https://")
            pdf_path = None
            
            if is_url:
                logger.info(f"Downloading remote document from Supabase: {document.filename}")
                from app.services.storage_service import StorageService
                file_bytes = await StorageService.download_file(document.filename)
                
                # Save to a temporary local file
                temp_filename = f"temp_process_{document.id}.pdf"
                temp_path = Path(settings.UPLOADS_DIR) / temp_filename
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                with open(temp_path, "wb") as f:
                    f.write(file_bytes)
                pdf_path = str(temp_path)
            else:
                logger.info(f"Using local PDF: {document.filename}")
                pdf_path = document.filename
            
            try:
                pages_data = PDFProcessor.extract_text_by_pages(pdf_path)
                page_count = len(pages_data)
            finally:
                # Always clean up temp file
                if is_url and pdf_path and Path(pdf_path).exists():
                    Path(pdf_path).unlink()
            
            if not pages_data:
                raise ValueError("Insufficient text extracted from PDF")
            
            # Update page count
            document.page_count = page_count
            await db.commit()
            
            # Step 2: Clean and chunk text page by page to keep track of page numbers
            logger.info("Cleaning and chunking text page by page")
            chunks = []
            metadatas = []
            full_text_list = []
            
            chunk_idx = 0
            for page_num, page_text in pages_data:
                if not page_text or len(page_text.strip()) < 5:
                    continue
                full_text_list.append(page_text)
                cleaned_page = TextProcessor.clean_text(page_text)
                cleaned_page = TextProcessor.remove_headers_footers(cleaned_page)
                
                page_chunks = TextProcessor.chunk_text(
                    cleaned_page,
                    chunk_size=1200,
                    chunk_overlap=200
                )
                for chunk in page_chunks:
                    chunks.append(chunk)
                    metadatas.append({
                        "chunk_index": chunk_idx,
                        "document_id": str(document_id),
                        "page_number": page_num
                    })
                    chunk_idx += 1
            
            if not chunks:
                raise ValueError("No chunks created from text")
            
            logger.info(
                f"CONTEXT DEBUG | Upload & processing successful for document_id={document_id} | "
                f"number of pages={page_count} | number of chunks generated={len(chunks)}"
            )
            
            # Step 4: Create vector store and embeddings
            logger.info(f"Creating embeddings for {len(chunks)} chunks")
            await vector_store_manager.create_collection(
                db=db,
                document_id=document_id,
                documents=chunks,
                metadatas=metadatas
            )
            await db.commit()
            
            # Step 5: Generate summary
            logger.info("Generating document summary")
            # Combine the pages for summary generation
            combined_cleaned_text = TextProcessor.clean_text("\n\n".join(full_text_list))
            summary = await DocumentService._generate_summary(combined_cleaned_text)
            
            document.summary = summary
            document.status = DocumentStatus.READY
            await db.commit()
            
            logger.info(f"Document {document_id} processed successfully")
            
            try:
                from app.services.notification_service import NotificationService
                await NotificationService.create_notification(
                    db=db,
                    user_id=document.user_id,
                    title="Document analysé",
                    message=f"L'analyse du document '{document.title}' s'est terminée avec succès.",
                    type="document"
                )
                await NotificationService.create_notification(
                    db=db,
                    user_id=document.user_id,
                    title="Résumé généré",
                    message=f"Le résumé pour le document '{document.title}' a été généré avec succès.",
                    type="ia"
                )
            except Exception as notify_err:
                logger.error(f"Failed to create document notification: {notify_err}")
            
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
    async def delete_document_files(document: Document, db: AsyncSession) -> None:
        """
        Delete document files and vector store.
        
        Args:
            document: Document instance
            db: Database session
        """
        try:
            # Delete physical file
            file_path = Path(document.filename)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {document.filename}")
            
            # Delete vector store collection
            await vector_store_manager.delete_collection(db, document.id)
            logger.info(f"Deleted vector store for document {document.id}")
                
        except Exception as e:
            logger.error(f"Error deleting document files: {e}")
