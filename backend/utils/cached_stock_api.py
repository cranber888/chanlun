"""
带本地缓存的股票数据源包装器

原理:
  1. 生成缓存 key: code|period|begin_date|end_date|autype
  2. 先查 SQLite 本地缓存
  3. 缓存未命中 → 调用原始数据源(BaoStock/AkShare)下载 → 存入本地
  4. 从缓存数据构建 CKLine_Unit 对象返回

这样不管怎么改笔规则/中枢规则, 原始K线都不需要重新下载。
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'chan_py_lib'))

from Common.CEnum import AUTYPE, DATA_FIELD, KL_TYPE
from Common.CTime import CTime
from KLine.KLine_Unit import CKLine_Unit
from DataAPI.CommonStockAPI import CCommonStockApi

from backend.utils.kline_cache import get_kline_cache, set_kline_cache


def _klu_to_dict(klu: CKLine_Unit) -> dict:
    """将 CKLine_Unit 转为可序列化的字典"""
    d = {
        "year": klu.time.year,
        "month": klu.time.month,
        "day": klu.time.day,
        "hour": klu.time.hour,
        "minute": klu.time.minute,
        "open": klu.open,
        "high": klu.high,
        "low": klu.low,
        "close": klu.close,
    }
    # 可选交易信息 (volume, turnover, turnover_rate)
    if hasattr(klu, 'trade_info') and klu.trade_info:
        ti = klu.trade_info
        if hasattr(ti, 'metric'):
            for field, val in ti.metric.items():
                if val is not None:
                    # field 是 DATA_FIELD 枚举, 其值就是字符串如 "volume"
                    key = field if isinstance(field, str) else field.value
                    d[key] = val
    return d


def _dict_to_klu(d: dict) -> CKLine_Unit:
    """从字典重建 CKLine_Unit"""
    kl_dict = {
        DATA_FIELD.FIELD_TIME: CTime(d["year"], d["month"], d["day"], d["hour"], d["minute"]),
        DATA_FIELD.FIELD_OPEN: d["open"],
        DATA_FIELD.FIELD_HIGH: d["high"],
        DATA_FIELD.FIELD_LOW: d["low"],
        DATA_FIELD.FIELD_CLOSE: d["close"],
    }
    # 恢复交易信息
    field_map = {
        "volume": DATA_FIELD.FIELD_VOLUME,
        "turnover": DATA_FIELD.FIELD_TURNOVER,
        "turnover_rate": DATA_FIELD.FIELD_TURNRATE,
    }
    for str_key, enum_key in field_map.items():
        if str_key in d:
            kl_dict[enum_key] = d[str_key]
    return CKLine_Unit(kl_dict)


class CCachedStockApi(CCommonStockApi):
    """
    带本地缓存的数据源包装器。
    包装任意 CCommonStockApi 实现, 在其前面加一层 SQLite 缓存。
    """

    # 保存被包装的原始 API 类和相关信息
    _inner_api_class = None
    _inner_data_src = None

    def __init__(self, code, k_type=KL_TYPE.K_DAY, begin_date=None, end_date=None, autype=AUTYPE.QFQ):
        # 不调用 super().__init__ 因为会触发 SetBasciInfo
        self.code = code
        self.k_type = k_type
        self.begin_date = begin_date
        self.end_date = end_date
        self.autype = autype
        self.name = code
        self.is_stock = True

        # 生成缓存 key
        self._cache_key = f"{code}|{k_type}|{begin_date}|{end_date}|{autype}"

    def get_kl_data(self):
        """优先从本地缓存读取, 未命中则在线下载并缓存"""
        # 1. 查缓存
        cached = get_kline_cache(self._cache_key)
        if cached is not None:
            print(f"  [K线缓存命中] {self.code} {self.k_type} ({len(cached)}根)")
            for d in cached:
                yield _dict_to_klu(d)
            return

        # 2. 缓存未命中, 用原始数据源下载
        t0 = time.time()
        inner_api = self._inner_api_class(
            self.code, self.k_type, self.begin_date, self.end_date, self.autype
        )
        # 复制基本信息
        self.name = inner_api.name
        self.is_stock = inner_api.is_stock

        raw_list = []  # 存储可序列化的字典
        klu_list = []  # 存储 CKLine_Unit
        for klu in inner_api.get_kl_data():
            raw_list.append(_klu_to_dict(klu))
            klu_list.append(klu)

        # 3. 存入本地缓存
        set_kline_cache(self._cache_key, raw_list)
        elapsed = time.time() - t0
        print(f"  [K线已下载] {self.code} {self.k_type} ({len(raw_list)}根, {elapsed:.1f}s)")

        # 4. 返回数据
        yield from klu_list

    def SetBasciInfo(self):
        """基本信息在 get_kl_data 中从内部API获取"""
        pass

    @classmethod
    def do_init(cls):
        """初始化内部数据源"""
        if cls._inner_api_class and hasattr(cls._inner_api_class, 'do_init'):
            cls._inner_api_class.do_init()

    @classmethod
    def do_close(cls):
        """关闭内部数据源"""
        if cls._inner_api_class and hasattr(cls._inner_api_class, 'do_close'):
            cls._inner_api_class.do_close()


def make_cached_api(inner_class):
    """
    工厂函数: 为指定的 API 类创建带缓存的子类。

    用法:
        CachedBaoStock = make_cached_api(CBaoStock)
    """
    cls = type(
        f"CCached_{inner_class.__name__}",
        (CCachedStockApi,),
        {
            '_inner_api_class': inner_class,
        }
    )
    return cls
