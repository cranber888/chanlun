"""AkShare 指数分钟级别数据适配器"""
import akshare as ak

from Common.CEnum import AUTYPE, DATA_FIELD, KL_TYPE
from Common.CTime import CTime
from Common.func_util import str2float
from KLine.KLine_Unit import CKLine_Unit
from DataAPI.CommonStockAPI import CCommonStockApi


PERIOD_MAP = {
    KL_TYPE.K_5M: '5',
    KL_TYPE.K_15M: '15',
    KL_TYPE.K_30M: '30',
    KL_TYPE.K_60M: '60',
}


class CAkshareIndexMin(CCommonStockApi):
    """使用 akshare index_zh_a_hist_min_em 获取A股指数分钟数据"""

    def __init__(self, code, k_type=KL_TYPE.K_5M, begin_date=None, end_date=None, autype=AUTYPE.QFQ):
        super().__init__(code, k_type, begin_date, end_date, autype)

    def get_kl_data(self):
        period = PERIOD_MAP.get(self.k_type)
        if period is None:
            raise Exception(f"AkshareIndexMin 不支持 {self.k_type} 级别")

        # 提取纯数字代码 (sh000001 -> 000001)
        symbol = self.code
        if symbol.startswith(('sh', 'sz')) and '.' not in symbol:
            symbol = symbol[2:]
        elif '.' in symbol:
            symbol = symbol.split('.')[1]

        start_date = self.begin_date + " 09:30:00" if self.begin_date else "1979-09-01 09:30:00"
        end_date = self.end_date + " 15:00:00" if self.end_date else "2222-01-01 15:00:00"

        df = ak.index_zh_a_hist_min_em(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        # 列名：时间, 开盘, 收盘, 最高, 最低, 成交量, 成交额, ...
        for _, row in df.iterrows():
            time_str = str(row.iloc[0])  # 时间列
            # 格式: "2026-03-25 09:35:00"
            year = int(time_str[:4])
            month = int(time_str[5:7])
            day = int(time_str[8:10])
            hour = int(time_str[11:13])
            minute = int(time_str[14:16])

            item = {
                DATA_FIELD.FIELD_TIME: CTime(year, month, day, hour, minute),
                DATA_FIELD.FIELD_OPEN: str2float(row.iloc[1]),   # 开盘
                DATA_FIELD.FIELD_CLOSE: str2float(row.iloc[2]),  # 收盘
                DATA_FIELD.FIELD_HIGH: str2float(row.iloc[3]),   # 最高
                DATA_FIELD.FIELD_LOW: str2float(row.iloc[4]),    # 最低
                DATA_FIELD.FIELD_VOLUME: str2float(row.iloc[7]), # 成交量
                DATA_FIELD.FIELD_TURNOVER: str2float(row.iloc[8]) if len(row) > 8 else 0,  # 成交额
            }
            yield CKLine_Unit(item)

    def SetBasciInfo(self):
        self.name = self.code
        self.is_stock = False

    @classmethod
    def do_init(cls):
        pass

    @classmethod
    def do_close(cls):
        pass
