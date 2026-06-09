"""唐奇安通道突破策略。"""

from __future__ import annotations

import pandas as pd

from .base import Strategy


class DonchianStrategy(Strategy):
    """
    唐奇安通道 / 海龟突破（仅做多）：
    - 收盘价突破前 N 日最高价 -> 买入 (signal=1)
    - 收盘价跌破前 M 日最低价 -> 平仓 (signal=-1)

    默认 N=20（入场）、M=10（出场），与经典海龟法则一致。
    """

    def __init__(self, entry_period: int = 20, exit_period: int = 10):
        if entry_period < 2:
            raise ValueError("donchian_entry_period 必须 >= 2")
        if exit_period < 2:
            raise ValueError("donchian_exit_period 必须 >= 2")
        self.entry_period = entry_period
        self.exit_period = exit_period

    def generate_signals(self, bars: pd.DataFrame) -> pd.DataFrame:
        df = bars.copy()
        high = df["high"] if "high" in df.columns else df["close"]
        low = df["low"] if "low" in df.columns else df["close"]

        # 用 shift(1) 表示「截至昨日」的通道，避免含当日高低点
        df["dc_entry_upper"] = high.rolling(
            self.entry_period, min_periods=self.entry_period
        ).max().shift(1)
        df["dc_exit_lower"] = low.rolling(
            self.exit_period, min_periods=self.exit_period
        ).min().shift(1)

        prev_close = df["close"].shift(1)
        prev_entry = df["dc_entry_upper"].shift(1)
        prev_exit = df["dc_exit_lower"].shift(1)

        breakout = (df["close"] > df["dc_entry_upper"]) & (prev_close <= prev_entry)
        breakdown = (df["close"] < df["dc_exit_lower"]) & (prev_close >= prev_exit)

        df["signal"] = 0
        df.loc[breakout, "signal"] = 1
        df.loc[breakdown, "signal"] = -1
        return df
