"""Celery tasks for document processing."""
import logging
from uuid import UUID
from celery import Task
from sqlalchemy import select

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.document import Document, DocumentStatus
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)


class DocumentProcessingTask(Task):
    """Base task for document processing with error handling."""
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


@celery_app.task(bind=True, base=DocumentProcessingTask, name="process_document")
def process_document_task(self, document_id: str) -> dict:
    """
    Process a document: extract text, create embeddings, generate summary.
    
    Args:
        document_id: Document UUID as string
        
    Returns:
        dict: Processing result
    """
    import asyncio
    
    logger.info(f"Starting document processing task for {document_id}")
    
    try:
        # Convert string to UUID
        doc_uuid = UUID(document_id)
        
        # Run async processing
        result = asyncio.run(_process_document_async(doc_uuid))
        
        logger.info(f"Document processing completed for {document_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in document processing task: {e}")
        
        # Update document status to error
        asyncio.run(_update_document_status(document_id, DocumentStatus.ERROR))
        
        raise


async def _process_document_async(document_id: UUID) -> dict:
    """
    Async wrapper for document processing.
    
    Args:
        document_id: Document UUID
        
    Returns:
        dict: Processing result
    """
    async with AsyncSessionLocal() as db:
        try:
            await DocumentService.process_document(document_id, db)
            
            return {
                "status": "success",
                "document_id": str(document_id),
                "message": "Document processed successfully"
            }
            
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
            raise


async def _update_document_status(document_id: str, status: DocumentStatus) -> None:
    """
    Update document status in database.
    
    Args:
        document_id: Document UUID as string
        status: New status
    """
    try:
        doc_uuid = UUID(document_id)
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Document).where(Document.id == doc_uuid)
            )
            document = result.scalar_one_or_none()
            
            if document:
                document.status = status
                await db.commit()
                logger.info(f"Updated document {document_id} status to {status}")
                
    except Exception as e:
        logger.error(f"Error updating document status: {e}")
