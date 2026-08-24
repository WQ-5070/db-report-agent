-- db-report-agent 样例库 DDL（PostgreSQL 版，对齐生产形态）
-- 与 generate_sample_data.py 生成的 SQLite 样例库同构，仅方言不同。
-- 用法：docker compose 启动 postgres 时会自动执行本文件初始化。

DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS regions;

CREATE TABLE regions (
    region_id   INTEGER PRIMARY KEY,
    region_name TEXT NOT NULL,
    tier        TEXT NOT NULL
);

CREATE TABLE users (
    user_id      INTEGER PRIMARY KEY,
    user_name    TEXT NOT NULL,
    city         TEXT NOT NULL,
    region_id    INTEGER NOT NULL REFERENCES regions(region_id),
    signup_date  DATE NOT NULL,
    is_active    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE orders (
    order_id         INTEGER PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(user_id),
    product_category TEXT NOT NULL,
    amount           NUMERIC(12,2) NOT NULL,
    order_date       DATE NOT NULL,
    region_id        INTEGER NOT NULL REFERENCES regions(region_id)
);

CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_orders_cat  ON orders(product_category);
