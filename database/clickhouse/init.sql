-- NEXORUM AI INSTITU — ClickHouse Analytics Schema

CREATE DATABASE IF NOT EXISTS nexorum;

-- Tick data (ultra-high frequency)
CREATE TABLE IF NOT EXISTS nexorum.ticks (
    symbol String,
    exchange String,
    price Float64,
    quantity Float64,
    side String,
    trade_id String,
    is_buyer_maker UInt8,
    ts DateTime64(3),
    received_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (symbol, exchange, ts)
PARTITION BY toYYYYMMDD(ts)
TTL ts + INTERVAL 30 DAY;

-- OHLCV 1-minute candles
CREATE TABLE IF NOT EXISTS nexorum.candles_1m (
    symbol String,
    exchange String,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume Float64,
    quote_volume Float64,
    trades_count UInt32,
    ts DateTime,
    received_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (symbol, exchange, ts)
PARTITION BY toYYYYMMDD(ts)
TTL ts + INTERVAL 90 DAY;

-- Order book snapshots
CREATE TABLE IF NOT EXISTS nexorum.orderbook_snapshots (
    symbol String,
    exchange String,
    bids Array(Tuple(Float64, Float64)),
    asks Array(Tuple(Float64, Float64)),
    best_bid Float64,
    best_ask Float64,
    spread Float64,
    depth_usd_bid Float64,
    depth_usd_ask Float64,
    ts DateTime64(3),
    received_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (symbol, exchange, ts)
PARTITION BY toYYYYMMDD(ts)
TTL ts + INTERVAL 7 DAY;

-- AI predictions / signals
CREATE TABLE IF NOT EXISTS nexorum.ai_signals (
    strategy_id String,
    agent_id String,
    symbol String,
    signal String, -- buy, sell, hold
    confidence Float64,
    predicted_price Float64,
    horizon_minutes UInt16,
    features Vector(Float32), -- embedding
    model_version String,
    ts DateTime64(3),
    received_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (strategy_id, symbol, ts)
PARTITION BY toYYYYMMDD(ts);

-- Risk metrics time series
CREATE TABLE IF NOT EXISTS nexorum.risk_metrics (
    user_id String,
    agent_id String,
    metric_name String,
    value Float64,
    metadata String,
    ts DateTime64(3)
) ENGINE = MergeTree()
ORDER BY (user_id, metric_name, ts)
PARTITION BY toYYYYMMDD(ts);

-- Materialized view: Daily trading stats
CREATE MATERIALIZED VIEW IF NOT EXISTS nexorum.daily_stats
ENGINE = SummingMergeTree()
ORDER BY (symbol, exchange, date)
AS SELECT
    symbol,
    exchange,
    toDate(ts) as date,
    count() as trade_count,
    sum(quantity) as total_volume,
    avg(price) as avg_price,
    max(price) as day_high,
    min(price) as day_low
FROM nexorum.ticks
GROUP BY symbol, exchange, date;
