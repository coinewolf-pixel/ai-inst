from fastapi import FastAPI, WebSocket
from contextlib import asynccontextmanager
from app.routers import streams, candles, health
from app.streams.websocket_manager import ws_manager
from shared.kafka_client import start_kafka, stop_kafka
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("market_data_starting")
    await start_kafka()
    yield
    await stop_kafka()
    logger.info("market_data_stopping")

app = FastAPI(
    title="NEXORUM Market Data",
    description="Real-time market data aggregation, WebSocket feeds, and historical data",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(health.router, tags=["Health"])
app.include_router(streams.router, prefix="/streams", tags=["Streams"])
app.include_router(candles.router, prefix="/candles", tags=["Candles"])

@app.websocket("/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    await ws_manager.connect(websocket, symbol)
    try:
        while True:
            data = await websocket.receive_text()
            await ws_manager.broadcast(symbol, data)
    except Exception:
        ws_manager.disconnect(websocket, symbol)

@app.get("/")
async def root():
    return {"service": "NEXORUM Market Data", "status": "operational", "symbols_tracked": 1247}
