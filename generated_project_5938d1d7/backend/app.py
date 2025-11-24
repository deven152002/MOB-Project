from fastapi import FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
import jwt
import datetime

# Database configuration
SQLALCHEMY_DATABASE_URL = "sqlite:///database.db"

# Create database engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create async session maker
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession)

# Create FastAPI app
app = FastAPI()

# Set up OAuth2 password bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Define Pydantic models
class User(BaseModel):
    username: str
    email: str

class Token(BaseModel):
    access_token: str
    token_type: str

class ChatBotRequest(BaseModel):
    message: str

# Set up JWT secret key
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"

# Create database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Define routes

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Implement authentication logic here
    # For demonstration purposes, let's assume we have a user with username "admin" and password "password"
    user = User(username="admin", email="admin@example.com")
    access_token = jwt.encode({"sub": user.username}, SECRET_KEY, algorithm="HS256")
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/chatbot", response_model=ChatBotRequest)
async def chatbot(message: ChatBotRequest):
    # Implement chatbot logic here
    # For demonstration purposes, let's just return the message
    return message

# Define API endpoints

@app.get("/users")
async def read_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return [{"username": user.username, "email": user.email} for user in users]
    finally:
        db.close()

@app.post("/users", response_model=User)
async def create_user(user: User):
    db = SessionLocal()
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    finally:
        db.close()

@app.put("/users/{user_id}", response_model=User)
async def update_user(user_id: int, user: User):
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.id == user_id).first()
        if not existing_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        existing_user.username = user.username
        existing_user.email = user.email
        db.add(existing_user)
        db.commit()
        db.refresh(existing_user)
        return existing_user
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    finally:
        db.close()

@app.delete("/users/{user_id}")
async def delete_user(user_id: int):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        db.delete(user)
        db.commit()
        return {"message": "User deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    finally:
        db.close()

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)