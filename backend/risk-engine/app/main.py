from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routers import limits, metrics, alerts, health
from shared.kafka_client import start_kafka, stop_kafka
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("risk_engine_starting")
    await start_kafka()
    yield
    await stop_kafka()
    logger.info("risk_engine_stopping")

app = FastAPI(
    title="NEXORUM Risk Engine",
    description="Real-time risk management, position limits, VaR, and circuit breakers",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(health.router, tags=["Health"])
app.include_router(limits.router, prefix="/limits", tags=["Risk Limits"])
app.include_router(metrics.router, prefix="/metrics", tags=["Risk Metrics"])
app.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])

@app.get("/")
async def root():
    return {"service": "NEXORUM Risk Engine", "status": "operational"}
