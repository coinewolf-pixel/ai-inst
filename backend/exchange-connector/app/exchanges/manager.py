import ccxt.async_support as ccxt
from typing import Dict, Optional
import os

class ExchangeManager:
    _instances: Dict[str, ccxt.Exchange] = {}

    EXCHANGE_MAP = {
        "binance": ccxt.binance,
        "binance_testnet": ccxt.binance,
        "bybit": ccxt.bybit,
        "okx": ccxt.okx,
        "coinbase": ccxt.coinbase,
    }

    @classmethod
    async def get_exchange(cls, slug: str, api_key: Optional[str] = None, secret: Optional[str] = None, passphrase: Optional[str] = None, testnet: bool = False):
        key = f"{slug}:{api_key or 'public'}"
        if key not in cls._instances:
            exchange_class = cls.EXCHANGE_MAP.get(slug)
            if not exchange_class:
                raise ValueError(f"Exchange {slug} not supported")

            config = {"enableRateLimit": True, "options": {}}
            if testnet or slug == "binance_testnet":
                config["options"]["defaultType"] = "future"
                if slug == "binance_testnet":
                    config["sandbox"] = True

            if api_key and secret:
                config["apiKey"] = api_key
                config["secret"] = secret
                if passphrase:
                    config["password"] = passphrase

            exchange = exchange_class(config)
            cls._instances[key] = exchange

        return cls._instances[key]

    @classmethod
    async def close_all(cls):
        for ex in cls._instances.values():
            await ex.close()
        cls._instances.clear()

exchange_manager = ExchangeManager()
