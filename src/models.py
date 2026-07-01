"""Models — SQLite 数据模型，存储企业状态和变更记录."""
import sqlite3
import json
from datetime import datetime
from config import DB_PATH


def get_connection():
    """获取数据库连接."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构."""
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        -- 公司表
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            ticker TEXT NOT NULL,
            cik TEXT,
            industry TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- 申报文件表
        CREATE TABLE IF NOT EXISTS filings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            filing_type TEXT NOT NULL DEFAULT '10-K',
            filing_date TEXT,
            source_url TEXT,
            file_path TEXT,
            processed_at TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (company_id) REFERENCES companies(id),
            UNIQUE(company_id, year, filing_type)
        );

        -- 企业对象表（核心：存储每个时间点的状态）
        CREATE TABLE IF NOT EXISTS enterprise_objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filing_id INTEGER NOT NULL,
            object_type TEXT NOT NULL,   -- doctrine/capability/strategy/risk/obligation/decision
            object_id TEXT,              -- 原始 ID，如 risk_1
            content TEXT NOT NULL,
            confidence TEXT DEFAULT 'medium',
            category TEXT,               -- 子类别
            metadata TEXT,               -- JSON 额外字段
            FOREIGN KEY (filing_id) REFERENCES filings(id)
        );

        -- 财务数据表
        CREATE TABLE IF NOT EXISTS financial_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filing_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,    -- revenue/net_income/etc
            value REAL,
            currency TEXT DEFAULT 'USD',
            note TEXT,
            FOREIGN KEY (filing_id) REFERENCES filings(id),
            UNIQUE(filing_id, metric_name)
        );

        -- 变更记录表（对比引擎的输出）
        CREATE TABLE IF NOT EXISTS changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            object_type TEXT NOT NULL,
            year_from INTEGER,
            year_to INTEGER,
            change_type TEXT NOT NULL,    -- added/removed/modified/persisted
            content_before TEXT,
            content_after TEXT,
            significance TEXT DEFAULT 'medium',
            metadata TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );

        -- 索引
        CREATE INDEX IF NOT EXISTS idx_objects_filing ON enterprise_objects(filing_id);
        CREATE INDEX IF NOT EXISTS idx_objects_type ON enterprise_objects(object_type);
        CREATE INDEX IF NOT EXISTS idx_changes_company ON changes(company_id);
        CREATE INDEX IF NOT EXISTS idx_financials_filing ON financial_metrics(filing_id);
    """)

    conn.commit()
    conn.close()


def upsert_company(name, ticker, cik=None):
    """插入或获取公司."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO companies (name, ticker, cik) VALUES (?, ?, ?)",
        (name, ticker, cik)
    )
    cur.execute("SELECT id FROM companies WHERE name = ?", (name,))
    company_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return company_id


def upsert_filing(company_id, year, filing_type="10-K", filing_date=None, source_url=None, file_path=None):
    """插入或获取申报记录."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT OR IGNORE INTO filings
           (company_id, year, filing_type, filing_date, source_url, file_path)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (company_id, year, filing_type, filing_date, source_url, file_path)
    )
    cur.execute(
        "SELECT id FROM filings WHERE company_id = ? AND year = ? AND filing_type = ?",
        (company_id, year, filing_type)
    )
    row = cur.fetchone()
    filing_id = row["id"] if row else None
    conn.commit()
    conn.close()
    return filing_id


def store_extraction_result(filing_id, extracted):
    """存储 LLM 提取结果到数据库."""
    conn = get_connection()
    cur = conn.cursor()

    objects = extracted.get("enterprise_objects", {})

    # 存储企业对象
    for obj_type, items in objects.items():
        if obj_type == "financial_health":
            continue  # 单独处理
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            cur.execute(
                """INSERT INTO enterprise_objects
                   (filing_id, object_type, object_id, content, confidence, category, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    filing_id,
                    obj_type,
                    item.get("id", ""),
                    item.get("content", ""),
                    item.get("confidence", "medium"),
                    item.get("category", item.get("type", "")),
                    json.dumps({k: v for k, v in item.items()
                                if k not in ("id", "content", "confidence", "category", "type")},
                               ensure_ascii=False)
                )
            )

    # 存储财务数据
    financials = objects.get("financial_health", {})
    if isinstance(financials, dict):
        metric_map = {
            "revenue": "revenue",
            "operating_income": "operating_income",
            "net_income": "net_income",
            "rd_spend": "rd_spend",
            "cash_and_equivalents": "cash_and_equivalents",
            "total_assets": "total_assets",
            "total_liabilities": "total_liabilities",
        }
        for metric_key, db_key in metric_map.items():
            metric_data = financials.get(metric_key, {})
            if isinstance(metric_data, dict) and metric_data.get("value") is not None:
                cur.execute(
                    """INSERT OR REPLACE INTO financial_metrics
                       (filing_id, metric_name, value, currency, note)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        filing_id,
                        db_key,
                        metric_data["value"],
                        metric_data.get("currency", "USD"),
                        metric_data.get("note", ""),
                    )
                )

    # 更新申报处理状态
    cur.execute(
        "UPDATE filings SET status = 'processed', processed_at = datetime('now') WHERE id = ?",
        (filing_id,)
    )

    conn.commit()
    conn.close()


def get_filing_by_id(filing_id):
    """获取单条申报记录."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT f.*, c.name as company_name, c.ticker
        FROM filings f
        JOIN companies c ON f.company_id = c.id
        WHERE f.id = ?
    """, (filing_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_objects_for_filing(filing_id):
    """获取某次申报的所有企业对象."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM enterprise_objects WHERE filing_id = ?",
        (filing_id,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_financials_for_filing(filing_id):
    """获取某次申报的财务数据."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM financial_metrics WHERE filing_id = ?",
        (filing_id,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {r["metric_name"]: r for r in rows}


def init_if_needed():
    """如果数据库不存在则初始化."""
    if not DB_PATH.exists():
        init_db()
        print(f"  📦 数据库已创建: {DB_PATH}")


if __name__ == "__main__":
    init_db()
    print(f"✅ 数据库初始化完成: {DB_PATH}")
