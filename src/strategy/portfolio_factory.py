"""组合选股策略工厂。"""

from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd

from .factor_rank import FactorRankConfig, FactorRankSelector
from .momentum_rank import MomentumRankConfig, MomentumRankSelector
from .portfolio_selector import PortfolioSelector

PORTFOLIO_STRATEGIES = ("momentum_rank", "factor_rank")


def build_portfolio_selector(
    pf: dict,
    volume_panel: Optional[pd.DataFrame] = None,
) -> Tuple[PortfolioSelector, str]:
    name = (pf.get("strategy") or "momentum_rank").strip().lower()

    if name == "momentum_rank":
        cfg = MomentumRankConfig(
            lookback=pf.get("momentum_lookback", 20),
            top_n=pf.get("top_n", 5),
            min_momentum=pf.get("min_momentum", 0.0),
        )
        sel = MomentumRankSelector(cfg)
        return sel, sel.label()

    if name == "factor_rank":
        weights = pf.get("factor_weights") or {
            "momentum": 0.40,
            "low_vol": 0.30,
            "reversal": 0.20,
            "volume": 0.10,
        }
        cfg = FactorRankConfig(
            top_n=pf.get("top_n", 5),
            lookback=pf.get("factor_lookback", pf.get("momentum_lookback", 20)),
            reversal_lookback=pf.get("reversal_lookback", 5),
            weights=weights,
            min_score=pf.get("min_factor_score"),
        )
        sel = FactorRankSelector(cfg, volume_panel=volume_panel)
        return sel, sel.label()

    raise ValueError(f"未知组合策略: {name}，可选: {', '.join(PORTFOLIO_STRATEGIES)}")
