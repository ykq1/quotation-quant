"""多因子截面选股。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .portfolio_selector import PortfolioSelector


@dataclass
class FactorRankConfig:
    top_n: int = 5
    lookback: int = 20
    reversal_lookback: int = 5
    weights: Dict[str, float] = field(default_factory=lambda: {
        "momentum": 0.40,
        "low_vol": 0.30,
        "reversal": 0.20,
        "volume": 0.10,
    })
    min_score: Optional[float] = None


class FactorRankSelector(PortfolioSelector):
    """
    多因子打分选股（仅使用 K 线价量数据）：

    | 因子 | 计算 | 偏好 |
    |------|------|------|
    | momentum | N 日收益率 | 越高越好 |
    | low_vol | N 日收益波动率 | 越低越好（低波动异象） |
    | reversal | 短周期收益率取反 | 短期超跌反弹 |
    | volume | N 日平均成交量对数 | 流动性越好越好 |

    每个调仓日对因子做截面 z-score，再加权求综合得分，取 Top N。
    """

    def __init__(
        self,
        config: FactorRankConfig,
        volume_panel: Optional[pd.DataFrame] = None,
    ):
        if config.top_n < 1:
            raise ValueError("top_n 必须 >= 1")
        if config.lookback < 2:
            raise ValueError("lookback 必须 >= 2")
        self.config = config
        self.volume_panel = volume_panel
        self._last_scores: Dict[str, float] = {}

    @property
    def warmup_period(self) -> int:
        return max(self.config.lookback, self.config.reversal_lookback) + 1

    def select(self, close_panel: pd.DataFrame, time_idx: int) -> List[str]:
        scores = self._composite_scores(close_panel, time_idx)
        if scores.empty:
            self._last_scores = {}
            return []

        if self.config.min_score is not None:
            scores = scores[scores >= self.config.min_score]
        if scores.empty:
            self._last_scores = {}
            return []

        self._last_scores = scores.sort_values(ascending=False).head(self.config.top_n).to_dict()
        return list(self._last_scores.keys())

    def score_snapshot(
        self,
        close_panel: pd.DataFrame,
        time_idx: int,
        symbols: List[str],
    ) -> Dict[str, float]:
        if self._last_scores:
            return {k: round(v, 4) for k, v in self._last_scores.items() if k in symbols}
        scores = self._composite_scores(close_panel, time_idx)
        out: Dict[str, float] = {}
        for sym in symbols:
            if sym in scores.index:
                out[sym] = round(float(scores[sym]), 4)
        return out

    def label(self) -> str:
        w = self.config.weights
        parts = ", ".join(f"{k}={v}" for k, v in w.items())
        return f"多因子选股 Top{self.config.top_n} ({parts})"

    def _composite_scores(self, close_panel: pd.DataFrame, time_idx: int) -> pd.Series:
        if time_idx < self.warmup_period:
            return pd.Series(dtype=float)

        weights = self._normalized_weights()
        composite: Optional[pd.Series] = None
        valid_mask = pd.Series(False, index=close_panel.columns)

        for name, weight in weights.items():
            raw = self._raw_factor(name, close_panel, time_idx)
            if raw is None:
                continue
            z = _zscore(raw)
            part = z * weight
            composite = part if composite is None else composite.add(part, fill_value=np.nan)
            valid_mask |= z.notna()

        if composite is None:
            return pd.Series(dtype=float)
        return composite[valid_mask].dropna()

    def _normalized_weights(self) -> Dict[str, float]:
        raw = dict(self.config.weights)
        if self.volume_panel is None:
            raw.pop("volume", None)
        total = sum(raw.values())
        if total <= 0:
            return {"momentum": 1.0}
        return {k: v / total for k, v in raw.items()}

    def _raw_factor(
        self,
        name: str,
        close_panel: pd.DataFrame,
        time_idx: int,
    ) -> Optional[pd.Series]:
        if name == "momentum":
            return self._momentum(close_panel, time_idx)
        if name == "low_vol":
            return -self._volatility(close_panel, time_idx)
        if name == "reversal":
            return -self._momentum(close_panel, time_idx, self.config.reversal_lookback)
        if name == "volume" and self.volume_panel is not None:
            return self._liquidity(time_idx)
        return None

    def _momentum(
        self,
        close_panel: pd.DataFrame,
        time_idx: int,
        lookback: Optional[int] = None,
    ) -> pd.Series:
        lb = lookback or self.config.lookback
        row = close_panel.iloc[time_idx]
        ref = close_panel.iloc[time_idx - lb]
        return row / ref - 1

    def _volatility(self, close_panel: pd.DataFrame, time_idx: int) -> pd.Series:
        window = close_panel.iloc[time_idx - self.config.lookback + 1: time_idx + 1]
        returns = window.pct_change().iloc[1:]
        return returns.std()

    def _liquidity(self, time_idx: int) -> pd.Series:
        assert self.volume_panel is not None
        window = self.volume_panel.iloc[time_idx - self.config.lookback + 1: time_idx + 1]
        avg = window.mean()
        return np.log(avg.replace(0, np.nan))


def _zscore(series: pd.Series) -> pd.Series:
    valid = series.dropna()
    if len(valid) < 2:
        return series * 0
    std = valid.std()
    if std == 0 or pd.isna(std):
        return series * 0
    return (series - valid.mean()) / std
