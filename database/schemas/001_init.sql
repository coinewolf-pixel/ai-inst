-- NEXORUM AI INSTITU — Core PostgreSQL + TimescaleDB Schema
-- Run as init script in Docker

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ═══════════════════════════════════════════════════════════
-- USERS & AUTH
-- ═══════════════════════════════════════════════════════════
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'trader' CHECK (role IN ('admin','trader','analyst','risk_manager')),
    kyc_status VARCHAR(50) DEFAULT 'pending' CHECK (kyc_status IN ('pending','verified','rejected')),
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    api_key_prefix VARCHAR(8),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(8) NOT NULL,
    name VARCHAR(100),
    permissions JSONB DEFAULT '[]',
    ip_whitelist JSONB DEFAULT '[]',
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════
-- EXCHANGES & ACCOUNTS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE exchanges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(50) NOT NULL UNIQUE,
    api_base_url VARCHAR(255),
    ws_url VARCHAR(255),
    supports_futures BOOLEAN DEFAULT FALSE,
    supports_margin BOOLEAN DEFAULT FALSE,
    supports_options BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE exchange_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    exchange_id UUID REFERENCES exchanges(id) ON DELETE CASCADE,
    account_name VARCHAR(100),
    api_key_encrypted TEXT NOT NULL,
    api_secret_encrypted TEXT NOT NULL,
    passphrase_encrypted TEXT,
    sub_account VARCHAR(100),
    is_testnet BOOLEAN DEFAULT FALSE,
    is_default BOOLEAN DEFAULT FALSE,
    balance_usd DECIMAL(18,8) DEFAULT 0,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════
-- STRATEGIES & AGENTS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    strategy_type VARCHAR(50) NOT NULL CHECK (strategy_type IN ('mean_reversion','momentum','arbitrage','market_making','custom_ml','grid','dca')),
    config JSONB NOT NULL DEFAULT '{}',
    ai_prompt TEXT,
    ai_model VARCHAR(50) DEFAULT 'gpt-4o',
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft','active','paused','archived')),
    version INT DEFAULT 1,
    is_public BOOLEAN DEFAULT FALSE,
    sharpe_ratio DECIMAL(5,2),
    max_drawdown DECIMAL(5,2),
    total_return DECIMAL(10,4),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    strategy_id UUID REFERENCES strategies(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    agent_type VARCHAR(50) DEFAULT 'trading' CHECK (agent_type IN ('trading','risk','analyst','executor')),
    config JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'idle' CHECK (status IN ('idle','running','paused','error','stopped')),
    exchange_account_id UUID REFERENCES exchange_accounts(id) ON DELETE SET NULL,
    last_action_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════
-- ORDERS & TRADES (TimescaleDB Hypertables)
-- ═══════════════════════════════════════════════════════════
CREATE TABLE orders (
    id UUID,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    exchange_account_id UUID REFERENCES exchange_accounts(id) ON DELETE SET NULL,
    exchange_order_id VARCHAR(255),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('buy','sell')),
    order_type VARCHAR(20) NOT NULL CHECK (order_type IN ('market','limit','stop_limit','stop_market','trailing_stop','iceberg')),
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8),
    stop_price DECIMAL(18,8),
    filled_quantity DECIMAL(18,8) DEFAULT 0,
    average_price DECIMAL(18,8),
    fee DECIMAL(18,8) DEFAULT 0,
    fee_asset VARCHAR(20),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','open','partially_filled','filled','cancelled','rejected','expired')),
    time_in_force VARCHAR(20) DEFAULT 'GTC',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

SELECT create_hypertable('orders', 'created_at', if_not_exists => TRUE);
CREATE INDEX idx_orders_user_symbol ON orders (user_id, symbol, created_at DESC);
CREATE INDEX idx_orders_agent ON orders (agent_id, created_at DESC);
CREATE INDEX idx_orders_status ON orders (status, created_at DESC);

CREATE TABLE trades (
    id UUID,
    order_id UUID,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    exchange_trade_id VARCHAR(255),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    fee DECIMAL(18,8) DEFAULT 0,
    fee_asset VARCHAR(20),
    pnl DECIMAL(18,8),
    realized_pnl DECIMAL(18,8),
    created_at TIMESTAMPTZ NOT NULL
);

SELECT create_hypertable('trades', 'created_at', if_not_exists => TRUE);
CREATE INDEX idx_trades_user_symbol ON trades (user_id, symbol, created_at DESC);
CREATE INDEX idx_trades_agent ON trades (agent_id, created_at DESC);

-- ═══════════════════════════════════════════════════════════
-- POSITIONS & PORTFOLIO
-- ═══════════════════════════════════════════════════════════
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    exchange_account_id UUID REFERENCES exchange_accounts(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('long','short')),
    quantity DECIMAL(18,8) NOT NULL DEFAULT 0,
    entry_price DECIMAL(18,8),
    mark_price DECIMAL(18,8),
    liquidation_price DECIMAL(18,8),
    unrealized_pnl DECIMAL(18,8) DEFAULT 0,
    realized_pnl DECIMAL(18,8) DEFAULT 0,
    margin_used DECIMAL(18,8) DEFAULT 0,
    leverage DECIMAL(5,2) DEFAULT 1,
    is_open BOOLEAN DEFAULT TRUE,
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, exchange_account_id, symbol, side)
);

CREATE TABLE portfolio_snapshots (
    id UUID,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    total_equity DECIMAL(18,8) NOT NULL,
    available_balance DECIMAL(18,8) NOT NULL,
    margin_balance DECIMAL(18,8) NOT NULL,
    unrealized_pnl DECIMAL(18,8) DEFAULT 0,
    daily_pnl DECIMAL(18,8) DEFAULT 0,
    weekly_pnl DECIMAL(18,8) DEFAULT 0,
    monthly_pnl DECIMAL(18,8) DEFAULT 0,
    assets JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL
);

SELECT create_hypertable('portfolio_snapshots', 'created_at', if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');

-- ═══════════════════════════════════════════════════════════
-- RISK & COMPLIANCE
-- ═══════════════════════════════════════════════════════════
CREATE TABLE risk_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    limit_type VARCHAR(50) NOT NULL CHECK (limit_type IN ('max_position_size','max_daily_loss','max_drawdown','max_leverage','max_orders_per_min','max_exposure','var_limit')),
    symbol VARCHAR(50),
    value DECIMAL(18,8) NOT NULL,
    is_hard_limit BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE risk_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('limit_breach','margin_call','liquidation_warning','unusual_activity','circuit_breaker','ai_override')),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    description TEXT,
    metadata JSONB DEFAULT '{}',
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    ip_address INET,
    user_agent TEXT,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user ON audit_logs (user_id, created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs (action, created_at DESC);

-- ═══════════════════════════════════════════════════════════
-- AI ORCHESTRATION
-- ═══════════════════════════════════════════════════════════
CREATE TABLE ai_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    title VARCHAR(255),
    model VARCHAR(50) DEFAULT 'gpt-4o',
    context_window JSONB DEFAULT '[]',
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ai_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES ai_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('system','user','assistant','tool')),
    content TEXT NOT NULL,
    tool_calls JSONB DEFAULT '[]',
    tokens_used INT,
    latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════
-- NOTIFICATIONS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL CHECK (type IN ('trade','risk','system','price_alert','agent')),
    title VARCHAR(255) NOT NULL,
    body TEXT,
    data JSONB DEFAULT '{}',
    is_read BOOLEAN DEFAULT FALSE,
    channel VARCHAR(20) DEFAULT 'in_app' CHECK (channel IN ('in_app','email','sms','push','telegram')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_unread ON notifications (user_id, is_read, created_at DESC);

-- Seed exchanges
INSERT INTO exchanges (name, slug, api_base_url, ws_url, supports_futures, supports_margin) VALUES
('Binance', 'binance', 'https://api.binance.com', 'wss://stream.binance.com:9443/ws', TRUE, TRUE),
('Binance Testnet', 'binance_testnet', 'https://testnet.binance.vision', 'wss://testnet.binance.vision/ws', TRUE, TRUE),
('Bybit', 'bybit', 'https://api.bybit.com', 'wss://stream.bybit.com/v5/public', TRUE, TRUE),
('OKX', 'okx', 'https://www.okx.com', 'wss://ws.okx.com:8443/ws/v5/public', TRUE, TRUE),
('Coinbase Advanced', 'coinbase', 'https://api.coinbase.com', 'wss://advanced-trade-ws.coinbase.com', FALSE, FALSE)
ON CONFLICT DO NOTHING;
