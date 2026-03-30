"""缠论分析 Web 应用 - FastAPI 后端"""
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

# 北京时间 UTC+8
BJ_TZ = timezone(timedelta(hours=8))

from typing import List

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# 确保 chan_py_lib 在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'chan_py_lib'))

from backend.services.chan_service import analyze_stock, KL_TYPE_LABELS
from backend.services.backtest_service import run_backtest
from backend.services.watchlist_service import get_watchlist, add_to_watchlist, remove_from_watchlist
from backend.services.market_service import search_stocks, preload_stock_list
from backend.utils.data_cache import clear_stock_cache, clear_cache, is_trading_hours
from backend.utils.kline_cache import clear_kline_cache, get_cache_stats

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
    # 中枢规则参数
    zs_max_bi_cnt: int = Query(0, description="中枢最大笔数(0=不限)"),
):
    # 根据周期自动调整回溯时长
    # 日线及以上: 12个月, 日线以下: 6个月
    period_months_map = {
        "K_5M": 6,
        "K_15M": 6,
        "K_30M": 6,
        "K_60M": 6,
        "K_DAY": 12,
        "K_WEEK": 12,
        "K_MON": 12,
    }
    actual_months = period_months_map.get(period, months)
    begin_time = (datetime.now(BJ_TZ) - timedelta(days=actual_months * 30)).strftime("%Y-%m-%d")
    try:
        result = analyze_stock(
            code, period=period, begin_time=begin_time, market=market,
            bi_strict=bi_strict, bi_fx_check=bi_fx_check,
            gap_as_kl=gap_as_kl, bi_end_is_peak=bi_end_is_peak,
            bi_allow_sub_peak=bi_allow_sub_peak,
            zs_max_bi_cnt=zs_max_bi_cnt,
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


# ---- 回测接口 ----

class BacktestRequest(BaseModel):
    code: str
    period: str = "K_DAY"
    market: str = "A"
    initial_capital: float = 100000
    position_ratio: float = 1.0
    commission_rate: float = 0.001
    stamp_tax_rate: float = 0.001
    stop_loss_pct: float = 0.0
    buy_types: List[str] = Field(default_factory=lambda: ["1"])
    sell_types: List[str] = Field(default_factory=lambda: ["1"])
    # 笔规则
    bi_strict: bool = True
    bi_fx_check: str = "strict"
    gap_as_kl: bool = False
    bi_end_is_peak: bool = True
    bi_allow_sub_peak: bool = True
    zs_max_bi_cnt: int = 0


@app.post("/api/backtest")
async def api_backtest(req: BacktestRequest):
    """运行缠论回测"""
    try:
        # 回测用更长时间数据
        period_months_map = {
            "K_5M": 6, "K_15M": 6, "K_30M": 6, "K_60M": 6,
            "K_DAY": 12, "K_WEEK": 12, "K_MON": 12,
        }
        actual_months = period_months_map.get(req.period, 12)
        begin_time = (datetime.now(BJ_TZ) - timedelta(days=actual_months * 30)).strftime("%Y-%m-%d")

        # 1. 先获取分析结果
        analysis = analyze_stock(
            req.code, period=req.period, begin_time=begin_time, market=req.market,
            bi_strict=req.bi_strict, bi_fx_check=req.bi_fx_check,
            gap_as_kl=req.gap_as_kl, bi_end_is_peak=req.bi_end_is_peak,
            bi_allow_sub_peak=req.bi_allow_sub_peak,
            zs_max_bi_cnt=req.zs_max_bi_cnt,
        )

        # 2. 运行回测
        result = run_backtest(
            analysis_data=analysis,
            initial_capital=req.initial_capital,
            position_ratio=req.position_ratio,
            commission_rate=req.commission_rate,
            stamp_tax_rate=req.stamp_tax_rate,
            stop_loss_pct=req.stop_loss_pct,
            buy_types=req.buy_types,
            sell_types=req.sell_types,
        )
        if "error" in result:
            return {"ok": False, "error": result["error"]}
        return {"ok": True, "data": result}
    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


# ---- 刷新接口 ----

@app.post("/api/refresh/{code}")
async def api_refresh(code: str):
    """清除指定股票的缓存（分析结果 + 原始K线），下次请求会重新从网络下载"""
    clear_stock_cache(code)
    clear_kline_cache(code)
    return {"ok": True, "message": f"已清除 {code} 的缓存"}


@app.post("/api/refresh")
async def api_refresh_all():
    """清除所有缓存（分析结果 + 原始K线）"""
    clear_cache()
    clear_kline_cache()
    return {"ok": True, "message": "已清除所有缓存"}


@app.get("/api/cache_stats")
async def api_cache_stats():
    """查看K线数据缓存统计"""
    stats = get_cache_stats()
    return {"ok": True, "data": stats}


@app.get("/api/trading_status")
async def api_trading_status():
    """返回当前是否交易时间"""
    return {"ok": True, "is_trading": is_trading_hours()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
