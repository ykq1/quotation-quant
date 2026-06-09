"""策略工厂。"""

from __future__ import annotations

from typing import Any, Tuple

from .base import Strategy
from .bollinger import BollingerStrategy
from .bollinger_breakout import BollingerBreakoutStrategy
from .donchian import DonchianStrategy
from .ma_cross import MaCrossStrategy
from .macd import MacdStrategy
from .momentum import MomentumStrategy
from .rsi import RsiStrategy

STRATEGIES = (
    "ma_cross",
    "rsi",
    "bollinger",
    "bollinger_breakout",
    "macd",
    "donchian",
    "momentum",
)


def build_strategy(bt: dict) -> Tuple[Strategy, str]:
    name = (bt.get("strategy") or "ma_cross").strip().lower()
    if name == "ma_cross":
        fast = bt.get("fast_period", 20)
        slow = bt.get("slow_period", 60)
        return MaCrossStrategy(fast_period=fast, slow_period=slow), f"MA({fast}) x MA({slow}) 交叉"
    if name == "rsi":
        period = bt.get("rsi_period", 14)
        oversold = bt.get("rsi_oversold", 30)
        overbought = bt.get("rsi_overbought", 70)
        return (
            RsiStrategy(period=period, oversold=oversold, overbought=overbought),
            f"RSI({period}) 超卖<{oversold} 超买>{overbought}",
        )
    if name == "bollinger":
        period = bt.get("bollinger_period", 20)
        std_dev = bt.get("bollinger_std", 2.0)
        return (
            BollingerStrategy(period=period, std_dev=std_dev),
            f"布林带({period}, {std_dev}σ) 均值回归",
        )
    if name == "macd":
        fast = bt.get("macd_fast", 12)
        slow = bt.get("macd_slow", 26)
        sig = bt.get("macd_signal", 9)
        return (
            MacdStrategy(fast=fast, slow=slow, signal_period=sig),
            f"MACD({fast},{slow},{sig}) DIF/DEA 交叉",
        )
    if name == "donchian":
        entry = bt.get("donchian_entry_period", 20)
        exit_p = bt.get("donchian_exit_period", 10)
        return (
            DonchianStrategy(entry_period=entry, exit_period=exit_p),
            f"唐奇安通道 突破{entry}日高/跌破{exit_p}日低",
        )
    if name == "bollinger_breakout":
        period = bt.get("bollinger_breakout_period", bt.get("bollinger_period", 20))
        std_dev = bt.get("bollinger_breakout_std", bt.get("bollinger_std", 2.0))
        return (
            BollingerBreakoutStrategy(period=period, std_dev=std_dev),
            f"布林带突破({period}, {std_dev}σ) 上轨入/中轨出",
        )
    if name == "momentum":
        lookback = bt.get("momentum_lookback", 20)
        entry = bt.get("momentum_entry_threshold", 0.0)
        exit_th = bt.get("momentum_exit_threshold", 0.0)
        return (
            MomentumStrategy(
                lookback_period=lookback,
                entry_threshold=entry,
                exit_threshold=exit_th,
            ),
            f"动量({lookback}日) 入>{entry} 出<{exit_th}",
        )
    raise ValueError(f"未知策略: {name}，可选: {', '.join(STRATEGIES)}")


def build_strategy_from_args(strategy: str, **kwargs: Any) -> Tuple[Strategy, str]:
    return build_strategy({"strategy": strategy, **kwargs})
