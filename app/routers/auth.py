"""Authentication router."""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import RegisterRequest, Token, UserResponse
from app.services.auth_service import AuthService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
) -> Token:
    """
    Register a new user.
    
    Args:
        request: Registration request with email, password, full_name
        db: Database session
        
    Returns:
        Token: JWT access token
        
    Raises:
        HTTPException: If email already exists
    """
    try:
        # Check if user already exists
        result = await db.execute(
            select(User).where(User.email == request.email)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = AuthService.hash_password(request.password)
        
        # Create user
        user = User(
            email=request.email,
            hashed_password=hashed_password,
            full_name=request.full_name,
            is_active=True
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Create access token
        access_token, expire = AuthService.create_access_token(
            user_id=user.id,
            email=user.email
        )
        
        expires_in = int((expire - datetime.utcnow()).total_seconds())
        
        logger.info(f"User registered: {user.email}")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> Token:
    """
    Login with email and password.
    
    Args:
        form_data: OAuth2 form with username (email) and password
        db: Database session
        
    Returns:
        Token: JWT access token
        
    Raises:
        HTTPException: If credentials are invalid
    """
    try:
        # Get user by email
        result = await db.execute(
            select(User).where(User.email == form_data.username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not AuthService.verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )
        
        # Create access token
        access_token, expire = AuthService.create_access_token(
            user_id=user.id,
            email=user.email
        )
        
        expires_in = int((expire - datetime.utcnow()).total_seconds())
        
        logger.info(f"User logged in: {user.email}")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging in: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to login"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """
    Get current user information.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        UserResponse: User information
    """
    return UserResponse.model_validate(current_user)
