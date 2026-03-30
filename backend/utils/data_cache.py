"""
双层缓存: 内存(快) + SQLite(持久化)
- 交易时间: 缓存 60 秒，保证数据新鲜
- 非交易时间: 缓存 24 小时，无需重新下载
"""
import json
import os
import sqlite3
import time
from collections import OrderedDict
from datetime import datetime, time as dtime, timezone, timedelta

# 北京时间 UTC+8
BJ_TZ = timezone(timedelta(hours=8))

# ============ 交易时间判断 ============

def is_trading_hours() -> bool:
    """判断当前是否在 A 股交易时段 (工作日 9:15 ~ 15:30, 北京时间)"""
    now = datetime.now(BJ_TZ)
    if now.weekday() >= 5:  # 周末
        return False
    t = now.time()
    return dtime(9, 15) <= t <= dtime(15, 30)


def get_ttl() -> int:
    """根据是否交易时间返回缓存有效期（秒）"""
    return 60 if is_trading_hours() else 86400  # 60s / 24h


# ============ SQLite 持久化层 ============

_DB_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
_DB_PATH = os.path.join(_DB_DIR, 'cache.db')
_db_conn = None


def _get_db():
    global _db_conn
    if _db_conn is None:
        os.makedirs(_DB_DIR, exist_ok=True)
        _db_conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _db_conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT,
                created_at REAL
            )
        """)
        _db_conn.commit()
    return _db_conn


def _db_get(key: str, ttl: int):
    """从 SQLite 获取数据"""
    db = _get_db()
    row = db.execute(
        "SELECT data, created_at FROM analysis_cache WHERE cache_key = ?",
        (key,)
    ).fetchone()
    if row is None:
        return None
    data_json, created_at = row
    if time.time() - created_at > ttl:
        return None  # 已过期
    return json.loads(data_json)


def _db_set(key: str, data):
    """写入 SQLite"""
    db = _get_db()
    data_json = json.dumps(data, ensure_ascii=False)
    db.execute(
        "INSERT OR REPLACE INTO analysis_cache (cache_key, data, created_at) VALUES (?, ?, ?)",
        (key, data_json, time.time())
    )
    db.commit()


def _db_clear():
    """清空 SQLite 缓存"""
    db = _get_db()
    db.execute("DELETE FROM analysis_cache")
    db.commit()


def _db_cleanup():
    """清理过期数据"""
    db = _get_db()
    # 删除超过 24 小时的数据
    cutoff = time.time() - 86400
    db.execute("DELETE FROM analysis_cache WHERE created_at < ?", (cutoff,))
    db.commit()


# ============ 内存缓存层 (快速访问) ============

_mem_cache = OrderedDict()
_MAX_MEM_SIZE = 50


# ============ 对外接口 ============

def get_cached(key: str):
    """获取缓存 (先查内存, 再查 SQLite)"""
    ttl = get_ttl()

    # 1. 内存缓存
    if key in _mem_cache:
        ts, data = _mem_cache[key]
        if time.time() - ts < ttl:
            _mem_cache.move_to_end(key)
            return data
        else:
            del _mem_cache[key]

    # 2. SQLite 缓存
    data = _db_get(key, ttl)
    if data is not None:
        # 回填内存
        _mem_cache[key] = (time.time(), data)
        while len(_mem_cache) > _MAX_MEM_SIZE:
            _mem_cache.popitem(last=False)
        return data

    return None


def set_cached(key: str, data):
    """写入缓存 (同时写内存和 SQLite)"""
    now = time.time()

    # 内存
    _mem_cache[key] = (now, data)
    _mem_cache.move_to_end(key)
    while len(_mem_cache) > _MAX_MEM_SIZE:
        _mem_cache.popitem(last=False)

    # SQLite
    _db_set(key, data)


def clear_cache():
    """清空所有缓存"""
    _mem_cache.clear()
    _db_clear()


def clear_stock_cache(code: str):
    """清空指定股票的所有缓存（用于刷新）"""
    # 内存
    keys_to_del = [k for k in _mem_cache if k.startswith(f"{code}|")]
    for k in keys_to_del:
        del _mem_cache[k]

    # SQLite
    db = _get_db()
    db.execute("DELETE FROM analysis_cache WHERE cache_key LIKE ?", (f"{code}|%",))
    db.commit()
