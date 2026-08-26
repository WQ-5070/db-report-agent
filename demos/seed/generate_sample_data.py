"""生成一个贴近真实业务的样例库（SQLite），用于本地零依赖演示。

产出 db-report-agent.db，包含: regions / users / orders 三张表，
数据带季节性、波动与一处异常，便于演示"自动选图 + 自然语言洞察"。

单独运行:
    python demos/seed/generate_sample_data.py
"""
from __future__ import annotations

import argparse
import os
import random
import sqlite3
from datetime import date, timedelta

# 固定随机种子 -> 数据可复现
random.seed(42)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db-report-agent.db")

REGIONS = [
    ("华东", "一线"),
    ("华南", "一线"),
    ("华北", "二线"),
    ("西南", "二线"),
    ("西北", "三线"),
]
# 各区域权重（人口/购买力越高、订单越多）——让区域分布更贴近真实
REGION_WEIGHTS = {"华东": 1.45, "华南": 1.35, "华北": 1.25, "西南": 0.9, "西北": 0.7}

CITIES = {
    "华东": ["上海", "杭州", "南京"],
    "华南": ["广州", "深圳"],
    "华北": ["北京", "天津"],
    "西南": ["成都", "重庆"],
    "西北": ["西安", "兰州"],
}

PRODUCT_CATEGORIES = ["数码", "家电", "服饰", "食品", "美妆"]
# 客单价乘数：令数码/家电贡献更高销售额，食品走量但单价低
CATEGORY_PRICE_MULT = {
    "数码": 1.7, "家电": 1.6, "美妆": 1.25, "服饰": 1.1, "食品": 0.8,
}


def build(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
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
            region_id    INTEGER NOT NULL,
            signup_date  TEXT NOT NULL,
            is_active    INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE orders (
            order_id        INTEGER PRIMARY KEY,
            user_id         INTEGER NOT NULL,
            product_category TEXT NOT NULL,
            amount          REAL NOT NULL,
            order_date      TEXT NOT NULL,
            region_id       INTEGER NOT NULL
        );
        CREATE INDEX idx_orders_date ON orders(order_date);
        CREATE INDEX idx_orders_cat  ON orders(product_category);
        """
    )

    # regions
    cur.executemany(
        "INSERT INTO regions(region_id, region_name, tier) VALUES (?,?,?)",
        [(i + 1, name, tier) for i, (name, tier) in enumerate(REGIONS)],
    )
    region_id = {name: i + 1 for i, (name, _) in enumerate(REGIONS)}

    # 按区域权重取一个区域（返回区域名）
    def pick_region() -> str:
        names = list(REGION_WEIGHTS.keys())
        weights = list(REGION_WEIGHTS.values())
        return random.choices(names, weights=weights, k=1)[0]

    # users
    users = []
    for uid in range(1, 501):
        region_name = pick_region()
        city = random.choice(CITIES[region_name])
        signup = date(2022, 1, 1) + timedelta(days=random.randint(0, 900))
        is_active = 1 if random.random() < 0.78 else 0
        users.append((uid, f"user_{uid}", city, region_id[region_name],
                      signup.isoformat(), is_active))
    cur.executemany("INSERT INTO users VALUES (?,?,?,?,?,?)", users)

    # orders: 24 个月，带季节性 + 一处异常(电商旺季 + 某月骤降)
    oid = 1
    base_date = date(2023, 1, 1)
    for m in range(24):
        year = base_date.year + (base_date.month - 1 + m) // 12
        month = (base_date.month - 1 + m) % 12 + 1
        month_start = date(year, month, 1)

        # 季节性系数 + 年度增长
        season = {"1": 1.1, "2": 0.85, "3": 1.0, "4": 1.0, "5": 1.05,
                  "6": 1.15, "7": 0.95, "8": 1.0, "9": 1.0, "10": 1.2,
                  "11": 1.35, "12": 1.6}[str(month)]
        growth = 1.0 + m * 0.015
        # 一处异常: 2024-04 数据骤降 (供"归因/异常"演示)
        if (year, month) == (2024, 4):
            factor = 0.5
        else:
            factor = 1.0

        orders_this_month = int(80 * season * growth * factor)
        for _ in range(orders_this_month):
            day = month_start + timedelta(days=random.randint(0, 27))
            order_date = day.isoformat() if day <= month_start + timedelta(days=30) else month_start.replace(day=28).isoformat()
            if day.month != month:  # 兜底: 不超过当月
                day = month_start.replace(day=random.randint(1, 28))
                order_date = day.isoformat()
            user = random.choice(users)
            region_name = REGIONS[user[3] - 1][0]
            category = random.choice(PRODUCT_CATEGORIES)
            amount = round(
                random.uniform(50, 3000) * CATEGORY_PRICE_MULT[category]
                * (2.0 if random.random() < 0.1 else 1.0),
                2,
            )
            cur.execute(
                "INSERT INTO orders(order_id, user_id, product_category, amount, order_date, region_id) "
                "VALUES (?,?,?,?,?,?)",
                (oid, user[0], category, amount, order_date, user[3]),
            )
            oid += 1

    conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 db-report-agent 样例库（确定性，random.seed(42)）")
    parser.add_argument("--output", default=DB_PATH,
                        help="样例库输出路径（默认 demos/db-report-agent.db）")
    args = parser.parse_args(argv)
    path = args.output
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with sqlite3.connect(path) as conn:
        build(conn)
    # 统计
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        n_orders = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        n_users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    print(f"生成样例库成功: {os.path.abspath(path)}")
    print(f"  users  = {n_users}")
    print(f"  orders = {n_orders}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
