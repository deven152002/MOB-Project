from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import Optional
import jwt
import datetime

# Database configuration
SQLALCHEMY_DATABASE_URL = "sqlite:///chatbot.db"

# Create database engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create async session maker
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession)

# Dependency for database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI application
app = FastAPI()

# OAuth2 password bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic models
class User(BaseModel):
    username: str
    email: str

class Message(BaseModel):
    text: str

# Database models
class ChatMessage(BaseModel):
    id: int
    user_id: int
    message: str
    timestamp: datetime.datetime

class User(BaseModel):
    id: int
    username: str
    email: str

class ChatUser(BaseModel):
    id: int
    username: str
    email: str

# Database session
db = SessionLocal()

# Authentication
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_id = payload.get("sub")
        return User(id=user_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# Chat API endpoints
@app.post("/token", response_model=User)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # TO DO: Implement authentication logic here
    return User(username=form_data.username, email=form_data.username)

@app.get("/chat")
async def read_chat():
    messages = db.query(ChatMessage).all()
    return {"messages": [message.dict() for message in messages]}

@app.post("/chat", response_model=ChatMessage)
async def create_message(message: Message, current_user: User = Depends(get_current_user)):
    new_message = ChatMessage(user_id=current_user.id, message=message.text, timestamp=datetime.datetime.now())
    db.add(new_message)
    await db.commit()
    return new_message

@app.get("/chat/{message_id}")
async def read_message(message_id: int):
    message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return {"message": message.dict()}