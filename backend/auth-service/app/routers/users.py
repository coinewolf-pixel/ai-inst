from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from shared.auth import get_current_user

router = APIRouter()

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None

@router.get("/me")
async def get_me(user=Depends(get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "kyc_status": "verified",
        "mfa_enabled": True,
        "created_at": "2026-01-15T00:00:00Z"
    }

@router.patch("/me")
async def update_me(req: UserProfileUpdate, user=Depends(get_current_user)):
    return {"id": user["id"], "updated_fields": req.model_dump(exclude_unset=True)}

@router.get("/me/api-keys")
async def list_api_keys(user=Depends(get_current_user)):
    return {
        "api_keys": [
            {
                "id": "key_001",
                "name": "Trading Bot",
                "prefix": "nxr_8a2f",
                "permissions": ["read", "trade"],
                "last_used": "2026-08-01T10:00:00Z",
                "expires_at": None
            }
        ]
    }

@router.get("/{user_id}")
async def get_user(user_id: UUID, current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return {"id": str(user_id), "email": "user@example.com", "role": "trader"}
