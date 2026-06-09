"""布林带突破策略（趋势跟踪）。"""

from __future__ import annotations

import pandas as pd

from .base import Strategy


class BollingerBreakoutStrategy(Strategy):
    """
    布林带突破（仅做多，与 bollinger 均值回归相反）：
    - 收盘价突破上轨 -> 买入 (signal=1)
    - 收盘价跌破中轨 -> 平仓 (signal=-1)
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        if period < 2:
            raise ValueError("period 必须 >= 2")
        if std_dev <= 0:
            raise ValueError("std_dev 必须 > 0")
        self.period = period
        self.std_dev = std_dev

    def generate_signals(self, bars: pd.DataFrame) -> pd.DataFrame:
        df = bars.copy()
        mid = df["close"].rolling(self.period, min_periods=self.period).mean()
        std = df["close"].rolling(self.period, min_periods=self.period).std()
        df["bb_mid"] = mid
        df["bb_upper"] = mid + self.std_dev * std
        df["bb_lower"] = mid - self.std_dev * std

        prev_close = df["close"].shift(1)
        prev_upper = df["bb_upper"].shift(1)
        prev_mid = df["bb_mid"].shift(1)

        buy = (df["close"] > df["bb_upper"]) & (prev_close <= prev_upper)
        sell = (df["close"] < df["bb_mid"]) & (prev_close >= prev_mid)

        df["signal"] = 0
        df.loc[buy, "signal"] = 1
        df.loc[sell, "signal"] = -1
        return df
