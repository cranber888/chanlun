"""缠论分析服务 - 封装 chan.py 的 CChan 调用"""
import sys
import os

# 将 chan_py_lib 加入 Python 路径
CHAN_LIB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'chan_py_lib')
sys.path.insert(0, CHAN_LIB_PATH)

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from backend.utils.chan_serializer import serialize_kline_list

# 将自定义指数分钟适配器注册到 DataAPI 命名空间（CChan custom: 机制需要）
import backend.utils.akshare_index_min_api as _idx_min_mod
import sys
sys.modules["DataAPI.AkshareIndexMinAPI"] = _idx_min_mod

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

# 分钟级别用 BaoStock，日线及以上用 AkShare
MINUTE_LEVELS = {"K_5M", "K_15M", "K_30M", "K_60M"}


def get_data_src_for_level(period: str, market: str, is_index: bool = False):
    """返回数据源标识（DATA_SRC 枚举或 custom: 字符串）"""
    if market == "HK":
        return DATA_SRC.AKSHARE
    if is_index:
        if period in MINUTE_LEVELS:
            # 指数分钟数据用 AkShare 专用适配器
            return "custom:AkshareIndexMinAPI.CAkshareIndexMin"
        # 指数日线及以上用 BaoStock（AkShare 指数日线接口有日期类型兼容问题）
        return DATA_SRC.BAO_STOCK
    if period in MINUTE_LEVELS:
        return DATA_SRC.BAO_STOCK
    return DATA_SRC.AKSHARE


def is_index_code(code: str) -> bool:
    """判断是否为指数代码"""
    # sh000001(上证指数), sz399001(深证成指), sh000300(沪深300) 等
    if code.startswith(("sh", "sz")):
        num = code[2:]
        return num.startswith(("000", "399"))
    # 纯数字: 000001 可能是平安银行也可能是上证指数，需要前缀区分
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
            return code  # AkShare 指数用 sh000001 格式
        if "." in code:
            return code.split(".")[1]
        if code.startswith(("sh", "sz")):
            return code[2:]
        return code


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
) -> dict:
    """对指定股票进行缠论分析"""
    kl_type = KL_TYPE_MAP.get(period)
    if kl_type is None:
        raise ValueError(f"不支持的周期: {period}")

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

    chan = CChan(
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
    return result
