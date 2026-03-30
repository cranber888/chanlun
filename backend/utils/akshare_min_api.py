"""AkShare 分钟级别数据适配器（个股 + 指数，实时数据）"""
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


class CAkshareMin(CCommonStockApi):
    """使用 AkShare 东方财富接口获取A股分钟数据（个股+指数，当天实时）"""

    def __init__(self, code, k_type=KL_TYPE.K_5M, begin_date=None, end_date=None, autype=AUTYPE.QFQ):
        super().__init__(code, k_type, begin_date, end_date, autype)

    def _get_symbol(self):
        """提取纯数字代码"""
        symbol = self.code
        if '.' in symbol:
            symbol = symbol.split('.')[1]
        elif symbol.startswith(('sh', 'sz')):
            symbol = symbol[2:]
        return symbol

    def get_kl_data(self):
        period = PERIOD_MAP.get(self.k_type)
        if period is None:
            raise Exception(f"AkshareMin 不支持 {self.k_type} 级别")

        symbol = self._get_symbol()
        start_date = self.begin_date + " 09:30:00" if self.begin_date else "1979-09-01 09:30:00"
        end_date = self.end_date + " 15:00:00" if self.end_date else "2222-01-01 15:00:00"

        # 复权参数
        adjust_map = {AUTYPE.QFQ: "qfq", AUTYPE.HFQ: "hfq", AUTYPE.NONE: ""}
        adjust = adjust_map.get(self.autype, "qfq")

        if self.is_stock:
            # 个股分钟数据
            df = ak.stock_zh_a_hist_min_em(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        else:
            # 指数分钟数据
            df = ak.index_zh_a_hist_min_em(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
            )

        # 列名：时间, 开盘, 收盘, 最高, 最低, 成交量, 成交额, ...
        for _, row in df.iterrows():
            time_str = str(row.iloc[0])
            year = int(time_str[:4])
            month = int(time_str[5:7])
            day = int(time_str[8:10])
            hour = int(time_str[11:13])
            minute = int(time_str[14:16])

            item = {
                DATA_FIELD.FIELD_TIME: CTime(year, month, day, hour, minute),
                DATA_FIELD.FIELD_OPEN: str2float(row.iloc[1]),
                DATA_FIELD.FIELD_CLOSE: str2float(row.iloc[2]),
                DATA_FIELD.FIELD_HIGH: str2float(row.iloc[3]),
                DATA_FIELD.FIELD_LOW: str2float(row.iloc[4]),
                DATA_FIELD.FIELD_VOLUME: str2float(row.iloc[5]) if len(row) > 5 else 0,
                DATA_FIELD.FIELD_TURNOVER: str2float(row.iloc[6]) if len(row) > 6 else 0,
            }
            yield CKLine_Unit(item)

    def SetBasciInfo(self):
        self.name = self.code
        symbol = self._get_symbol()
        # 指数: 000xxx, 399xxx
        if symbol.startswith(('000', '399')) and len(symbol) == 6:
            self.is_stock = False
        else:
            self.is_stock = True

    @classmethod
    def do_init(cls):
        pass

    @classmethod
    def do_close(cls):
        pass
