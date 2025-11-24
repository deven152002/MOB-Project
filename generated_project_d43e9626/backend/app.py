from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from jose import jwt, JWTError
import secrets
import string
from datetime import datetime, timedelta

# Database configuration
SQLALCHEMY_DATABASE_URL = "sqlite:///exercise.db"

# Create database engine and session maker
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

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
class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    username: str
    email: str

class Exercise(BaseModel):
    code: str
    explanation: str
    quiz_id: int
    user_id: int

# Authentication
def verify_token(token: str):
    try:
        payload = jwt.decode(token, "secret_key", algorithms=["HS256"])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Dependency for authentication
async def get_current_user(token: str = Depends(oauth2_scheme)):
    user_id = verify_token(token)
    # Fetch user from database
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# Dependency for exercises
async def get_current_exercise(exercise_id: int, current_user: User = Depends(get_current_user)):
    # Fetch exercise from database
    db = SessionLocal()
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise

# Create user endpoint
@app.post("/users/")
async def create_user(user: User):
    # Insert user into database
    db = SessionLocal()
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Create exercise endpoint
@app.post("/exercises/")
async def create_exercise(exercise: Exercise):
    # Insert exercise into database
    db = SessionLocal()
    try:
        db.add(exercise)
        db.commit()
        db.refresh(exercise)
        return exercise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Get user endpoint
@app.get("/users/")
async def get_users(current_user: User = Depends(get_current_user)):
    # Fetch users from database
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return users
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Get exercise endpoint
@app.get("/exercises/")
async def get_exercises(current_user: User = Depends(get_current_user)):
    # Fetch exercises from database
    db = SessionLocal()
    try:
        exercises = db.query(Exercise).all()
        return exercises
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Get user exercise endpoint
@app.get("/exercises/{exercise_id}/")
async def get_exercise(exercise_id: int, current_user: User = Depends(get_current_user)):
    # Fetch exercise from database
    db = SessionLocal()
    try:
        exercise = await get_current_exercise(exercise_id, current_user)
        return exercise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Login endpoint
@app.post("/token/")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Verify credentials and generate token
    user = form_data.username
    password = form_data.password
    # Fetch user from database
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == user).first()
        if not user or user.password != password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        # Generate token
        access_token_expires = timedelta(minutes=30)
        access_token = jwt.encode({"sub": user.id}, "secret_key", algorithm="HS256", expires_delta=access_token_expires)
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

# Logout endpoint
@app.post("/logout/")
async def logout(current_user: User = Depends(get_current_user)):
    # Clear token from database
    db = SessionLocal()
    try:
        user = current_user
        # Delete token from database
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))