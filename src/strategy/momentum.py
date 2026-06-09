"""价格动量策略。"""

from __future__ import annotations

import pandas as pd

from .base import Strategy


class MomentumStrategy(Strategy):
    """
    N 日价格动量（仅做多，单标的）：
    - 动量 = close / close[N日前] - 1
    - 动量向上突破入场阈值 -> 买入 (signal=1)
    - 动量向下跌破出场阈值 -> 平仓 (signal=-1)

    默认阈值为 0，即动量由负转正买入、由正转负卖出。
    """

    def __init__(
        self,
        lookback_period: int = 20,
        entry_threshold: float = 0.0,
        exit_threshold: float = 0.0,
    ):
        if lookback_period < 1:
            raise ValueError("lookback_period 必须 >= 1")
        self.lookback_period = lookback_period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def generate_signals(self, bars: pd.DataFrame) -> pd.DataFrame:
        df = bars.copy()
        ref = df["close"].shift(self.lookback_period)
        df["momentum"] = df["close"] / ref - 1

        prev = df["momentum"].shift(1)
        buy = (df["momentum"] > self.entry_threshold) & (prev <= self.entry_threshold)
        sell = (df["momentum"] < self.exit_threshold) & (prev >= self.exit_threshold)

        df["signal"] = 0
        df.loc[buy, "signal"] = 1
        df.loc[sell, "signal"] = -1
        return df
