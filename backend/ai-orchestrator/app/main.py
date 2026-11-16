from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.routers import conversations, strategies, agents, health
from shared.kafka_client import start_kafka, stop_kafka
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ai_orchestrator_starting", version=settings.APP_VERSION)
    await start_kafka()
    yield
    await stop_kafka()
    logger.info("ai_orchestrator_stopping")

app = FastAPI(
    title="NEXORUM AI Orchestrator",
    description="AI-native strategy generation, agent orchestration, and conversational trading intelligence",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(health.router, tags=["Health"])
app.include_router(conversations.router, prefix="/conversations", tags=["AI Conversations"])
app.include_router(strategies.router, prefix="/strategies", tags=["Strategies"])
app.include_router(agents.router, prefix="/agents", tags=["Agents"])

@app.get("/")
async def root():
    return {"service": "NEXORUM AI Orchestrator", "status": "operational", "version": "1.0.0"}
