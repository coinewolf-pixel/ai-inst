from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
import os
import structlog
from shared.kafka_client import publish

router = APIRouter()
logger = structlog.get_logger()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenRefresh(BaseModel):
    refresh_token: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: UserRegister):
    hashed = pwd_context.hash(req.password)
    user_id = "usr_" + os.urandom(8).hex()

    await publish("users.registered", {
        "user_id": user_id,
        "email": req.email,
        "timestamp": datetime.utcnow().isoformat()
    })

    logger.info("user_registered", user_id=user_id, email=req.email)
    return {"id": user_id, "email": req.email, "message": "Registration successful"}

@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # In production: verify against DB
    # Mock validation for structure
    if form_data.username != "demo@nexorum.ai" or form_data.password != "demo_password_2026":
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_data = {"sub": "usr_demo_001", "email": form_data.username, "role": "trader"}
    access = create_access_token(user_data)
    refresh = create_refresh_token(user_data)

    await publish("users.login", {
        "user_id": "usr_demo_001",
        "ip": "127.0.0.1",
        "timestamp": datetime.utcnow().isoformat()
    })

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@router.post("/refresh")
async def refresh_token(req: TokenRefresh):
    try:
        payload = jwt.decode(req.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_data = {"sub": payload["sub"], "email": payload.get("email"), "role": payload.get("role")}
        new_access = create_access_token(user_data)
        return {"access_token": new_access, "token_type": "bearer", "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60}
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@router.post("/logout")
async def logout():
    return {"message": "Logged out successfully"}
