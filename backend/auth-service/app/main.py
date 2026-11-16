from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routers import auth, users, mfa, health
from shared.kafka_client import start_kafka, stop_kafka
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("auth_service_starting")
    await start_kafka()
    yield
    await stop_kafka()
    logger.info("auth_service_stopping")

app = FastAPI(
    title="NEXORUM Auth Service",
    description="Authentication, authorization, MFA, and API key management",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(mfa.router, prefix="/mfa", tags=["MFA"])

@app.get("/")
async def root():
    return {"service": "NEXORUM Auth Service", "status": "operational"}
