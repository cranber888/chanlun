"""
原始K线数据本地缓存 (SQLite)

功能:
  - 首次请求: 从 BaoStock/AkShare 在线下载 → 存入 SQLite → 返回数据
  - 后续请求: 直接从 SQLite 读取, 跳过网络下载
  - 交易时间内缓存较短 (10分钟), 保证数据新鲜
  - 非交易时间缓存较长 (24小时)
  - 手动刷新可清除缓存
"""
import os
import sqlite3
import time
from datetime import datetime, time as dtime, timezone, timedelta

# 北京时间 UTC+8
_BJ_TZ = timezone(timedelta(hours=8))

# ============ 配置 ============

_DB_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
_DB_PATH = os.path.join(_DB_DIR, 'kline_data.db')
_db_conn = None


def _get_db():
    """获取/初始化 SQLite 连接"""
    global _db_conn
    if _db_conn is None:
        os.makedirs(_DB_DIR, exist_ok=True)
        _db_conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _db_conn.execute("""
            CREATE TABLE IF NOT EXISTS kline_raw (
                cache_key TEXT PRIMARY KEY,
                data TEXT,
                created_at REAL
            )
        """)
        _db_conn.commit()
    return _db_conn


# ============ 交易时间判断 ============

def _is_trading_hours() -> bool:
    now = datetime.now(_BJ_TZ)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dtime(9, 15) <= t <= dtime(15, 30)


def _get_ttl() -> int:
    """K线数据缓存有效期"""
    return 120 if _is_trading_hours() else 86400  # 交易中2分钟, 非交易24小时


# ============ 缓存操作 ============

def get_kline_cache(key: str):
    """从本地获取K线数据, 返回 list[dict] 或 None"""
    import json
    db = _get_db()
    ttl = _get_ttl()
    row = db.execute(
        "SELECT data, created_at FROM kline_raw WHERE cache_key = ?",
        (key,)
    ).fetchone()
    if row is None:
        return None
    data_json, created_at = row
    if time.time() - created_at > ttl:
        return None  # 已过期
    return json.loads(data_json)


def set_kline_cache(key: str, data: list):
    """存储K线数据到本地"""
    import json
    db = _get_db()
    data_json = json.dumps(data, ensure_ascii=False)
    db.execute(
        "INSERT OR REPLACE INTO kline_raw (cache_key, data, created_at) VALUES (?, ?, ?)",
        (key, data_json, time.time())
    )
    db.commit()


def clear_kline_cache(code: str = None):
    """清除K线缓存, code=None 清除全部

    code 可能是 '600519', 'sh.600519', 'sh600519' 等格式,
    需要匹配所有包含该股票代码数字部分的缓存。
    """
    db = _get_db()
    if code:
        # 提取纯数字部分用于模糊匹配
        digits = ''.join(c for c in code if c.isdigit())
        if digits:
            db.execute("DELETE FROM kline_raw WHERE cache_key LIKE ?", (f"%{digits}%",))
        else:
            db.execute("DELETE FROM kline_raw WHERE cache_key LIKE ?", (f"%{code}%",))
    else:
        db.execute("DELETE FROM kline_raw")
    db.commit()


def get_cache_stats():
    """获取缓存统计信息"""
    db = _get_db()
    row = db.execute("SELECT COUNT(*), SUM(LENGTH(data)) FROM kline_raw").fetchone()
    count = row[0] or 0
    size_bytes = row[1] or 0
    return {"count": count, "size_mb": round(size_bytes / 1024 / 1024, 2)}
