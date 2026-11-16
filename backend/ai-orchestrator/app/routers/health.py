from fastapi import APIRouter
from shared.redis_client import get_redis
import asyncpg
import os

router = APIRouter()

@router.get("/health")
async def health_check():
    redis = await get_redis()
    redis_ok = await redis.ping()
    return {
        "status": "healthy" if redis_ok else "degraded",
        "service": "ai-orchestrator",
        "redis": "connected" if redis_ok else "disconnected"
    }

@router.get("/ready")
async def readiness():
    return {"status": "ready"}
