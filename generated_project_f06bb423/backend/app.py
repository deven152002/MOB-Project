from fastapi import FastAPI, HTTPException, Depends, Query, UploadFile, File, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import Optional, List, Tuple
from jose import jwt, JWTError
from passlib.context import CryptContext
import datetime
import os
import shutil
import logging
import secrets
import re
from pathlib import Path
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from PIL import Image as PILImage
import io

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# CORS configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")

# File upload security
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_IMAGE_TYPES = os.getenv("ALLOWED_IMAGE_TYPES", "jpg,jpeg,png,gif,webp").split(",")
ALLOWED_IMAGE_EXTENSIONS = [f".{ext.lower()}" for ext in ALLOWED_IMAGE_TYPES]

# Rate limiting
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# Database configuration
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./image_processing.db")

# Create database engine and session maker (using sync for SQLite)
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Integer, default=1)  # 1 for active, 0 for inactive

class Image(Base):
    __tablename__ = "images"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    brightness = Column(Float, default=0.0)
    filter = Column(String, nullable=True)
    user_id = Column(Integer, nullable=True)  # Link to user if authentication is used

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency for database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    finally:
        db.close()

# FastAPI application
app = FastAPI(title="Image Processing API", version="1.0.0")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Create uploads directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Add CORS middleware with environment-based configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Serve uploaded files statically
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# OAuth2 password bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic models with validation
class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    
    @validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username must contain only letters, numbers, and underscores')
        return v

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool

    class Config:
        from_attributes = True

class ImageCreate(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    width: int = Field(..., gt=0, le=10000)
    height: int = Field(..., gt=0, le=10000)
    brightness: float = Field(default=0.0, ge=0.0, le=100.0)
    filter: Optional[str] = Field(None, max_length=50)

class ImageResponse(BaseModel):
    id: int
    filename: str
    width: int
    height: int
    brightness: float
    filter: Optional[str]

    class Config:
        from_attributes = True

# Security utilities
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get current authenticated user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None or user.is_active == 0:
        raise credentials_exception
    return user

# File upload security utilities
def validate_file_type(filename: str) -> bool:
    """Validate file extension"""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and other attacks"""
    # Remove path components
    filename = Path(filename).name
    # Remove dangerous characters
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    return filename

def validate_image_file(file: UploadFile) -> Tuple[bool, Optional[str]]:
    """Validate uploaded image file"""
    # Check file extension
    if not validate_file_type(file.filename):
        return False, f"Invalid file type. Allowed types: {', '.join(ALLOWED_IMAGE_TYPES)}"
    
    # Check file size (read first chunk)
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_UPLOAD_SIZE_BYTES:
        return False, f"File size exceeds maximum allowed size of {MAX_UPLOAD_SIZE_MB}MB"
    
    if file_size == 0:
        return False, "File is empty"
    
    return True, None

# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "message": "Validation error"}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred"}
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Image Processing API"}

# Database initialization
@app.on_event("startup")
async def startup_event():
    """Initialize database and create default admin user if needed"""
    logger.info("Starting up Image Processing API")
    # Tables are created by Base.metadata.create_all()
    # Optionally create a default admin user here

# Authentication endpoints
@app.post("/token", response_model=Token)
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user and return JWT token"""
    try:
        user = db.query(User).filter(User.username == form_data.username).first()
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if user.is_active == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during authentication"
        )

@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.username == user_data.username) | (User.email == user_data.email)
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already registered"
            )
        
        # Create new user
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            is_active=1
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"New user registered: {user_data.username}")
        return db_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during registration"
        )

# Image endpoints
@app.get("/images/{image_id}", response_model=ImageResponse)
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def get_image(request: Request, image_id: int, db: Session = Depends(get_db)):
    """Get a specific image by ID"""
    try:
        if image_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image ID"
            )
        
        image = db.query(Image).filter(Image.id == image_id).first()
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found"
            )
        return image
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting image {image_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving image"
        )

@app.post("/images", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def create_image(request: Request, image: ImageCreate, db: Session = Depends(get_db)):
    """Create a new image record"""
    try:
        db_image = Image(**image.dict())
        db.add(db_image)
        db.commit()
        db.refresh(db_image)
        logger.info(f"Created image record: {db_image.id}")
        return db_image
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error creating image record"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating image"
        )

@app.post("/images/upload", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload an image file with security validation"""
    try:
        # Validate file
        is_valid, error_msg = validate_image_file(file)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Sanitize filename
        safe_filename = sanitize_filename(file.filename)
        
        # Read file content to validate it's actually an image
        file_content = await file.read()
        try:
            img = PILImage.open(io.BytesIO(file_content))
            width, height = img.size
            # Verify it's a valid image format
            img.verify()
        except Exception as e:
            logger.warning(f"Invalid image file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is not a valid image"
            )
        
        # Reset file pointer for saving
        file.file = io.BytesIO(file_content)
        
        # Save uploaded file
        file_path = UPLOAD_DIR / safe_filename
        # Handle filename collisions
        counter = 1
        original_path = file_path
        while file_path.exists():
            name, ext = os.path.splitext(original_path.name)
            file_path = UPLOAD_DIR / f"{name}_{counter}{ext}"
            counter += 1
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create image record
        db_image = Image(
            filename=file_path.name,
            width=width,
            height=height,
            brightness=0.0,
            filter=None
        )
        db.add(db_image)
        db.commit()
        db.refresh(db_image)
        logger.info(f"Uploaded image: {file_path.name} (ID: {db_image.id})")
        return db_image
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading image"
        )

@app.get("/images", response_model=List[ImageResponse])
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def list_images(request: Request, db: Session = Depends(get_db), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
    """Get all images with pagination"""
    try:
        images = db.query(Image).offset(skip).limit(limit).all()
        return images
    except Exception as e:
        logger.error(f"Error listing images: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving images"
        )

@app.post("/images/{image_id}/resize", response_model=ImageResponse)
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def resize_image(
    request: Request,
    image_id: int,
    width: int = Query(..., ge=1, le=10000, description="New width"),
    height: int = Query(..., ge=1, le=10000, description="New height"),
    db: Session = Depends(get_db)
):
    """Resize an image"""
    try:
        if image_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image ID"
            )
        
        image = db.query(Image).filter(Image.id == image_id).first()
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found"
            )
        
        image.width = width
        image.height = height
        db.commit()
        db.refresh(image)
        logger.info(f"Resized image {image_id} to {width}x{height}")
        return image
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error resizing image {image_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error resizing image"
        )

@app.post("/images/{image_id}/brightness", response_model=ImageResponse)
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def adjust_brightness(
    request: Request,
    image_id: int,
    brightness: float = Query(..., ge=0.0, le=100.0, description="Brightness value (0-100)"),
    db: Session = Depends(get_db)
):
    """Adjust image brightness"""
    try:
        if image_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image ID"
            )
        
        image = db.query(Image).filter(Image.id == image_id).first()
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found"
            )
        
        image.brightness = brightness
        db.commit()
        db.refresh(image)
        logger.info(f"Adjusted brightness for image {image_id} to {brightness}")
        return image
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error adjusting brightness for image {image_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error adjusting brightness"
        )

@app.post("/images/{image_id}/filter", response_model=ImageResponse)
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def apply_filter(
    request: Request,
    image_id: int,
    filter_name: str = Query(..., min_length=1, max_length=50, description="Filter name", alias="filter"),
    db: Session = Depends(get_db)
):
    """Apply a filter to an image"""
    try:
        if image_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image ID"
            )
        
        # Validate filter name (prevent injection)
        allowed_filters = ["none", "grayscale", "sepia", "blur", "sharpen"]
        filter_value = filter_name.lower()
        if filter_value not in allowed_filters:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid filter. Allowed filters: {', '.join(allowed_filters)}"
            )
        
        image = db.query(Image).filter(Image.id == image_id).first()
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found"
            )
        
        image.filter = filter_value
        db.commit()
        db.refresh(image)
        logger.info(f"Applied filter '{filter_value}' to image {image_id}")
        return image
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error applying filter to image {image_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error applying filter"
        )

@app.post("/images/{image_id}/save", response_model=ImageResponse)
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def save_image(request: Request, image_id: int, db: Session = Depends(get_db)):
    """Save an image (placeholder for actual save logic)"""
    try:
        if image_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image ID"
            )
        
        image = db.query(Image).filter(Image.id == image_id).first()
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found"
            )
        
        # TODO: Implement actual save logic (e.g., save processed image to disk)
        logger.info(f"Saved image {image_id}")
        return image
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving image {image_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error saving image"
        )

# Guided tour endpoint
@app.get("/guided-tour")
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def guided_tour(request: Request):
    """Get guided tour information"""
    return {"message": "Welcome to our guided tour!"}
