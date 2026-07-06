create table if not exists markets (
    market_pk bigserial primary key,
    exchange text not null,
    native_market_id text not null,
    native_event_id text,
    native_series_id text,
    market_family text,
    market_name text,
    market_status text,
    settlement_source text,
    raw_payload jsonb not null default '{}'::jsonb,
    discovered_at_utc timestamptz not null default now(),
    updated_at_utc timestamptz not null default now(),
    unique (exchange, native_market_id)
);

create table if not exists contracts (
    contract_pk bigserial primary key,
    market_pk bigint not null references markets(market_pk),
    exchange text not null,
    native_contract_id text not null,
    contract_name text,
    outcome_label text,
    min_value numeric,
    max_value numeric,
    lower_inclusive boolean,
    upper_inclusive boolean,
    settlement_text text,
    raw_payload jsonb not null default '{}'::jsonb,
    discovered_at_utc timestamptz not null default now(),
    updated_at_utc timestamptz not null default now(),
    unique (exchange, native_contract_id)
);

create table if not exists market_quotes (
    quote_pk bigserial primary key,
    exchange text not null,
    native_market_id text not null,
    native_contract_id text,
    source_timestamp_utc timestamptz,
    observed_at_utc timestamptz not null,
    received_at_utc timestamptz not null default now(),
    inserted_at_utc timestamptz not null default now(),
    best_bid numeric,
    best_ask numeric,
    bid_size numeric,
    ask_size numeric,
    midpoint numeric generated always as (
        case
            when best_bid is not null and best_ask is not null then (best_bid + best_ask) / 2
            else null
        end
    ) stored,
    raw_payload jsonb not null default '{}'::jsonb
);

create index if not exists idx_market_quotes_lookup
    on market_quotes (exchange, native_market_id, native_contract_id, observed_at_utc);

create table if not exists market_trades (
    trade_pk bigserial primary key,
    exchange text not null,
    native_trade_id text,
    native_market_id text not null,
    native_contract_id text,
    source_timestamp_utc timestamptz,
    observed_at_utc timestamptz not null,
    received_at_utc timestamptz not null default now(),
    inserted_at_utc timestamptz not null default now(),
    trade_price numeric,
    trade_size numeric,
    aggressor_side text,
    raw_payload jsonb not null default '{}'::jsonb,
    unique (exchange, native_trade_id)
);

create index if not exists idx_market_trades_lookup
    on market_trades (exchange, native_market_id, native_contract_id, observed_at_utc);

create table if not exists events (
    event_pk bigserial primary key,
    event_id text not null unique,
    event_type text not null,
    source text not null,
    scheduled_timestamp_utc timestamptz,
    source_timestamp_utc timestamptz,
    observed_at_utc timestamptz,
    inserted_at_utc timestamptz not null default now(),
    actual_value numeric,
    previous_value numeric,
    consensus numeric,
    surprise numeric,
    revision numeric,
    release_url text,
    raw_payload jsonb not null default '{}'::jsonb
);

create table if not exists event_context (
    event_context_pk bigserial primary key,
    event_pk bigint not null references events(event_pk),
    symbol text not null,
    source text not null,
    observed_at_utc timestamptz not null,
    value numeric,
    raw_payload jsonb not null default '{}'::jsonb,
    unique (event_pk, symbol, source)
);

create table if not exists exchange_contract_mesh (
    mesh_pk bigserial primary key,
    market_family text not null,
    economic_outcome_id text not null,
    exchange text not null,
    native_market_id text not null,
    native_contract_id text not null,
    mapping_confidence text not null default 'manual_review',
    notes text,
    created_at_utc timestamptz not null default now(),
    unique (market_family, economic_outcome_id, exchange, native_contract_id)
);

