"""将 chan.py 的分析结果序列化为前端可用的 JSON 格式"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'chan_py_lib'))

from Common.CEnum import BI_DIR, TREND_TYPE


def ctime_to_ts(ctime) -> int:
    """CTime -> Unix timestamp (seconds)"""
    return int(ctime.ts)


def serialize_kline_list(kl_list) -> dict:
    """将 CKLine_List 序列化为前端可用的 JSON"""
    klines = []
    ma_data = {}  # {period: [{time, value}]}
    boll_data = []

    for klc in kl_list.lst:
        for klu in klc.lst:
            ts = ctime_to_ts(klu.time)
            klines.append({
                "time": ts,
                "open": round(klu.open, 4),
                "high": round(klu.high, 4),
                "low": round(klu.low, 4),
                "close": round(klu.close, 4),
            })

            # MA 均线
            if hasattr(klu, 'trend') and klu.trend:
                mean_dict = klu.trend.get(TREND_TYPE.MEAN, {})
                for period, value in mean_dict.items():
                    if value is not None:
                        if period not in ma_data:
                            ma_data[period] = []
                        ma_data[period].append({"time": ts, "value": round(value, 4)})

            # BOLL
            if hasattr(klu, 'boll') and klu.boll is not None:
                boll_data.append({
                    "time": ts,
                    "upper": round(klu.boll.UP, 4),
                    "mid": round(klu.boll.MID, 4),
                    "lower": round(klu.boll.DOWN, 4),
                })

    bi_list = []
    for bi in kl_list.bi_list:
        bi_list.append({
            "dir": "up" if bi.dir == BI_DIR.UP else "down",
            "begin_time": ctime_to_ts(bi.get_begin_klu().time),
            "begin_val": round(bi.get_begin_val(), 4),
            "end_time": ctime_to_ts(bi.get_end_klu().time),
            "end_val": round(bi.get_end_val(), 4),
            "is_sure": bi.is_sure,
        })

    seg_list = []
    for seg in kl_list.seg_list:
        seg_list.append({
            "dir": "up" if seg.dir == BI_DIR.UP else "down",
            "begin_time": ctime_to_ts(seg.start_bi.get_begin_klu().time),
            "begin_val": round(seg.start_bi.get_begin_val(), 4),
            "end_time": ctime_to_ts(seg.end_bi.get_end_klu().time),
            "end_val": round(seg.end_bi.get_end_val(), 4),
            "is_sure": seg.is_sure,
        })

    zs_list = []
    for zs in kl_list.zs_list:
        zs_list.append({
            "begin_time": ctime_to_ts(zs.begin.time),
            "end_time": ctime_to_ts(zs.end.time),
            "low": round(zs.low, 4),
            "high": round(zs.high, 4),
            "peak_low": round(zs.peak_low, 4),
            "peak_high": round(zs.peak_high, 4),
            "is_sure": zs.is_sure,
        })

    seg_zs_list = []
    for zs in kl_list.segzs_list:
        seg_zs_list.append({
            "begin_time": ctime_to_ts(zs.begin.time),
            "end_time": ctime_to_ts(zs.end.time),
            "low": round(zs.low, 4),
            "high": round(zs.high, 4),
            "peak_low": round(zs.peak_low, 4),
            "peak_high": round(zs.peak_high, 4),
            "is_sure": zs.is_sure,
        })

    bsp_list = []
    for bsp in kl_list.bs_point_lst.getSortedBspList():
        bsp_list.append({
            "time": ctime_to_ts(bsp.klu.time),
            "is_buy": bsp.is_buy,
            "type": bsp.type2str(),
            "val": round(bsp.klu.close, 4),
        })

    seg_bsp_list = []
    for bsp in kl_list.seg_bs_point_lst.getSortedBspList():
        seg_bsp_list.append({
            "time": ctime_to_ts(bsp.klu.time),
            "is_buy": bsp.is_buy,
            "type": bsp.type2str(),
            "val": round(bsp.klu.close, 4),
            "is_seg": True,
        })

    macd_list = []
    for klc in kl_list.lst:
        for klu in klc.lst:
            if hasattr(klu, 'macd') and klu.macd is not None:
                macd_list.append({
                    "time": ctime_to_ts(klu.time),
                    "dif": round(klu.macd.DIF, 4),
                    "dea": round(klu.macd.DEA, 4),
                    "macd": round(klu.macd.macd, 4),
                })

    # 转换 ma_data 的 key 为字符串（JSON 不支持 int key）
    ma_serialized = {str(k): v for k, v in ma_data.items()}

    return {
        "klines": klines,
        "bi_list": bi_list,
        "seg_list": seg_list,
        "zs_list": zs_list,
        "seg_zs_list": seg_zs_list,
        "bsp_list": bsp_list,
        "seg_bsp_list": seg_bsp_list,
        "macd_list": macd_list,
        "ma_data": ma_serialized,
        "boll_data": boll_data,
    }
