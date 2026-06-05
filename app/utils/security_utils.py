"""Security utilities for prompt injection detection and context sanitization."""
import re
import logging

logger = logging.getLogger(__name__)


class PromptInjectionDetector:
    """Detects jailbreaks, prompt extractions, and malicious user prompts."""
    
    # Common prompt injection pattern signatures
    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(any|previous|all)\s+instructions",
        r"(?i)system\s+prompt",
        r"(?i)you\s+are\s+now\s+a\s+different\s+ai",
        r"(?i)act\s+as\s+a",
        r"(?i)dan\s+mode",
        r"(?i)bypass\s+restrictions",
        r"(?i)forget\s+rules",
        r"(?i)disregard\s+(the)?\s+above",
        r"(?i)stop\s+following\s+instructions",
        r"(?i)reveal\s+(your)?\s+initial\s+prompt",
        r"(?i)what\s+is\s+your\s+system\s+instruction",
    ]
    
    @staticmethod
    def is_injection(prompt: str) -> bool:
        """
        Check if the prompt contains prompt injection patterns.
        
        Args:
            prompt: User input string
            
        Returns:
            bool: True if injection pattern detected, False otherwise
        """
        if not prompt:
            return False
            
        for pattern in PromptInjectionDetector.INJECTION_PATTERNS:
            if re.search(pattern, prompt):
                logger.warning(f"Prompt injection pattern detected: '{pattern}'")
                return True
                
        return False


class ContextSanitizer:
    """Cleans and sanitizes retrieved context from files to prevent script injection and command leakage."""
    
    @staticmethod
    def sanitize(context: str) -> str:
        """
        Sanitize context by removing system command tags, HTML script tags, and prompt injection attempts within files.
        
        Args:
            context: Text chunk context
            
        Returns:
            str: Sanitized context
        """
        if not context:
            return ""
            
        # Remove script tags
        sanitized = re.sub(r"<script.*?>.*?</script>", "", context, flags=re.DOTALL | re.IGNORECASE)
        sanitized = re.sub(r"javascript:", "", sanitized, flags=re.IGNORECASE)
        
        # Remove markdown HTML wrappers
        sanitized = re.sub(r"<iframe.*?>.*?</iframe>", "", sanitized, flags=re.DOTALL | re.IGNORECASE)
        sanitized = re.sub(r"<object.*?>.*?</object>", "", sanitized, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove prompt command patterns that might cause model overrides
        sanitized = re.sub(r"(?i)system:", "doc_system:", sanitized)
        sanitized = re.sub(r"(?i)assistant:", "doc_assistant:", sanitized)
        sanitized = re.sub(r"(?i)user:", "doc_user:", sanitized)
        
        return sanitized
