-- Webhooks (ADR 0016, phase 3): addresses that receive events, signed, with retries.

CREATE TABLE lattice.webhook (
  id         bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name       varchar(128) NOT NULL,
  url        varchar(1024) NOT NULL,
  secret     varchar(64)  NOT NULL,                    -- signs each post (HMAC-SHA256)
  events     text[]       NOT NULL DEFAULT '{*}',      -- event types, or * for all
  format     varchar(16)  NOT NULL DEFAULT 'cloudevents' CHECK (format IN ('cloudevents', 'chat')),
  active     boolean      NOT NULL DEFAULT true,
  created_by bigint       REFERENCES lattice.app_user (id) ON DELETE SET NULL,
  created_at timestamp    NOT NULL DEFAULT lattice.utc_now()
);

CREATE TABLE lattice.webhook_delivery (
  id              bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  webhook_id      bigint       NOT NULL REFERENCES lattice.webhook (id) ON DELETE CASCADE,
  event_id        varchar(64)  NOT NULL,
  event_type      varchar(128) NOT NULL,
  subject         varchar(255) NOT NULL DEFAULT '',
  body            text         NOT NULL,               -- exactly what is posted and signed
  status          varchar(10)  NOT NULL DEFAULT 'queued',  -- queued, delivered, failed
  attempts        integer      NOT NULL DEFAULT 0,
  next_attempt_at timestamp    NOT NULL DEFAULT lattice.utc_now(),
  response_status integer,
  last_error      text         NOT NULL DEFAULT '',
  created_at      timestamp    NOT NULL DEFAULT lattice.utc_now(),
  delivered_at    timestamp
);
CREATE INDEX webhook_delivery_due ON lattice.webhook_delivery (next_attempt_at) WHERE status = 'queued';
CREATE INDEX webhook_delivery_webhook ON lattice.webhook_delivery (webhook_id, created_at);
