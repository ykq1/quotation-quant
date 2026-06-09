"""双均线交叉策略。"""

from __future__ import annotations

import pandas as pd

from .base import Strategy


class MaCrossStrategy(Strategy):
    """
    经典均线金叉/死叉：
    - 快线上穿慢线 -> 做多 (signal=1)
    - 快线下穿慢线 -> 平仓 (signal=-1)
    """

    def __init__(self, fast_period: int = 20, slow_period: int = 60):
        if fast_period >= slow_period:
            raise ValueError("fast_period 必须小于 slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signals(self, bars: pd.DataFrame) -> pd.DataFrame:
        df = bars.copy()
        df["ma_fast"] = df["close"].rolling(self.fast_period, min_periods=self.fast_period).mean()
        df["ma_slow"] = df["close"].rolling(self.slow_period, min_periods=self.slow_period).mean()

        prev_fast = df["ma_fast"].shift(1)
        prev_slow = df["ma_slow"].shift(1)

        golden = (df["ma_fast"] > df["ma_slow"]) & (prev_fast <= prev_slow)
        death = (df["ma_fast"] < df["ma_slow"]) & (prev_fast >= prev_slow)

        df["signal"] = 0
        df.loc[golden, "signal"] = 1
        df.loc[death, "signal"] = -1
        return df
