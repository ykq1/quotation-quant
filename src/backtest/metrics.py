"""回测绩效指标。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


@dataclass
class BacktestMetrics:
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    round_trip_win_rate: float
    trade_count: int
    final_equity: float

    def to_dict(self):
        return {
            "total_return": round(self.total_return, 4),
            "annual_return": round(self.annual_return, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "win_rate": round(self.win_rate, 4),
            "round_trip_win_rate": round(self.round_trip_win_rate, 4),
            "trade_count": self.trade_count,
            "final_equity": round(self.final_equity, 2),
        }


def compute_metrics(equity_curve: pd.Series, trades: List[dict], bars_per_year: int = 252) -> BacktestMetrics:
    if equity_curve.empty:
        return BacktestMetrics(0, 0, 0, 0, 0, 0, 0, 0)

    initial = float(equity_curve.iloc[0])
    final = float(equity_curve.iloc[-1])
    total_return = (final - initial) / initial if initial else 0

    n = len(equity_curve)
    annual_return = (1 + total_return) ** (bars_per_year / max(n, 1)) - 1 if n > 1 else total_return

    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax.replace(0, np.nan)
    max_drawdown = float(drawdown.min()) if len(drawdown) else 0

    daily_ret = equity_curve.pct_change().dropna()
    sharpe = 0.0
    if len(daily_ret) > 1 and daily_ret.std() > 0:
        sharpe = float(daily_ret.mean() / daily_ret.std() * np.sqrt(bars_per_year))

    wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
    trade_count = len(trades)
    win_rate = wins / trade_count if trade_count else 0

    sells = [t for t in trades if t.get("side") == "SELL"]
    round_trip_wins = sum(1 for t in sells if t.get("pnl", 0) > 0)
    round_trip_win_rate = round_trip_wins / len(sells) if sells else 0

    return BacktestMetrics(
        total_return=total_return,
        annual_return=annual_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe,
        win_rate=win_rate,
        round_trip_win_rate=round_trip_win_rate,
        trade_count=trade_count,
        final_equity=final,
    )
