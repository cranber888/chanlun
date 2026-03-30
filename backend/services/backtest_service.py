"""
缠论模拟量化回测引擎

策略: 基于缠论买卖点信号进行模拟交易
- 买入: 出现指定类型的买点时买入
- 卖出: 出现指定类型的卖点时卖出
- 支持止损 (跌破买入价 x%)

回测流程:
  1. 获取缠论分析结果 (含买卖点)
  2. 按时间顺序遍历买卖点
  3. 模拟开仓/平仓, 记录每笔交易
  4. 计算绩效指标
"""
from datetime import datetime, timedelta


def run_backtest(
    analysis_data: dict,
    initial_capital: float = 100000.0,
    position_ratio: float = 1.0,
    commission_rate: float = 0.001,
    stamp_tax_rate: float = 0.001,
    stop_loss_pct: float = 0.0,
    buy_types: list = None,
    sell_types: list = None,
) -> dict:
    """
    运行回测

    参数:
        analysis_data: 缠论分析结果 (serialize_kline_list 的输出)
        initial_capital: 初始资金 (元)
        position_ratio: 仓位比例 (0~1, 1=满仓)
        commission_rate: 佣金费率 (双向)
        stamp_tax_rate: 印花税 (卖出时)
        stop_loss_pct: 止损比例 (0=不止损, 如 0.05=跌5%止损)
        buy_types: 买入信号类型, 如 ["1"]  表示只用1类买点
        sell_types: 卖出信号类型, 如 ["1"]  表示只用1类卖点

    返回:
        回测结果字典
    """
    if buy_types is None:
        buy_types = ["1"]
    if sell_types is None:
        sell_types = ["1"]

    klines = analysis_data.get("klines", [])
    bsp_list = analysis_data.get("bsp_list", [])
    seg_bsp_list = analysis_data.get("seg_bsp_list", [])

    if not klines:
        return {"error": "无K线数据，无法回测"}

    # 买卖点为空时返回空结果（没信号=没交易）
    if not bsp_list and not seg_bsp_list:
        equity_curve = [{"time": kl["time"], "equity": initial_capital} for kl in klines]
        return {
            "summary": {
                "initial_capital": initial_capital,
                "final_equity": initial_capital,
                "total_return": 0,
                "annual_return": 0,
                "max_drawdown": 0,
                "total_trades": 0,
                "win_trades": 0,
                "lose_trades": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_loss_ratio": 0,
            },
            "trades": [],
            "equity_curve": equity_curve,
        }

    # 构建K线时间->价格映射 (用于止损检查和资金曲线)
    kl_map = {}
    for kl in klines:
        kl_map[kl["time"]] = kl

    # 合并买卖点并按时间排序
    all_bsp = []
    for bsp in bsp_list:
        all_bsp.append({**bsp, "source": "bi"})
    for bsp in seg_bsp_list:
        all_bsp.append({**bsp, "source": "seg"})
    all_bsp.sort(key=lambda x: x["time"])

    # ---- 回测状态 ----
    capital = initial_capital      # 当前现金
    shares = 0                      # 持仓股数
    buy_price = 0                   # 买入均价
    buy_time = 0                    # 买入时间

    trades = []                     # 交易记录
    equity_curve = []               # 资金曲线 [{time, equity}]
    max_equity = initial_capital    # 历史最高资产
    max_drawdown = 0                # 最大回撤

    # ---- 辅助函数 ----
    def get_equity(price):
        """当前总资产"""
        return capital + shares * price

    def calc_commission(amount):
        """计算佣金 (最低5元)"""
        comm = amount * commission_rate
        return max(comm, 5.0)

    def do_buy(price, time_ts):
        """执行买入"""
        nonlocal capital, shares, buy_price, buy_time
        if shares > 0:
            return  # 已有持仓, 不重复买入

        available = capital * position_ratio
        comm = calc_commission(available)
        actual_amount = available - comm

        if actual_amount <= 0:
            return

        # 按手 (100股) 买入
        buy_shares = int(actual_amount / price / 100) * 100
        if buy_shares <= 0:
            return

        cost = buy_shares * price + calc_commission(buy_shares * price)
        capital -= cost
        shares = buy_shares
        buy_price = price
        buy_time = time_ts

    def do_sell(price, time_ts, reason="signal"):
        """执行卖出"""
        nonlocal capital, shares, buy_price, buy_time
        if shares <= 0:
            return  # 无持仓

        sell_amount = shares * price
        comm = calc_commission(sell_amount)
        tax = sell_amount * stamp_tax_rate
        net = sell_amount - comm - tax

        # 记录交易
        pnl = net - (shares * buy_price + calc_commission(shares * buy_price))
        pnl_pct = (price - buy_price) / buy_price * 100

        trades.append({
            "buy_time": buy_time,
            "buy_price": round(buy_price, 4),
            "sell_time": time_ts,
            "sell_price": round(price, 4),
            "shares": shares,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
        })

        capital += net
        shares = 0
        buy_price = 0
        buy_time = 0

    # ---- 判断买卖点类型是否匹配 ----
    def match_buy(bsp):
        """判断是否为目标买点"""
        if not bsp["is_buy"]:
            return False
        bsp_type = bsp["type"]  # 如 "1", "2", "3a", "3b", "1p", "2s"
        for bt in buy_types:
            if bt in bsp_type:
                return True
        return False

    def match_sell(bsp):
        """判断是否为目标卖点"""
        if bsp["is_buy"]:
            return False
        bsp_type = bsp["type"]
        for st in sell_types:
            if st in bsp_type:
                return True
        return False

    # ---- 主回测循环 ----
    bsp_idx = 0

    for kl in klines:
        ts = kl["time"]
        close = kl["close"]
        low = kl["low"]

        # 止损检查 (用最低价)
        if shares > 0 and stop_loss_pct > 0:
            if low <= buy_price * (1 - stop_loss_pct):
                stop_price = buy_price * (1 - stop_loss_pct)
                do_sell(round(stop_price, 4), ts, reason="stop_loss")

        # 检查当前K线时间点是否有买卖点信号
        while bsp_idx < len(all_bsp) and all_bsp[bsp_idx]["time"] <= ts:
            bsp = all_bsp[bsp_idx]
            if bsp["time"] == ts:
                if match_sell(bsp) and shares > 0:
                    do_sell(close, ts, reason="signal")
                elif match_buy(bsp) and shares == 0:
                    do_buy(close, ts)
            bsp_idx += 1

        # 记录资金曲线
        equity = get_equity(close)
        equity_curve.append({
            "time": ts,
            "equity": round(equity, 2),
        })

        # 更新最大回撤
        if equity > max_equity:
            max_equity = equity
        dd = (max_equity - equity) / max_equity
        if dd > max_drawdown:
            max_drawdown = dd

    # ---- 如果最后还有持仓, 按最后收盘价平仓 ----
    if shares > 0 and klines:
        last_kl = klines[-1]
        do_sell(last_kl["close"], last_kl["time"], reason="end")

    # ---- 计算绩效 ----
    final_equity = capital
    total_return = (final_equity - initial_capital) / initial_capital * 100

    # 年化收益
    if len(klines) >= 2:
        days = (klines[-1]["time"] - klines[0]["time"]) / 86400
        if days > 0:
            annual_return = ((final_equity / initial_capital) ** (365 / days) - 1) * 100
        else:
            annual_return = 0
    else:
        annual_return = 0

    # 胜率和盈亏比
    win_trades = [t for t in trades if t["pnl"] > 0]
    lose_trades = [t for t in trades if t["pnl"] <= 0]
    win_rate = len(win_trades) / len(trades) * 100 if trades else 0

    avg_win = sum(t["pnl"] for t in win_trades) / len(win_trades) if win_trades else 0
    avg_loss = abs(sum(t["pnl"] for t in lose_trades) / len(lose_trades)) if lose_trades else 0
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')

    return {
        "summary": {
            "initial_capital": initial_capital,
            "final_equity": round(final_equity, 2),
            "total_return": round(total_return, 2),
            "annual_return": round(annual_return, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "total_trades": len(trades),
            "win_trades": len(win_trades),
            "lose_trades": len(lose_trades),
            "win_rate": round(win_rate, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_loss_ratio": round(profit_loss_ratio, 2) if profit_loss_ratio != float('inf') else 999,
        },
        "trades": trades,
        "equity_curve": equity_curve,
    }
