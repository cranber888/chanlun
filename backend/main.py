"""缠论分析 Web 应用 - FastAPI 后端"""
import os
import sys
import traceback
from datetime import datetime, timedelta

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# 确保 chan_py_lib 在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'chan_py_lib'))

from backend.services.chan_service import analyze_stock, KL_TYPE_LABELS
from backend.services.watchlist_service import get_watchlist, add_to_watchlist, remove_from_watchlist
from backend.services.market_service import search_stocks, preload_stock_list

app = FastAPI(title="缠论分析系统")


@app.on_event("startup")
async def startup_event():
    """服务器启动时后台预加载股票列表"""
    preload_stock_list()


# 静态文件
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'static')
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, '..', 'index.html'))


# ---- 分析接口 ----

@app.get("/api/analysis/{code}")
async def api_analysis(
    code: str,
    period: str = Query("K_DAY", description="K线周期"),
    months: int = Query(12, description="回溯月数"),
    market: str = Query("A", description="市场: A/HK"),
    # 笔规则参数
    bi_strict: bool = Query(True, description="严格笔"),
    bi_fx_check: str = Query("strict", description="分型检查: strict/loss/half/totally"),
    gap_as_kl: bool = Query(False, description="跳空缺口算K线"),
    bi_end_is_peak: bool = Query(True, description="笔尾必须是极值"),
    bi_allow_sub_peak: bool = Query(True, description="允许次高低点"),
):
    begin_time = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
    try:
        result = analyze_stock(
            code, period=period, begin_time=begin_time, market=market,
            bi_strict=bi_strict, bi_fx_check=bi_fx_check,
            gap_as_kl=gap_as_kl, bi_end_is_peak=bi_end_is_peak,
            bi_allow_sub_peak=bi_allow_sub_peak,
        )
        return {"ok": True, "data": result}
    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


@app.get("/api/periods")
async def api_periods():
    return {"ok": True, "data": [{"value": k, "label": v} for k, v in KL_TYPE_LABELS.items()]}


# ---- 自选股接口 ----

@app.get("/api/watchlist")
async def api_get_watchlist():
    return {"ok": True, "data": get_watchlist()}


class WatchlistAdd(BaseModel):
    code: str
    name: str
    market: str = "A"


@app.post("/api/watchlist")
async def api_add_watchlist(item: WatchlistAdd):
    data = add_to_watchlist(item.code, item.name, item.market)
    return {"ok": True, "data": data}


@app.delete("/api/watchlist/{code}")
async def api_remove_watchlist(code: str):
    data = remove_from_watchlist(code)
    return {"ok": True, "data": data}


# ---- 搜索接口 ----

@app.get("/api/search")
async def api_search(q: str = Query("", min_length=1)):
    results = search_stocks(q)
    return {"ok": True, "data": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
