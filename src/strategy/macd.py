"""MACD 交叉策略。"""

from __future__ import annotations

import pandas as pd

from .base import Strategy


class MacdStrategy(Strategy):
    """
    MACD 金叉/死叉（仅做多）：
    - DIF 上穿 DEA -> 买入 (signal=1)
    - DIF 下穿 DEA -> 平仓 (signal=-1)
    """

    def __init__(self, fast: int = 12, slow: int = 26, signal_period: int = 9):
        if fast >= slow:
            raise ValueError("macd_fast 必须小于 macd_slow")
        if signal_period < 1:
            raise ValueError("macd_signal 必须 >= 1")
        self.fast = fast
        self.slow = slow
        self.signal_period = signal_period

    def generate_signals(self, bars: pd.DataFrame) -> pd.DataFrame:
        df = bars.copy()
        ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()
        df["macd_dif"] = ema_fast - ema_slow
        df["macd_dea"] = df["macd_dif"].ewm(span=self.signal_period, adjust=False).mean()
        df["macd_hist"] = df["macd_dif"] - df["macd_dea"]

        prev_dif = df["macd_dif"].shift(1)
        prev_dea = df["macd_dea"].shift(1)

        golden = (df["macd_dif"] > df["macd_dea"]) & (prev_dif <= prev_dea)
        death = (df["macd_dif"] < df["macd_dea"]) & (prev_dif >= prev_dea)

        df["signal"] = 0
        df.loc[golden, "signal"] = 1
        df.loc[death, "signal"] = -1
        return df
