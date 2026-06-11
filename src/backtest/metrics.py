"""回测绩效指标。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

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
    benchmark_total_return: float = 0.0
    benchmark_annual_return: float = 0.0
    excess_return: float = 0.0

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
            "benchmark_total_return": round(self.benchmark_total_return, 4),
            "benchmark_annual_return": round(self.benchmark_annual_return, 4),
            "excess_return": round(self.excess_return, 4),
        }


def buy_hold_equity_from_close(
    close: pd.Series,
    initial_capital: float = 1_000_000,
) -> pd.Series:
    """单标的：首日收盘买入并一直持有。"""
    if close.empty:
        return pd.Series(dtype=float)
    base = float(close.iloc[0])
    if base == 0:
        return pd.Series(initial_capital, index=close.index)
    return initial_capital * (close.astype(float) / base)


def buy_hold_equity_from_panel(
    close_panel: pd.DataFrame,
    initial_capital: float = 1_000_000,
) -> pd.Series:
    """组合：首日等权买入全部标的并一直持有（不再调仓）。"""
    if close_panel.empty or close_panel.shape[1] == 0:
        return pd.Series(dtype=float)
    normalized = close_panel.astype(float).div(close_panel.iloc[0]).replace([np.inf, -np.inf], np.nan)
    portfolio_index = normalized.mean(axis=1, skipna=True)
    return initial_capital * portfolio_index


def _total_and_annual_return(equity_curve: pd.Series, bars_per_year: int) -> tuple[float, float]:
    if equity_curve.empty:
        return 0.0, 0.0
    initial = float(equity_curve.iloc[0])
    final = float(equity_curve.iloc[-1])
    total_return = (final - initial) / initial if initial else 0.0
    n = len(equity_curve)
    annual_return = (1 + total_return) ** (bars_per_year / max(n, 1)) - 1 if n > 1 else total_return
    return total_return, annual_return


def compute_metrics(
    equity_curve: pd.Series,
    trades: List[dict],
    bars_per_year: int = 252,
    benchmark_equity: Optional[pd.Series] = None,
) -> BacktestMetrics:
    if equity_curve.empty:
        return BacktestMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    total_return, annual_return = _total_and_annual_return(equity_curve, bars_per_year)
    final = float(equity_curve.iloc[-1])
    n = len(equity_curve)

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

    benchmark_total_return = 0.0
    benchmark_annual_return = 0.0
    if benchmark_equity is not None and not benchmark_equity.empty:
        benchmark_total_return, benchmark_annual_return = _total_and_annual_return(
            benchmark_equity, bars_per_year
        )

    return BacktestMetrics(
        total_return=total_return,
        annual_return=annual_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe,
        win_rate=win_rate,
        round_trip_win_rate=round_trip_win_rate,
        trade_count=trade_count,
        final_equity=final,
        benchmark_total_return=benchmark_total_return,
        benchmark_annual_return=benchmark_annual_return,
        excess_return=total_return - benchmark_total_return,
    )
