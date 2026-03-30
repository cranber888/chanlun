"""缠论分析服务 - 封装 chan.py 的 CChan 调用（带K线本地缓存）"""
import sys
import os
import time

# 将 chan_py_lib 加入 Python 路径
CHAN_LIB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'chan_py_lib')
sys.path.insert(0, CHAN_LIB_PATH)

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from backend.utils.chan_serializer import serialize_kline_list
from backend.utils.data_cache import get_cached, set_cached, clear_stock_cache, is_trading_hours
from backend.utils.cached_stock_api import make_cached_api
from backend.utils.kline_cache import clear_kline_cache

# 将自定义 AkShare 适配器注册到 DataAPI 命名空间（CChan custom: 机制需要）
import backend.utils.akshare_min_api as _ak_min_mod
sys.modules["DataAPI.AkshareMinAPI"] = _ak_min_mod

import backend.utils.akshare_index_daily_api as _ak_idx_daily_mod
sys.modules["DataAPI.AkshareIndexDailyAPI"] = _ak_idx_daily_mod

KL_TYPE_MAP = {
    "K_5M": KL_TYPE.K_5M,
    "K_15M": KL_TYPE.K_15M,
    "K_30M": KL_TYPE.K_30M,
    "K_60M": KL_TYPE.K_60M,
    "K_DAY": KL_TYPE.K_DAY,
    "K_WEEK": KL_TYPE.K_WEEK,
    "K_MON": KL_TYPE.K_MON,
}

KL_TYPE_LABELS = {
    "K_5M": "5分钟",
    "K_15M": "15分钟",
    "K_30M": "30分钟",
    "K_60M": "60分钟",
    "K_DAY": "日线",
    "K_WEEK": "周线",
    "K_MON": "月线",
}

# 分钟级别统一用 AkShare（实时数据），日线及以上用 AkShare/BaoStock
MINUTE_LEVELS = {"K_5M", "K_15M", "K_30M", "K_60M"}


# ============ 带缓存的 CChan 子类 ============

class CCachedChan(CChan):
    """
    继承 CChan, 覆写 GetStockAPI 方法, 让所有数据源自动带本地缓存。
    这样原始K线只下载一次, 后续改规则不需要重新下载。
    """
    def GetStockAPI(self):
        # 获取原始 API 类
        original_cls = super().GetStockAPI()
        # 包装为带缓存的版本
        return make_cached_api(original_cls)


# ============ 辅助函数 ============

def get_data_src_for_level(period: str, market: str, is_index: bool = False):
    """返回数据源标识（DATA_SRC 枚举或 custom: 字符串）"""
    if market == "HK":
        return DATA_SRC.AKSHARE
    if period in MINUTE_LEVELS:
        # 分钟数据统一用 AkShare 东财接口（个股+指数都支持，当天实时）
        return "custom:AkshareMinAPI.CAkshareMin"
    if is_index:
        # 指数日线用 AkShare 东财接口（当天实时）
        return "custom:AkshareIndexDailyAPI.CAkshareIndexDaily"
    return DATA_SRC.AKSHARE


def is_index_code(code: str) -> bool:
    """判断是否为指数代码"""
    if code.startswith(("sh", "sz")):
        num = code[2:]
        return num.startswith(("000", "399"))
    return False


def format_code_for_src(code: str, data_src, market: str) -> str:
    """根据数据源格式化股票代码"""
    if market == "HK":
        return code
    # custom 数据源（指数分钟）直接用原始代码
    if isinstance(data_src, str):
        return code
    if data_src == DATA_SRC.BAO_STOCK:
        # BaoStock 需要 sh.600000 或 sz.000001 格式
        if code.startswith(("sh", "sz")) and "." not in code:
            return code[:2] + "." + code[2:]
        if code.isdigit():
            prefix = "sh" if code.startswith(("6", "5", "9")) else "sz"
            return f"{prefix}.{code}"
        return code
    else:
        # AkShare 用纯数字，但指数需要保留前缀
        if is_index_code(code):
            return code
        if "." in code:
            return code.split(".")[1]
        if code.startswith(("sh", "sz")):
            return code[2:]
        return code


# ============ 主分析函数 ============

def analyze_stock(
    code: str,
    period: str = "K_DAY",
    begin_time: str = None,
    market: str = "A",
    # 笔规则参数
    bi_strict: bool = True,
    bi_fx_check: str = "strict",
    gap_as_kl: bool = False,
    bi_end_is_peak: bool = True,
    bi_allow_sub_peak: bool = True,
    # 中枢规则参数
    zs_max_bi_cnt: int = 0,
) -> dict:
    """对指定股票进行缠论分析（带双层缓存: K线缓存 + 分析结果缓存）"""
    kl_type = KL_TYPE_MAP.get(period)
    if kl_type is None:
        raise ValueError(f"不支持的周期: {period}")

    # 生成完整缓存 key（包含所有影响结果的参数）
    cache_key = (
        f"{code}|{period}|{begin_time}|{market}|"
        f"{bi_strict}|{bi_fx_check}|{gap_as_kl}|{bi_end_is_peak}|{bi_allow_sub_peak}|"
        f"{zs_max_bi_cnt}"
    )

    # 1. 尝试从分析结果缓存获取（完全命中, 最快）
    cached = get_cached(cache_key)
    if cached is not None:
        print(f"[结果缓存命中] {code} {period}")
        return cached

    t0 = time.time()

    idx = is_index_code(code)
    data_src = get_data_src_for_level(period, market, is_index=idx)
    formatted_code = format_code_for_src(code, data_src, market)

    config = CChanConfig({
        # 笔规则（可配置）
        "bi_strict": bi_strict,
        "bi_fx_check": bi_fx_check,
        "gap_as_kl": gap_as_kl,
        "bi_end_is_peak": bi_end_is_peak,
        "bi_allow_sub_peak": bi_allow_sub_peak,
        # 线段和中枢
        "seg_algo": "chan",
        "zs_combine": True,
        "zs_max_bi_cnt": zs_max_bi_cnt,
        # 买卖点
        "divergence_rate": 0.9,
        "bs_type": "1,1p,2,2s,3a,3b",
        # 技术指标：均线 + 布林带
        "mean_metrics": [5, 10, 20, 60],
        "boll_n": 20,
        # 静默
        "print_warning": False,
        "print_err_time": False,
    })

    # 2. 使用带缓存的 CCachedChan（K线数据自动本地缓存）
    chan = CCachedChan(
        code=formatted_code,
        begin_time=begin_time,
        end_time=None,
        data_src=data_src,
        lv_list=[kl_type],
        config=config,
        autype=AUTYPE.QFQ,
    )

    result = serialize_kline_list(chan[0])
    result["code"] = code
    result["period"] = period
    result["period_label"] = KL_TYPE_LABELS.get(period, period)

    # 3. 存入分析结果缓存
    set_cached(cache_key, result)
    print(f"[分析完成] {code} {period} 耗时 {time.time()-t0:.1f}s")

    return result
