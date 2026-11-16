from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routers import accounts, orders, markets, health
from shared.kafka_client import start_kafka, stop_kafka
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("exchange_connector_starting")
    await start_kafka()
    yield
    await stop_kafka()
    logger.info("exchange_connector_stopping")

app = FastAPI(
    title="NEXORUM Exchange Connector",
    description="Unified multi-exchange connectivity with CCXT Pro",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(health.router, tags=["Health"])
app.include_router(accounts.router, prefix="/accounts", tags=["Exchange Accounts"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])
app.include_router(markets.router, prefix="/markets", tags=["Markets"])

@app.get("/")
async def root():
    return {"service": "NEXORUM Exchange Connector", "status": "operational", "exchanges": ["binance","bybit","okx","coinbase"]}
