"""RSI 均值回归策略。"""

from __future__ import annotations

import pandas as pd

from .base import Strategy


class RsiStrategy(Strategy):
    """
    RSI 超买超卖（仅做多）：
    - RSI 跌入超卖区 -> 买入 (signal=1)
    - RSI 涨入超买区 -> 平仓 (signal=-1)
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ):
        if period < 2:
            raise ValueError("period 必须 >= 2")
        if not 0 < oversold < overbought < 100:
            raise ValueError("需满足 0 < oversold < overbought < 100")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, bars: pd.DataFrame) -> pd.DataFrame:
        df = bars.copy()
        df["rsi"] = _wilder_rsi(df["close"], self.period)

        prev_rsi = df["rsi"].shift(1)
        buy = (df["rsi"] < self.oversold) & (prev_rsi >= self.oversold)
        sell = (df["rsi"] > self.overbought) & (prev_rsi <= self.overbought)

        df["signal"] = 0
        df.loc[buy, "signal"] = 1
        df.loc[sell, "signal"] = -1
        return df


def _wilder_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))
