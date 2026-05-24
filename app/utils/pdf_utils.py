"""PDF processing utilities using PyMuPDF."""
import logging
from pathlib import Path
from typing import List, Tuple
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFProcessor:
    """PDF processing utilities."""
    
    @staticmethod
    def extract_text_from_pdf(pdf_path: str) -> Tuple[str, int]:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            tuple: (extracted_text, page_count)
            
        Raises:
            Exception: If PDF cannot be opened or processed
        """
        try:
            doc = fitz.open(pdf_path)
            text_parts = []
            page_count = len(doc)
            
            for page_num in range(page_count):
                page = doc[page_num]
                text = page.get_text()
                
                if text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
            
            doc.close()
            
            full_text = "\n\n".join(text_parts)
            logger.info(f"Extracted {len(full_text)} characters from {page_count} pages")
            
            return full_text, page_count
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
            raise
    
    @staticmethod
    def extract_text_by_pages(pdf_path: str) -> List[Tuple[int, str]]:
        """
        Extract text from PDF page by page.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            list: List of (page_number, text) tuples
            
        Raises:
            Exception: If PDF cannot be opened or processed
        """
        try:
            doc = fitz.open(pdf_path)
            pages = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                pages.append((page_num + 1, text))
            
            doc.close()
            
            logger.info(f"Extracted text from {len(pages)} pages")
            return pages
            
        except Exception as e:
            logger.error(f"Error extracting pages from PDF {pdf_path}: {e}")
            raise
    
    @staticmethod
    def get_pdf_metadata(pdf_path: str) -> dict:
        """
        Get PDF metadata.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            dict: PDF metadata
        """
        try:
            doc = fitz.open(pdf_path)
            metadata = {
                "page_count": len(doc),
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "creator": doc.metadata.get("creator", ""),
                "producer": doc.metadata.get("producer", ""),
            }
            doc.close()
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting PDF metadata from {pdf_path}: {e}")
            return {"page_count": 0}
    
    @staticmethod
    def validate_pdf(pdf_path: str) -> bool:
        """
        Validate if file is a valid PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            bool: True if valid PDF
        """
        try:
            doc = fitz.open(pdf_path)
            is_valid = len(doc) > 0
            doc.close()
            return is_valid
        except Exception as e:
            logger.warning(f"PDF validation failed for {pdf_path}: {e}")
            return False
