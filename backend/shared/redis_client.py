import redis.asyncio as redis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)

async def get_redis():
    return redis.Redis(connection_pool=pool)
