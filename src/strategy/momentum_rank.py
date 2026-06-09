"""截面动量因子选股。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from .portfolio_selector import PortfolioSelector


@dataclass
class MomentumRankConfig:
    lookback: int = 20
    top_n: int = 5
    min_momentum: float = 0.0


class MomentumRankSelector(PortfolioSelector):
    """
    多标的截面动量排名：
    - 动量 = close[t] / close[t-lookback] - 1
    - 每个调仓日选取动量最高的 top_n 只（且 >= min_momentum）
    - 等权持有
    """

    def __init__(self, config: MomentumRankConfig):
        if config.lookback < 1:
            raise ValueError("lookback 必须 >= 1")
        if config.top_n < 1:
            raise ValueError("top_n 必须 >= 1")
        self.config = config

    @property
    def warmup_period(self) -> int:
        return self.config.lookback

    def select(self, close_panel: pd.DataFrame, time_idx: int) -> List[str]:
        if time_idx < self.config.lookback:
            return []

        row = close_panel.iloc[time_idx]
        ref = close_panel.iloc[time_idx - self.config.lookback]
        momentum = row / ref - 1

        valid = momentum.dropna()
        valid = valid[valid >= self.config.min_momentum]
        if valid.empty:
            return []

        ranked = valid.sort_values(ascending=False)
        return ranked.head(self.config.top_n).index.tolist()

    def score_snapshot(
        self,
        close_panel: pd.DataFrame,
        time_idx: int,
        symbols: List[str],
    ) -> Dict[str, float]:
        if time_idx < self.config.lookback:
            return {}
        row = close_panel.iloc[time_idx]
        ref = close_panel.iloc[time_idx - self.config.lookback]
        out: Dict[str, float] = {}
        for sym in symbols:
            c0, c1 = ref.get(sym), row.get(sym)
            if pd.notna(c0) and pd.notna(c1) and c0 != 0:
                out[sym] = round(float(c1 / c0 - 1), 4)
        return out

    def label(self) -> str:
        c = self.config
        return (
            f"动量因子选股 lookback={c.lookback} "
            f"Top{c.top_n} min_momentum={c.min_momentum}"
        )
