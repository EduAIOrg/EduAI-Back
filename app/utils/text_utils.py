"""Text processing utilities."""
import re
import logging
from typing import List

logger = logging.getLogger(__name__)


class TextProcessor:
    """Text processing utilities."""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean extracted text by removing excessive whitespace and artifacts.
        
        Args:
            text: Raw text
            
        Returns:
            str: Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers (common patterns)
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    @staticmethod
    def remove_headers_footers(text: str, threshold: int = 3) -> str:
        """
        Remove repetitive headers and footers.
        
        Args:
            text: Text to process
            threshold: Minimum number of repetitions to consider as header/footer
            
        Returns:
            str: Text with headers/footers removed
        """
        lines = text.split('\n')
        
        # Count line occurrences
        line_counts = {}
        for line in lines:
            stripped = line.strip()
            if stripped and len(stripped) < 100:  # Only consider short lines
                line_counts[stripped] = line_counts.get(stripped, 0) + 1
        
        # Identify repetitive lines
        repetitive_lines = {
            line for line, count in line_counts.items()
            if count >= threshold
        }
        
        # Filter out repetitive lines
        filtered_lines = [
            line for line in lines
            if line.strip() not in repetitive_lines
        ]
        
        return '\n'.join(filtered_lines)
    
    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to chunk
            chunk_size: Maximum chunk size in characters
            chunk_overlap: Overlap between chunks
            
        Returns:
            list: List of text chunks
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < text_length:
                # Look for sentence ending punctuation
                for punct in ['. ', '! ', '? ', '\n\n']:
                    last_punct = text.rfind(punct, start, end)
                    if last_punct != -1:
                        end = last_punct + len(punct)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = end - chunk_overlap if end < text_length else text_length
        
        logger.info(f"Split text into {len(chunks)} chunks")
        return chunks
    
    @staticmethod
    def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
        """
        Extract keywords from text (simple frequency-based approach).
        
        Args:
            text: Text to analyze
            max_keywords: Maximum number of keywords to return
            
        Returns:
            list: List of keywords
        """
        # Convert to lowercase and split into words
        words = re.findall(r'\b[a-zàâäéèêëïîôùûüÿæœç]{4,}\b', text.lower())
        
        # Common French stop words
        stop_words = {
            'dans', 'pour', 'avec', 'sans', 'sous', 'sur', 'vers',
            'chez', 'entre', 'parmi', 'selon', 'contre', 'depuis',
            'pendant', 'avant', 'après', 'lors', 'durant', 'cette',
            'celui', 'celle', 'ceux', 'celles', 'leur', 'leurs',
            'notre', 'votre', 'quel', 'quelle', 'quels', 'quelles',
            'tout', 'tous', 'toute', 'toutes', 'autre', 'autres',
            'même', 'mêmes', 'tel', 'telle', 'tels', 'telles',
            'être', 'avoir', 'faire', 'dire', 'aller', 'voir',
            'savoir', 'pouvoir', 'vouloir', 'venir', 'devoir',
            'plus', 'moins', 'très', 'bien', 'encore', 'aussi',
            'donc', 'mais', 'alors', 'ainsi', 'comme', 'quand',
        }
        
        # Filter stop words and count frequencies
        word_freq = {}
        for word in words:
            if word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Sort by frequency and return top keywords
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, _ in sorted_words[:max_keywords]]
        
        return keywords
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
        """
        Truncate text to maximum length.
        
        Args:
            text: Text to truncate
            max_length: Maximum length
            suffix: Suffix to add if truncated
            
        Returns:
            str: Truncated text
        """
        if len(text) <= max_length:
            return text
        
        # Try to break at word boundary
        truncated = text[:max_length - len(suffix)]
        last_space = truncated.rfind(' ')
        
        if last_space > max_length * 0.8:  # Only break at space if it's not too far back
            truncated = truncated[:last_space]
        
        return truncated + suffix
