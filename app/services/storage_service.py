import logging
from uuid import UUID
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

class StorageService:
    """Service for interacting with Supabase Storage via HTTP REST API."""

    @staticmethod
    def is_configured() -> bool:
        """Check if Supabase is properly configured in the settings."""
        return bool(settings.SUPABASE_URL and settings.SUPABASE_KEY)

    @staticmethod
    async def upload_file(
        user_id: UUID,
        file_id: UUID,
        content: bytes,
        content_type: str = "application/pdf"
    ) -> str:
        """
        Upload file content to Supabase Storage.
        
        Args:
            user_id: Owner user UUID
            file_id: Document file UUID
            content: File bytes
            content_type: MIME type of the file
            
        Returns:
            str: Publicly accessible download URL of the uploaded document.
            
        Raises:
            Exception: If the upload fails or credentials are missing.
        """
        if not StorageService.is_configured():
            raise ValueError("Supabase storage is not configured (missing URL or KEY).")

        bucket = settings.SUPABASE_BUCKET
        file_path = f"{user_id}/{file_id}.pdf"
        
        # Prepare Supabase REST API URL
        upload_url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{bucket}/{file_path}"
        
        headers = {
            "Authorization": f"Bearer {settings.SUPABASE_KEY}",
            "Content-Type": content_type
        }
        
        logger.info(f"Uploading file {file_path} to Supabase bucket '{bucket}'...")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(upload_url, content=content, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Supabase upload failed: {response.status_code} - {response.text}")
                raise RuntimeError(f"Failed to upload file to Supabase: {response.text}")
                
            logger.info(f"Successfully uploaded {file_path} to Supabase.")
            
            # Construct public download URL
            public_url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{bucket}/{file_path}"
            return public_url

    @staticmethod
    async def download_file(file_url: str) -> bytes:
        """
        Download file content from a Supabase Storage public URL.
        
        Args:
            file_url: Full public URL of the file
            
        Returns:
            bytes: File content
            
        Raises:
            Exception: If download fails
        """
        logger.info(f"Downloading file from URL: {file_url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(file_url)
            
            if response.status_code != 200:
                logger.error(f"Failed to download file: {response.status_code} - {response.text}")
                raise RuntimeError(f"Failed to download file from URL: {response.text}")
                
            return response.content

    @staticmethod
    async def delete_file(file_url: str) -> None:
        """
        Delete a file from Supabase Storage based on its public URL.
        
        Args:
            file_url: Full public URL of the file
            
        Raises:
            Exception: If deletion fails
        """
        if not StorageService.is_configured():
            logger.warning("Supabase storage not configured; skipping deletion from cloud.")
            return

        # Parse file path from public URL
        # Format: {supabase_url}/storage/v1/object/public/{bucket}/{user_id}/{file_id}.pdf
        bucket = settings.SUPABASE_BUCKET
        public_prefix = f"/storage/v1/object/public/{bucket}/"
        
        if public_prefix not in file_url:
            logger.warning(f"URL '{file_url}' does not look like a Supabase URL, skipping storage deletion.")
            return
            
        file_path = file_url.split(public_prefix)[-1]
        delete_url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{bucket}/{file_path}"
        
        headers = {
            "Authorization": f"Bearer {settings.SUPABASE_KEY}"
        }
        
        logger.info(f"Deleting file {file_path} from Supabase bucket '{bucket}'...")
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(delete_url, headers=headers)
            
            if response.status_code not in [200, 204]:
                logger.error(f"Failed to delete file from Supabase: {response.status_code} - {response.text}")
            else:
                logger.info(f"Successfully deleted {file_path} from Supabase.")
