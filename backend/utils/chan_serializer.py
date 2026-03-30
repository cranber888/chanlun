"""将 chan.py 的分析结果序列化为前端可用的 JSON 格式"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'chan_py_lib'))

from Common.CEnum import BI_DIR, BSP_TYPE, KLINE_DIR, TREND_TYPE


def ctime_to_ts(ctime) -> int:
    """CTime -> Unix timestamp (seconds)"""
    return int(ctime.ts)


def compute_bi_trends(kl_list):
    """
    计算笔走势段 —— 由笔中枢构成的走势。

    走势类型:
      - 盘整: 只包含 1 个中枢
      - 趋势: 包含 2+ 个同向不重叠中枢

    走势结束条件:
      1. 趋势结束: 出现反向中枢
      2. 中枢扩展: 相邻中枢区间有重叠（已由 max_bi_cnt 辅助控制）
      3. 盘整走势出 3B 后价格回到原中枢
    """
    zs_lst = list(kl_list.zs_list)
    bi_list = kl_list.bi_list
    bsp_list = list(kl_list.bs_point_lst.getSortedBspList())

    if not zs_lst:
        return []

    # ---------- 辅助函数 ----------
    def zs_overlap(z1, z2):
        """两个中枢区间是否有重叠"""
        return max(z1.low, z2.low) <= min(z1.high, z2.high)

    def zs_direction(za, zb):
        """zb 相对 za 的方向: 'up' / 'down'"""
        return 'up' if zb.low > za.high else 'down'

    def has_3b_return(zs, bi_list_raw, bsp_list_raw):
        """
        判断盘整中枢是否出现过 3B 买卖点且之后价格回到中枢。
        3B 类型：BSP_TYPE.T3B
        """
        if zs.bi_out is None:
            return False
        out_bi = zs.bi_out
        # 在 bsp 列表中查找该中枢出口附近的 3b 类型
        for bsp in bsp_list_raw:
            if BSP_TYPE.T3B not in bsp.type:
                continue
            # bsp 的 bi 应该在中枢 bi_out 之后
            if bsp.bi.idx < out_bi.idx:
                continue
            # 检查 bsp 之后是否有 bi 回到中枢区间
            for bi_idx in range(bsp.bi.idx + 1, len(bi_list_raw)):
                bi = bi_list_raw[bi_idx]
                # bi 的价格范围与中枢有交集 = 回到中枢
                bi_low = min(bi.get_begin_val(), bi.get_end_val())
                bi_high = max(bi.get_begin_val(), bi.get_end_val())
                if max(zs.low, bi_low) <= min(zs.high, bi_high):
                    return True
            break  # 只检查第一个 3b
        return False

    # ---------- 分组: 将中枢按走势归组 ----------
    groups = []       # 每组: [zs1, zs2, ...]
    current = [zs_lst[0]]

    for i in range(1, len(zs_lst)):
        prev_zs = current[-1]
        curr_zs = zs_lst[i]

        # 条件 2: 中枢区间重叠 → 中枢扩展, 结束当前走势
        if zs_overlap(prev_zs, curr_zs):
            groups.append(current)
            current = [curr_zs]
            continue

        # 不重叠 → 判断方向
        new_dir = zs_direction(prev_zs, curr_zs)

        if len(current) >= 2:
            # 已有趋势方向, 检查是否一致
            existing_dir = zs_direction(current[0], current[-1])
            if new_dir == existing_dir:
                current.append(curr_zs)
            else:
                # 条件 1: 趋势方向反转
                groups.append(current)
                current = [curr_zs]
        else:
            # 第一对中枢, 直接加入
            current.append(curr_zs)

    groups.append(current)

    # ---------- 条件 3: 盘整走势 3B 回中枢检查 ----------
    # 对只有 1 个中枢的组, 如果出现 3B 回中枢, 强制结束走势
    # (当前分组逻辑已经是单中枢一组, 这里只做标记供前端使用)

    # ---------- 将每组转换为走势段 ----------
    result = []
    for group in groups:
        first_zs = group[0]
        last_zs = group[-1]

        # 确定走势方向
        if len(group) > 1:
            direction = zs_direction(group[0], group[-1])
        else:
            # 盘整: 方向由进出笔决定
            if first_zs.bi_in is not None and first_zs.bi_out is not None:
                entry_val = first_zs.bi_in.get_begin_val()
                exit_val = first_zs.bi_out.get_end_val()
                direction = 'up' if exit_val > entry_val else 'down'
            elif first_zs.bi_in is not None:
                direction = 'up' if first_zs.bi_in.dir == BI_DIR.UP else 'down'
            else:
                direction = 'up'

        # 起点: 进入第一个中枢的那笔的起点
        if first_zs.bi_in is not None:
            start_time = ctime_to_ts(first_zs.bi_in.get_begin_klu().time)
            start_val = first_zs.bi_in.get_begin_val()
        else:
            # 第一个中枢没有 bi_in (数据起始处)
            start_time = ctime_to_ts(first_zs.begin.time)
            start_val = first_zs.peak_low if direction == 'up' else first_zs.peak_high

        # 终点: 离开最后一个中枢的那笔的终点
        if last_zs.bi_out is not None:
            end_time = ctime_to_ts(last_zs.bi_out.get_end_klu().time)
            end_val = last_zs.bi_out.get_end_val()
        else:
            # 最后一个中枢还没有 bi_out (数据末尾)
            end_time = ctime_to_ts(last_zs.end_bi.get_end_klu().time)
            end_val = last_zs.end_bi.get_end_val()

        # 走势类型
        trend_type = 'trend' if len(group) > 1 else 'consolidation'
        has_3b = has_3b_return(last_zs, bi_list, bsp_list) if trend_type == 'consolidation' else False

        result.append({
            'begin_time': start_time,
            'begin_val': round(start_val, 4),
            'end_time': end_time,
            'end_val': round(end_val, 4),
            'dir': direction,
            'zs_count': len(group),
            'type': trend_type,
            'has_3b_return': has_3b,
        })

    return result


def serialize_kline_list(kl_list) -> dict:
    """将 CKLine_List 序列化为前端可用的 JSON"""
    klines = []
    merged_klines = []  # 合并K线列表
    ma_data = {}  # {period: [{time, value}]}
    boll_data = []

    for klc_idx, klc in enumerate(kl_list.lst):
        klc_size = len(klc.lst)  # 该合并K线包含的原始K线数量
        for klu in klc.lst:
            ts = ctime_to_ts(klu.time)
            # 成交量
            vol = 0
            if hasattr(klu, 'trade_info') and klu.trade_info and hasattr(klu.trade_info, 'metric'):
                from Common.CEnum import DATA_FIELD as _DF
                vol = klu.trade_info.metric.get(_DF.FIELD_VOLUME) or 0

            kl_item = {
                "time": ts,
                "open": round(klu.open, 4),
                "high": round(klu.high, 4),
                "low": round(klu.low, 4),
                "close": round(klu.close, 4),
                "volume": vol,
            }
            if klc_size > 1:
                kl_item["merged"] = True  # 标记：该K线参与了合并
            klines.append(kl_item)

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

        # 输出合并K线（仅包含被合并过的，即 klc_size > 1）
        if klc_size > 1:
            first_klu = klc.lst[0]
            last_klu = klc.lst[-1]
            merged_klines.append({
                "begin_time": ctime_to_ts(first_klu.time),
                "end_time": ctime_to_ts(last_klu.time),
                "high": round(klc.high, 4),
                "low": round(klc.low, 4),
                "dir": "up" if klc.dir == KLINE_DIR.UP else "down",
                "count": klc_size,
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
        bi_cnt = zs.end_bi.idx - zs.begin_bi.idx + 1
        zs_list.append({
            "begin_time": ctime_to_ts(zs.begin.time),
            "end_time": ctime_to_ts(zs.end.time),
            "low": round(zs.low, 4),
            "high": round(zs.high, 4),
            "peak_low": round(zs.peak_low, 4),
            "peak_high": round(zs.peak_high, 4),
            "is_sure": zs.is_sure,
            "begin_bi_idx": zs.begin_bi.idx,
            "end_bi_idx": zs.end_bi.idx,
            "bi_cnt": bi_cnt,
        })

    # 线段的线段（高级别走势，蓝色线）
    segseg_list = []
    for seg in kl_list.segseg_list:
        segseg_list.append({
            "dir": "up" if seg.dir == BI_DIR.UP else "down",
            "begin_time": ctime_to_ts(seg.get_begin_klu().time),
            "begin_val": round(seg.get_begin_val(), 4),
            "end_time": ctime_to_ts(seg.get_end_klu().time),
            "end_val": round(seg.get_end_val(), 4),
            "is_sure": seg.is_sure,
        })

    # 线段级别中枢（高级别中枢，绿色框）
    seg_zs_list = []
    for zs in kl_list.segzs_list:
        bi_cnt = zs.end_bi.idx - zs.begin_bi.idx + 1
        seg_zs_list.append({
            "begin_time": ctime_to_ts(zs.begin.time),
            "end_time": ctime_to_ts(zs.end.time),
            "low": round(zs.low, 4),
            "high": round(zs.high, 4),
            "peak_low": round(zs.peak_low, 4),
            "peak_high": round(zs.peak_high, 4),
            "is_sure": zs.is_sure,
            "bi_cnt": bi_cnt,
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

    # 笔走势（由笔中枢构成的走势段）
    bi_trend_list = compute_bi_trends(kl_list)

    # 转换 ma_data 的 key 为字符串（JSON 不支持 int key）
    ma_serialized = {str(k): v for k, v in ma_data.items()}

    return {
        "klines": klines,
        "merged_klines": merged_klines,
        "bi_list": bi_list,
        "seg_list": seg_list,
        "segseg_list": segseg_list,
        "zs_list": zs_list,
        "seg_zs_list": seg_zs_list,
        "bi_trend_list": bi_trend_list,
        "bsp_list": bsp_list,
        "seg_bsp_list": seg_bsp_list,
        "macd_list": macd_list,
        "ma_data": ma_serialized,
        "boll_data": boll_data,
    }
