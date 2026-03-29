"""股票搜索服务"""

_stock_list_cache = None


def get_a_stock_list():
    """获取 A 股股票列表（带缓存，懒加载 akshare）"""
    global _stock_list_cache
    if _stock_list_cache is not None:
        return _stock_list_cache
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        result = []
        for _, row in df.iterrows():
            result.append({
                "code": str(row["代码"]),
                "name": str(row["名称"]),
                "market": "A",
            })
        _stock_list_cache = result
        return result
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return []


def search_stocks(keyword: str, limit: int = 20) -> list:
    """搜索股票（代码或名称模糊匹配）"""
    stocks = get_a_stock_list()
    results = []
    kw = keyword.upper()
    for s in stocks:
        if kw in s["code"] or kw in s["name"].upper():
            results.append(s)
            if len(results) >= limit:
                break
    return results
