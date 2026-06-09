"""事件驱动简易回测引擎（仅做多）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

import pandas as pd

from backtest.metrics import BacktestMetrics, compute_metrics
from strategy.base import Strategy

TradeOn = Literal["close", "next_open"]


@dataclass
class BacktestConfig:
    initial_capital: float = 1_000_000
    commission_rate: float = 0.0003
    slippage_rate: float = 0.0001
    trade_on: TradeOn = "next_open"
    bars_per_year: int = 252


@dataclass
class BacktestResult:
    bars: pd.DataFrame
    equity_curve: pd.Series
    trades: List[dict] = field(default_factory=list)
    metrics: Optional[BacktestMetrics] = None


class BacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config

    def run(self, strategy: Strategy, bars: pd.DataFrame) -> BacktestResult:
        df = strategy.generate_signals(bars)
        cash = self.config.initial_capital
        shares = 0.0
        entry_price = 0.0
        trades: List[dict] = []
        equity: List[float] = []

        for i in range(len(df)):
            row = df.iloc[i]
            price = self._execution_price(df, i)
            close_px = float(row["close"])

            if row["signal"] == 1 and shares == 0 and price is not None:
                cost = price * (1 + self.config.slippage_rate)
                shares = cash / cost
                fee = cash * self.config.commission_rate
                cash = 0
                entry_price = cost
                trades.append({
                    "time": int(row["time"]),
                    "side": "BUY",
                    "price": cost,
                    "shares": shares,
                    "fee": fee,
                })

            elif row["signal"] == -1 and shares > 0 and price is not None:
                sell_px = price * (1 - self.config.slippage_rate)
                proceeds = shares * sell_px
                fee = proceeds * self.config.commission_rate
                pnl = proceeds - fee - shares * entry_price
                cash = proceeds - fee
                trades.append({
                    "time": int(row["time"]),
                    "side": "SELL",
                    "price": sell_px,
                    "shares": shares,
                    "fee": fee,
                    "pnl": pnl,
                })
                shares = 0
                entry_price = 0

            mark = shares * close_px + cash
            equity.append(mark)

        equity_series = pd.Series(equity, index=df.index, name="equity")
        metrics = compute_metrics(equity_series, trades, self.config.bars_per_year)
        return BacktestResult(bars=df, equity_curve=equity_series, trades=trades, metrics=metrics)

    def _execution_price(self, df: pd.DataFrame, i: int) -> Optional[float]:
        if self.config.trade_on == "close":
            return float(df.iloc[i]["close"])
        if i + 1 >= len(df):
            return None
        nxt = df.iloc[i + 1]
        if "open" in nxt and pd.notna(nxt["open"]):
            return float(nxt["open"])
        return float(nxt["close"])
