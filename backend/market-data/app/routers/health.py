from fastapi import APIRouter
from shared.redis_client import get_redis

router = APIRouter()

@router.get("/health")
async def health_check():
    redis = await get_redis()
    redis_ok = await redis.ping()
    return {"status": "healthy", "service": "market-data", "redis": "connected" if redis_ok else "disconnected"}
