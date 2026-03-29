"""股票搜索服务"""
import json
import os
import time
import threading
from pypinyin import lazy_pinyin, Style

_stock_list_cache = None
_cache_lock = threading.Lock()

# 磁盘缓存路径（重启服务器不用重新下载）
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
CACHE_FILE = os.path.join(CACHE_DIR, 'stock_list_cache.json')
CACHE_MAX_AGE = 4 * 3600  # 缓存4小时过期

# A股主要指数（内置，不需要网络请求）
INDEX_LIST = [
    {"code": "sh000001", "name": "上证指数", "market": "A"},
    {"code": "sz399001", "name": "深证成指", "market": "A"},
    {"code": "sz399006", "name": "创业板指", "market": "A"},
    {"code": "sh000300", "name": "沪深300", "market": "A"},
    {"code": "sh000016", "name": "上证50", "market": "A"},
    {"code": "sh000905", "name": "中证500", "market": "A"},
    {"code": "sh000852", "name": "中证1000", "market": "A"},
    {"code": "sz399303", "name": "国证2000", "market": "A"},
    {"code": "sh000688", "name": "科创50", "market": "A"},
    {"code": "sz399673", "name": "创业板50", "market": "A"},
    {"code": "sh000010", "name": "上证180", "market": "A"},
    {"code": "sh000903", "name": "中证100", "market": "A"},
    {"code": "sz399005", "name": "中小板指", "market": "A"},
    {"code": "sz399300", "name": "沪深300", "market": "A"},
    {"code": "sh000011", "name": "基金指数", "market": "A"},
]

# 给指数预生成拼音缩写
for _item in INDEX_LIST:
    _item["pinyin"] = ''.join(lazy_pinyin(_item["name"], style=Style.FIRST_LETTER))


def _get_pinyin(name: str) -> str:
    """获取中文名称的拼音首字母缩写"""
    return ''.join(lazy_pinyin(name, style=Style.FIRST_LETTER))


def _load_disk_cache():
    """从磁盘加载缓存"""
    try:
        if os.path.exists(CACHE_FILE):
            mtime = os.path.getmtime(CACHE_FILE)
            if time.time() - mtime < CACHE_MAX_AGE:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"从磁盘缓存加载了 {len(data)} 只股票")
                return data
    except Exception as e:
        print(f"读取磁盘缓存失败: {e}")
    return None


def _save_disk_cache(data):
    """保存缓存到磁盘"""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"已缓存 {len(data)} 只股票到磁盘")
    except Exception as e:
        print(f"保存磁盘缓存失败: {e}")


def _fetch_stock_list():
    """从网络获取股票列表"""
    import akshare as ak
    df = ak.stock_zh_a_spot_em()
    result = []
    for _, row in df.iterrows():
        name = str(row["名称"])
        result.append({
            "code": str(row["代码"]),
            "name": name,
            "market": "A",
            "pinyin": _get_pinyin(name),
        })
    return result


def get_a_stock_list():
    """获取 A 股股票列表（内存缓存 → 磁盘缓存 → 网络下载）"""
    global _stock_list_cache
    if _stock_list_cache is not None:
        return _stock_list_cache

    with _cache_lock:
        # 二次检查（另一个线程可能已经加载好了）
        if _stock_list_cache is not None:
            return _stock_list_cache

        # 尝试磁盘缓存
        cached = _load_disk_cache()
        if cached:
            _stock_list_cache = cached
            return _stock_list_cache

        # 从网络下载
        try:
            print("正在从网络下载A股股票列表（首次需要1-2分钟）...")
            result = _fetch_stock_list()
            _stock_list_cache = result
            _save_disk_cache(result)
            return result
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return []


def preload_stock_list():
    """后台预加载股票列表（服务器启动时调用）"""
    def _preload():
        get_a_stock_list()
        print("股票列表预加载完成")
    t = threading.Thread(target=_preload, daemon=True)
    t.start()


def search_stocks(keyword: str, limit: int = 20) -> list:
    """搜索股票和指数（代码、名称、拼音缩写模糊匹配）"""
    results = []
    kw = keyword.upper()
    kw_lower = keyword.lower()

    # 先搜指数
    for s in INDEX_LIST:
        if kw in s["code"].upper() or kw in s["name"].upper() or kw_lower in s.get("pinyin", ""):
            results.append({"code": s["code"], "name": s["name"], "market": s["market"]})

    # 再搜个股
    stocks = get_a_stock_list()
    for s in stocks:
        if kw in s["code"] or kw in s["name"].upper() or kw_lower in s.get("pinyin", ""):
            results.append({"code": s["code"], "name": s["name"], "market": s["market"]})
            if len(results) >= limit:
                break
    return results
