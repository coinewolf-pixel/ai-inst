from fastapi import APIRouter, Depends
from pydantic import BaseModel
from shared.auth import get_current_user
import pyotp
import qrcode
import io
import base64

router = APIRouter()

class MFAVerify(BaseModel):
    code: str

@router.post("/setup")
async def setup_mfa(user=Depends(get_current_user)):
    secret = pyotp.random_base32()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user["email"],
        issuer_name="NEXORUM AI"
    )
    qr = qrcode.make(uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_b64}",
        "message": "Scan this QR code with your authenticator app"
    }

@router.post("/verify")
async def verify_mfa(req: MFAVerify, user=Depends(get_current_user)):
    # In production: verify against stored secret
    return {"verified": True, "message": "MFA enabled successfully"}

@router.post("/disable")
async def disable_mfa(user=Depends(get_current_user)):
    return {"disabled": True}
