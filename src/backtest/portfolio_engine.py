"""多标的组合回测引擎（等权调仓）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

import pandas as pd

from backtest.metrics import BacktestMetrics, buy_hold_equity_from_panel, compute_metrics
from strategy.portfolio_selector import PortfolioSelector

TradeOn = Literal["close", "next_open"]


@dataclass
class PortfolioBacktestConfig:
    initial_capital: float = 1_000_000
    commission_rate: float = 0.0003
    slippage_rate: float = 0.0001
    trade_on: TradeOn = "next_open"
    rebalance_days: int = 20
    bars_per_year: int = 252


@dataclass
class PortfolioBacktestResult:
    equity_curve: pd.Series
    rebalance_log: List[dict] = field(default_factory=list)
    trades: List[dict] = field(default_factory=list)
    metrics: Optional[BacktestMetrics] = None


class PortfolioBacktestEngine:
    def __init__(self, config: PortfolioBacktestConfig):
        self.config = config

    def run(
        self,
        selector: PortfolioSelector,
        close_panel: pd.DataFrame,
        open_panel: pd.DataFrame,
    ) -> PortfolioBacktestResult:
        cash = self.config.initial_capital
        holdings: Dict[str, float] = {}
        entry_cost: Dict[str, float] = {}
        trades: List[dict] = []
        rebalance_log: List[dict] = []
        equity: List[float] = []
        times = close_panel.index.to_list()

        pending_targets: Optional[List[str]] = None
        pending_signal_idx: Optional[int] = None

        for i, t in enumerate(times):
            # 执行上一调仓日的挂单
            if pending_targets is not None and pending_signal_idx is not None:
                exec_idx = self._execution_index(pending_signal_idx, len(times))
                if exec_idx is not None and i == exec_idx:
                    cash, holdings, entry_cost, new_trades = self._rebalance(
                        cash,
                        holdings,
                        entry_cost,
                        pending_targets,
                        close_panel,
                        open_panel,
                        i,
                        int(t),
                    )
                    trades.extend(new_trades)
                    pending_targets = None
                    pending_signal_idx = None

            # 调仓信号日
            warmup = selector.warmup_period
            if i >= warmup and (i - warmup) % self.config.rebalance_days == 0:
                selected = selector.select(close_panel, i)
                rebalance_log.append({
                    "time": int(t),
                    "selected": selected,
                    "scores": selector.score_snapshot(close_panel, i, selected),
                })
                if self.config.trade_on == "close":
                    cash, holdings, entry_cost, new_trades = self._rebalance(
                        cash,
                        holdings,
                        entry_cost,
                        selected,
                        close_panel,
                        open_panel,
                        i,
                        int(t),
                    )
                    trades.extend(new_trades)
                else:
                    pending_targets = selected
                    pending_signal_idx = i

            equity.append(self._portfolio_value(cash, holdings, close_panel, i))

        equity_series = pd.Series(equity, index=close_panel.index, name="equity")
        benchmark_equity = buy_hold_equity_from_panel(
            close_panel, self.config.initial_capital
        )
        metrics = compute_metrics(
            equity_series,
            trades,
            self.config.bars_per_year,
            benchmark_equity=benchmark_equity,
        )
        return PortfolioBacktestResult(
            equity_curve=equity_series,
            rebalance_log=rebalance_log,
            trades=trades,
            metrics=metrics,
        )

    def _execution_index(self, signal_idx: int, n: int) -> Optional[int]:
        if self.config.trade_on == "close":
            return signal_idx
        nxt = signal_idx + 1
        return nxt if nxt < n else None

    def _execution_price(
        self,
        symbol: str,
        close_panel: pd.DataFrame,
        open_panel: pd.DataFrame,
        idx: int,
    ) -> Optional[float]:
        if self.config.trade_on == "close":
            px = close_panel.iloc[idx][symbol]
        else:
            px = open_panel.iloc[idx][symbol]
        if pd.isna(px):
            return None
        return float(px)

    def _portfolio_value(
        self,
        cash: float,
        holdings: Dict[str, float],
        close_panel: pd.DataFrame,
        idx: int,
    ) -> float:
        total = cash
        row = close_panel.iloc[idx]
        for sym, shares in holdings.items():
            px = row.get(sym)
            if pd.notna(px):
                total += shares * float(px)
        return total

    def _rebalance(
        self,
        cash: float,
        holdings: Dict[str, float],
        entry_cost: Dict[str, float],
        targets: List[str],
        close_panel: pd.DataFrame,
        open_panel: pd.DataFrame,
        exec_idx: int,
        trade_time: int,
    ):
        trades: List[dict] = []
        row_close = close_panel.iloc[exec_idx]

        # 先卖出不在目标组合中的标的
        for sym in list(holdings.keys()):
            if sym in targets:
                continue
            px = self._execution_price(sym, close_panel, open_panel, exec_idx)
            if px is None or holdings[sym] <= 0:
                holdings.pop(sym, None)
                entry_cost.pop(sym, None)
                continue
            sell_px = px * (1 - self.config.slippage_rate)
            shares = holdings[sym]
            proceeds = shares * sell_px
            fee = proceeds * self.config.commission_rate
            cost_basis = entry_cost.get(sym, sell_px) * shares
            pnl = proceeds - fee - cost_basis
            cash += proceeds - fee
            trades.append({
                "time": trade_time,
                "symbol": sym,
                "side": "SELL",
                "price": sell_px,
                "shares": shares,
                "fee": fee,
                "pnl": pnl,
            })
            holdings.pop(sym)
            entry_cost.pop(sym, None)

        if not targets:
            return cash, holdings, entry_cost, trades

        equity = cash + sum(
            holdings.get(s, 0) * float(row_close[s])
            for s in holdings
            if pd.notna(row_close.get(s))
        )
        target_value = equity / len(targets)

        # 买入/调整目标标的
        for sym in targets:
            px = self._execution_price(sym, close_panel, open_panel, exec_idx)
            if px is None:
                continue
            current_value = holdings.get(sym, 0) * float(row_close[sym]) if sym in holdings else 0.0
            delta_value = target_value - current_value
            if abs(delta_value) < 1e-6:
                continue

            if delta_value > 0:
                buy_px = px * (1 + self.config.slippage_rate)
                buy_cash = min(delta_value, cash)
                if buy_cash <= 0:
                    continue
                add_shares = buy_cash / buy_px
                fee = buy_cash * self.config.commission_rate
                cash -= buy_cash + fee
                old_shares = holdings.get(sym, 0.0)
                old_cost = entry_cost.get(sym, buy_px)
                new_shares = old_shares + add_shares
                if new_shares > 0:
                    entry_cost[sym] = (
                        (old_shares * old_cost + add_shares * buy_px) / new_shares
                    )
                holdings[sym] = new_shares
                trades.append({
                    "time": trade_time,
                    "symbol": sym,
                    "side": "BUY",
                    "price": buy_px,
                    "shares": add_shares,
                    "fee": fee,
                })
            else:
                sell_px = px * (1 - self.config.slippage_rate)
                reduce_value = -delta_value
                sell_shares = min(holdings.get(sym, 0), reduce_value / sell_px)
                if sell_shares <= 0:
                    continue
                proceeds = sell_shares * sell_px
                fee = proceeds * self.config.commission_rate
                cost_basis = entry_cost.get(sym, sell_px) * sell_shares
                pnl = proceeds - fee - cost_basis
                cash += proceeds - fee
                holdings[sym] -= sell_shares
                if holdings[sym] <= 1e-10:
                    holdings.pop(sym)
                    entry_cost.pop(sym, None)
                trades.append({
                    "time": trade_time,
                    "symbol": sym,
                    "side": "SELL",
                    "price": sell_px,
                    "shares": sell_shares,
                    "fee": fee,
                    "pnl": pnl,
                })

        return cash, holdings, entry_cost, trades
