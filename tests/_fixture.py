"""测试夹具：创建自包含的临时 SQLite 库（含敏感列，供护栏测试）。"""
from __future__ import annotations

import sqlite3


def make_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE regions (
            region_id INTEGER PRIMARY KEY, region_name TEXT, tier TEXT
        );
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY, user_name TEXT, phone TEXT,
            city TEXT, region_id INTEGER, is_active INTEGER
        );
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY, user_id INTEGER,
            product_category TEXT, amount REAL, order_date TEXT, region_id INTEGER
        );
        INSERT INTO regions VALUES (1, '华东', '一线');
        INSERT INTO users VALUES (1, 'u1', '13800000000', '上海', 1, 1);
        INSERT INTO orders VALUES (1, 1, '数码', 100.0, '2024-01-05', 1);
        INSERT INTO orders VALUES (2, 1, '家电', 200.0, '2024-02-10', 1);
        """
    )
    conn.commit()
    conn.close()
