from fastapi import APIRouter, Depends
from shared.auth import get_current_user
from app.exchanges.manager import exchange_manager
import structlog

router = APIRouter()
logger = structlog.get_logger()

@router.get("/tickers")
async def get_tickers(exchange: str = "binance", user=Depends(get_current_user)):
    try:
        ex = await exchange_manager.get_exchange(exchange)
        tickers = await ex.fetch_tickers()
        await ex.close()

        simplified = {}
        for sym, data in list(tickers.items())[:50]:
            simplified[sym] = {
                "last": data.get("last"),
                "bid": data.get("bid"),
                "ask": data.get("ask"),
                "change_24h": data.get("percentage"),
                "volume_24h": data.get("quoteVolume"),
                "high_24h": data.get("high"),
                "low_24h": data.get("low")
            }
        return {"exchange": exchange, "tickers": simplified}
    except Exception as e:
        logger.error("fetch_tickers_failed", error=str(e))
        return {"exchange": exchange, "tickers": {}, "error": str(e)}

@router.get("/orderbook")
async def get_orderbook(symbol: str = "BTC/USDT", exchange: str = "binance", user=Depends(get_current_user)):
    try:
        ex = await exchange_manager.get_exchange(exchange)
        ob = await ex.fetch_order_book(symbol, limit=20)
        await ex.close()
        return {
            "symbol": symbol,
            "exchange": exchange,
            "timestamp": ob.get("timestamp"),
            "bids": ob.get("bids", [])[:10],
            "asks": ob.get("asks", [])[:10],
            "spread": ob["asks"][0][0] - ob["bids"][0][0] if ob.get("asks") and ob.get("bids") else None
        }
    except Exception as e:
        return {"symbol": symbol, "exchange": exchange, "error": str(e)}

@router.get("/ohlcv")
async def get_ohlcv(symbol: str = "BTC/USDT", exchange: str = "binance", timeframe: str = "1h", limit: int = 100, user=Depends(get_current_user)):
    try:
        ex = await exchange_manager.get_exchange(exchange)
        ohlcv = await ex.fetch_ohlcv(symbol, timeframe, limit=limit)
        await ex.close()
        candles = [
            {"timestamp": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]}
            for c in ohlcv
        ]
        return {"symbol": symbol, "timeframe": timeframe, "candles": candles}
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}
