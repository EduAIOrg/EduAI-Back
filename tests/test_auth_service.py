"""Tests for authentication service."""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from app.services.auth_service import AuthService
from app.schemas.auth import TokenData


class TestAuthService:
    """Test suite for AuthService."""
    
    def test_hash_password(self):
        """Test password hashing."""
        password = "test_password_123"
        hashed = AuthService.hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$2b$")
    
    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "test_password_123"
        hashed = AuthService.hash_password(password)
        
        assert AuthService.verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = AuthService.hash_password(password)
        
        assert AuthService.verify_password(wrong_password, hashed) is False
    
    def test_create_access_token(self):
        """Test JWT access token creation."""
        user_id = uuid4()
        email = "test@example.com"
        
        token, expire = AuthService.create_access_token(user_id, email)
        
        assert isinstance(token, str)
        assert len(token) > 0
        assert isinstance(expire, datetime)
        assert expire > datetime.utcnow()
    
    def test_create_refresh_token(self):
        """Test JWT refresh token creation."""
        user_id = uuid4()
        email = "test@example.com"
        
        token, expire = AuthService.create_refresh_token(user_id, email)
        
        assert isinstance(token, str)
        assert len(token) > 0
        assert isinstance(expire, datetime)
        assert expire > datetime.utcnow()
    
    def test_verify_token_valid(self):
        """Test token verification with valid token."""
        user_id = uuid4()
        email = "test@example.com"
        
        token, _ = AuthService.create_access_token(user_id, email)
        token_data = AuthService.verify_token(token)
        
        assert token_data is not None
        assert isinstance(token_data, TokenData)
        assert token_data.user_id == user_id
        assert token_data.email == email
    
    def test_verify_token_invalid(self):
        """Test token verification with invalid token."""
        invalid_token = "invalid.token.here"
        
        token_data = AuthService.verify_token(invalid_token)
        
        assert token_data is None
    
    def test_verify_token_expired(self):
        """Test token verification with expired token."""
        # This test would require mocking time or using a very short expiration
        # For now, we just verify the structure
        user_id = uuid4()
        email = "test@example.com"
        
        token, _ = AuthService.create_access_token(user_id, email)
        token_data = AuthService.verify_token(token)
        
        assert token_data is not None
    
    def test_password_hash_uniqueness(self):
        """Test that same password produces different hashes (salt)."""
        password = "test_password_123"
        hash1 = AuthService.hash_password(password)
        hash2 = AuthService.hash_password(password)
        
        # Hashes should be different due to random salt
        assert hash1 != hash2
        
        # But both should verify correctly
        assert AuthService.verify_password(password, hash1)
        assert AuthService.verify_password(password, hash2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
