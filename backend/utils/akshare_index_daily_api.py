"""AkShare 指数日线数据适配器（使用东财 index_zh_a_hist，当天实时）"""
import akshare as ak

from Common.CEnum import AUTYPE, DATA_FIELD, KL_TYPE
from Common.CTime import CTime
from Common.func_util import str2float
from KLine.KLine_Unit import CKLine_Unit
from DataAPI.CommonStockAPI import CCommonStockApi


PERIOD_MAP = {
    KL_TYPE.K_DAY: 'daily',
    KL_TYPE.K_WEEK: 'weekly',
    KL_TYPE.K_MON: 'monthly',
}


class CAkshareIndexDaily(CCommonStockApi):
    """使用 AkShare index_zh_a_hist 获取A股指数日线数据"""

    def __init__(self, code, k_type=KL_TYPE.K_DAY, begin_date=None, end_date=None, autype=AUTYPE.QFQ):
        super().__init__(code, k_type, begin_date, end_date, autype)

    def _get_symbol(self):
        symbol = self.code
        if '.' in symbol:
            symbol = symbol.split('.')[1]
        elif symbol.startswith(('sh', 'sz')):
            symbol = symbol[2:]
        return symbol

    def get_kl_data(self):
        period = PERIOD_MAP.get(self.k_type)
        if period is None:
            raise Exception(f"AkshareIndexDaily 不支持 {self.k_type} 级别")

        symbol = self._get_symbol()
        start_date = self.begin_date.replace("-", "") if self.begin_date else "19900101"
        end_date = self.end_date.replace("-", "") if self.end_date else "20991231"

        df = ak.index_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        # 列名: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, ...
        for _, row in df.iterrows():
            date_str = str(row.iloc[0])
            year = int(date_str[:4])
            month = int(date_str[5:7])
            day = int(date_str[8:10])

            item = {
                DATA_FIELD.FIELD_TIME: CTime(year, month, day, 0, 0),
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
        self.is_stock = False

    @classmethod
    def do_init(cls):
        pass

    @classmethod
    def do_close(cls):
        pass
