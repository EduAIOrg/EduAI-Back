"""FastAPI main application."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import init_db, close_db
from app.routers import auth, documents, chat, quiz, translate, voice, notifications, billing


# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting EduAI Africa backend...")
    
    # Create necessary directories
    Path(settings.UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
    
    # Resolve and validate HF LLM Model
    from app.ai.llm_factory import LLMFactory
    try:
        await LLMFactory.validate_and_resolve_model()
    except Exception as e:
        logger.error(f"Failed to validate Hugging Face model on startup: {e}")
        
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down EduAI Africa backend...")
    await close_db()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for EduAI Africa - AI-powered educational assistant",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": exc.body
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An error occurred"
        }
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        dict: Health status
    """
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint.
    
    Returns:
        dict: Welcome message
    """
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


# Mount static files for uploads
uploads_path = Path(settings.UPLOADS_DIR)
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount(
    "/static/uploads",
    StaticFiles(directory=str(uploads_path)),
    name="uploads"
)


# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(quiz.router, prefix="/api")
app.include_router(translate.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(billing.router, prefix="/api")


# Log registered routes
@app.on_event("startup")
async def log_routes():
    """Log all registered routes."""
    if settings.DEBUG:
        logger.info("Registered routes:")
        for route in app.routes:
            if hasattr(route, "methods"):
                logger.info(f"  {', '.join(route.methods)} {route.path}")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
