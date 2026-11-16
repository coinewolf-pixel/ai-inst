from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from shared.auth import get_current_user
from shared.kafka_client import publish
from datetime import datetime

router = APIRouter()

class AlertCreate(BaseModel):
    event_type: str = Field(..., pattern="^(limit_breach|margin_call|liquidation_warning|unusual_activity|circuit_breaker|ai_override)$")
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    description: str
    agent_id: Optional[UUID] = None
    metadata: dict = {}

@router.post("/")
async def create_alert(req: AlertCreate, user=Depends(get_current_user)):
    alert_id = UUID(int=0)
    await publish("risk.alerts", {
        "alert_id": str(alert_id),
        "user_id": user["id"],
        "severity": req.severity,
        "event_type": req.event_type,
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"id": str(alert_id), "severity": req.severity, "status": "active"}

@router.get("/")
async def list_alerts(
    severity: Optional[str] = None,
    resolved: Optional[bool] = None,
    user=Depends(get_current_user)
):
    return {
        "alerts": [
            {
                "id": "alert-001",
                "type": "limit_breach",
                "severity": "high",
                "description": "Daily loss limit exceeded on Agent Alpha",
                "agent_id": "agent-123",
                "created_at": datetime.utcnow().isoformat(),
                "resolved": False
            }
        ],
        "total": 1,
        "unresolved_critical": 1
    }

@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, user=Depends(get_current_user)):
    return {"id": alert_id, "resolved": True, "resolved_by": user["id"], "resolved_at": datetime.utcnow().isoformat()}
