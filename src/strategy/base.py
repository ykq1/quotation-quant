"""策略基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    @abstractmethod
    def generate_signals(self, bars: pd.DataFrame) -> pd.DataFrame:
        """
        在 bars 上生成信号列 signal: 1=做多, -1=平仓/做空, 0=空仓
        返回的 DataFrame 应包含原 bars 列及 signal 列。
        """
