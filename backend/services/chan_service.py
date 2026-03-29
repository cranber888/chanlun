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


def get_data_src_for_level(period: str, market: str) -> DATA_SRC:
    if market == "HK":
        return DATA_SRC.AKSHARE
    if period in MINUTE_LEVELS:
        return DATA_SRC.BAO_STOCK
    return DATA_SRC.AKSHARE


def format_code_for_src(code: str, data_src: DATA_SRC, market: str) -> str:
    """根据数据源格式化股票代码"""
    if market == "HK":
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
        # AkShare 用纯数字
        if "." in code:
            return code.split(".")[1]
        if code.startswith(("sh", "sz")):
            return code[2:]
        return code


def analyze_stock(code: str, period: str = "K_DAY", begin_time: str = None, market: str = "A") -> dict:
    """对指定股票进行缠论分析"""
    kl_type = KL_TYPE_MAP.get(period)
    if kl_type is None:
        raise ValueError(f"不支持的周期: {period}")

    data_src = get_data_src_for_level(period, market)
    formatted_code = format_code_for_src(code, data_src, market)

    config = CChanConfig({
        "bi_strict": True,
        "seg_algo": "chan",
        "zs_combine": True,
        "divergence_rate": 0.9,
        "bs_type": "1,1p,2,2s,3a,3b",
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
