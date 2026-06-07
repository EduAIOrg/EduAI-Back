"""Documents router."""
import logging
import os
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.document import Document, DocumentStatus
from app.schemas.document import (
    DocumentResponse,
    DocumentStatusResponse,
    DocumentSummaryResponse
)
from app.services.document_service import DocumentService
from app.config import settings
from app.utils.pdf_utils import PDFProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[DocumentResponse]:
    """
    List all documents for the current user.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        list: List of user's documents
    """
    try:
        result = await db.execute(
            select(Document)
            .where(Document.user_id == current_user.id)
            .order_by(Document.created_at.desc())
        )
        documents = result.scalars().all()
        
        return [DocumentResponse.model_validate(doc) for doc in documents]
        
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents"
        )


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> DocumentResponse:
    """
    Upload a new PDF document.
    
    Args:
        file: PDF file to upload
        title: Optional document title
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        DocumentResponse: Created document
        
    Raises:
        HTTPException: If file is invalid or upload fails
    """
    try:
        from app.services.quota_service import QuotaService
        if not await QuotaService.check_quota(db, current_user, "upload"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Quota journalier de téléchargement de documents dépassé pour votre forfait."
            )

        # Validate file type
        if not file.content_type == "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed"
            )
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Calculate SHA256 hash of document content
        import hashlib
        doc_hash = hashlib.sha256(content).hexdigest()
        
        # Check for duplicates in database
        dup_stmt = select(Document).where(Document.document_hash == doc_hash)
        dup_res = await db.execute(dup_stmt)
        existing_doc = dup_res.scalars().first()
        
        if existing_doc:
            if existing_doc.user_id == current_user.id:
                logger.info(f"Duplicate document found for same user: {existing_doc.id}")
                return DocumentResponse.model_validate(existing_doc)
            else:
                logger.info(f"Global duplicate document found. Copying metadata and chunks from {existing_doc.id}")
                # Increment upload usage count since they are adding a document to their dashboard
                await QuotaService.increment_usage(db, current_user.id, "upload")
                # Create a new document entry referencing the existing filename
                document = Document(
                    user_id=current_user.id,
                    title=title if title else Path(file.filename).stem,
                    filename=existing_doc.filename,
                    file_size=file_size,
                    page_count=existing_doc.page_count,
                    status=existing_doc.status,
                    summary=existing_doc.summary,
                    document_hash=doc_hash
                )
                db.add(document)
                await db.commit()
                await db.refresh(document)
                
                try:
                    from app.services.notification_service import NotificationService
                    await NotificationService.create_notification(
                        db=db,
                        user_id=current_user.id,
                        title="Document importé",
                        message=f"Le document '{document.title}' a été importé avec succès.",
                        type="document"
                    )
                except Exception as notify_err:
                    logger.error(f"Failed to create notification: {notify_err}")
                
                # Copy document chunks for the new user if original is ready
                if existing_doc.status == DocumentStatus.READY:
                    from app.models.document_chunk import DocumentChunk
                    chunks_stmt = select(DocumentChunk).where(DocumentChunk.document_id == existing_doc.id)
                    chunks_res = await db.execute(chunks_stmt)
                    existing_chunks = chunks_res.scalars().all()
                    
                    for ec in existing_chunks:
                        nc = DocumentChunk(
                            document_id=document.id,
                            chunk_index=ec.chunk_index,
                            page_number=ec.page_number,
                            content=ec.content,
                            embedding=ec.embedding
                        )
                        db.add(nc)
                    await db.commit()
                else:
                    # If original is not ready, schedule task to process
                    await DocumentService.process_document(document.id, db)
                    
                return DocumentResponse.model_validate(document)
        
        # Validate file size
        if file_size > settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum of {settings.MAX_UPLOAD_SIZE_MB}MB"
            )
        
        # Check if Supabase storage is configured
        from app.services.storage_service import StorageService
        
        file_id = uuid.uuid4()
        file_extension = Path(file.filename).suffix
        
        if StorageService.is_configured():
            # Validate PDF by writing to a temporary file
            temp_path = Path(settings.UPLOADS_DIR) / f"temp_{file_id}{file_extension}"
            with open(temp_path, "wb") as f:
                f.write(content)
            
            if not PDFProcessor.validate_pdf(str(temp_path)):
                temp_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid PDF file"
                )
            temp_path.unlink()
            
            # Upload to Supabase
            try:
                cloud_url = await StorageService.upload_file(
                    user_id=current_user.id,
                    file_id=file_id,
                    content=content,
                    content_type="application/pdf"
                )
                filename_path = cloud_url
            except Exception as e:
                logger.error(f"Failed to upload to Supabase: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload to cloud storage: {e}"
                )
        else:
            # Create user upload directory
            user_upload_dir = Path(settings.UPLOADS_DIR) / str(current_user.id)
            user_upload_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{file_id}{file_extension}"
            file_path = user_upload_dir / filename
            
            # Save file
            with open(file_path, "wb") as f:
                f.write(content)
            
            logger.info(f"Saved file locally: {file_path}")
            
            # Validate PDF
            if not PDFProcessor.validate_pdf(str(file_path)):
                file_path.unlink()  # Delete invalid file
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid PDF file"
                )
            filename_path = str(file_path)
        
        # Use provided title or filename
        doc_title = title if title else Path(file.filename).stem
        
        # Create document record
        document = Document(
            user_id=current_user.id,
            title=doc_title,
            filename=filename_path,
            file_size=file_size,
            status=DocumentStatus.UPLOADING,
            document_hash=doc_hash
        )
        
        db.add(document)
        await db.commit()
        await db.refresh(document)
        
        try:
            from app.services.notification_service import NotificationService
            await NotificationService.create_notification(
                db=db,
                user_id=current_user.id,
                title="Document importé",
                message=f"Le document '{document.title}' a été importé avec succès.",
                type="document"
            )
        except Exception as notify_err:
            logger.error(f"Failed to create notification: {notify_err}")
        
        # Log quota usage
        from app.services.quota_service import QuotaService
        await QuotaService.increment_usage(db, current_user.id, "upload")
        
        # Launch async processing task
        await DocumentService.process_document(document.id, db)
        
        logger.info(f"Document created: {document.id}")
        
        return DocumentResponse.model_validate(document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> DocumentResponse:
    """
    Get a specific document.
    
    Args:
        document_id: Document UUID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        DocumentResponse: Document details
        
    Raises:
        HTTPException: If document not found or access denied
    """
    try:
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Check ownership
        if document.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Temporary diagnostic logging
        logger.info(f"Document path: {document.filename}")
        is_url = document.filename.startswith("http://") or document.filename.startswith("https://")
        logger.info(f"Exists: {True if is_url else Path(document.filename).exists()}")
        
        return DocumentResponse.model_validate(document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document"
        )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> DocumentStatusResponse:
    """
    Get document processing status.
    
    Args:
        document_id: Document UUID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        DocumentStatusResponse: Processing status
    """
    try:
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        
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
        
        # Generate progress message
        progress_messages = {
            DocumentStatus.UPLOADING: "Téléchargement en cours...",
            DocumentStatus.PROCESSING: "Traitement du document en cours...",
            DocumentStatus.READY: "Document prêt",
            DocumentStatus.ERROR: "Erreur lors du traitement"
        }
        
        return DocumentStatusResponse(
            status=document.status,
            progress_message=progress_messages.get(
                document.status,
                "Statut inconnu"
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document status"
        )


@router.get("/{document_id}/summary", response_model=DocumentSummaryResponse)
async def get_document_summary(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> DocumentSummaryResponse:
    """
    Get document summary.
    
    Args:
        document_id: Document UUID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        DocumentSummaryResponse: Document summary
    """
    try:
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        
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
        
        return DocumentSummaryResponse(
            summary=document.summary,
            status=document.status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document summary"
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a document.
    
    Args:
        document_id: Document UUID
        current_user: Current authenticated user
        db: Database session
        
    Raises:
        HTTPException: If document not found or access denied
    """
    try:
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        
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
        
        # Delete files and vector store
        await DocumentService.delete_document_files(document, db)
        
        # Delete database record
        doc_title = document.title
        await db.delete(document)
        await db.commit()
        
        try:
            from app.services.notification_service import NotificationService
            await NotificationService.create_notification(
                db=db,
                user_id=current_user.id,
                title="Document supprimé",
                message=f"Le document '{doc_title}' a été supprimé.",
                type="document"
            )
        except Exception as notify_err:
            logger.error(f"Failed to create notification: {notify_err}")
            
        logger.info(f"Document deleted: {document_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )
