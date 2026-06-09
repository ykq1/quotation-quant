#!/usr/bin/env python3
"""组合级回测入口（动量/多因子选股）。"""

from __future__ import annotations

import argparse
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from backtest.portfolio_engine import PortfolioBacktestConfig, PortfolioBacktestEngine
from data.kline_client import KlineClient
from data.universe_loader import (
    build_price_panels,
    fetch_universe_from_api,
    load_universe_from_dir,
)
from strategy.portfolio_factory import PORTFOLIO_STRATEGIES, build_portfolio_selector


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="组合选股回测（动量/多因子）")
    parser.add_argument("-c", "--config", default="config.yaml", help="配置文件路径")
    parser.add_argument(
        "--strategy",
        choices=PORTFOLIO_STRATEGIES,
        help="组合策略：momentum_rank | factor_rank",
    )
    parser.add_argument(
        "--universe-dir",
        help="离线模式：多标的 CSV 目录（默认 sample_data/universe）",
    )
    parser.add_argument("--export-equity", help="导出组合净值 CSV")
    parser.add_argument("--export-rebalance", help="导出调仓记录 JSON")
    args = parser.parse_args()

    pf: dict = {}
    q: dict = {}
    if os.path.exists(args.config):
        cfg = load_config(args.config)
        pf = dict(cfg.get("portfolio") or {})
        q = cfg.get("quotation") or {}

    if args.strategy:
        pf["strategy"] = args.strategy

    if args.universe_dir:
        bars_map = load_universe_from_dir(args.universe_dir, pf.get("symbols"))
        market = pf.get("market", "OFFLINE")
    elif pf.get("symbols"):
        client = KlineClient(
            q["base_url"],
            q.get("kline_path", "/v1/refinitiv/stock/kline/list/v2"),
        )
        bars_map = fetch_universe_from_api(
            client,
            symbols=pf["symbols"],
            market=pf["market"],
            page_size=pf.get("page_size", 300),
        )
        market = pf["market"]
    else:
        default_dir = os.path.join(os.path.dirname(__file__), "sample_data", "universe")
        if not os.path.isdir(default_dir):
            print("请先生成演示数据: python sample_data/generate_universe_demo.py")
            sys.exit(1)
        bars_map = load_universe_from_dir(default_dir)
        market = "OFFLINE"

    close_panel, open_panel, volume_panel, _ = build_price_panels(bars_map)
    selector, strategy_label = build_portfolio_selector(pf, volume_panel)

    pcfg = PortfolioBacktestConfig(
        initial_capital=pf.get("initial_capital", 1_000_000),
        commission_rate=pf.get("commission_rate", 0.0003),
        slippage_rate=pf.get("slippage_rate", 0.0001),
        trade_on=pf.get("trade_on", "next_open"),
        rebalance_days=pf.get("rebalance_days", 20),
    )
    engine = PortfolioBacktestEngine(pcfg)
    result = engine.run(selector, close_panel, open_panel)

    print("=" * 50)
    print(f"市场/模式: {market}")
    print(f"股票池: {len(bars_map)} 只")
    print(f"策略: {strategy_label}")
    print(f"调仓周期: 每 {pcfg.rebalance_days} 个交易日")
    print(f"回测交易日: {len(close_panel)}")
    print("-" * 50)
    print("绩效指标:")
    print(json.dumps(result.metrics.to_dict(), indent=2, ensure_ascii=False))
    print("-" * 50)
    print(f"调仓次数: {len(result.rebalance_log)}")
    print(f"成交笔数: {len(result.trades)}")
    if result.rebalance_log:
        print("最近调仓:")
        for row in result.rebalance_log[-3:]:
            print(f"  {row}")

    if args.export_equity:
        out = result.equity_curve.reset_index()
        out.columns = ["time", "equity"]
        out.to_csv(args.export_equity, index=False)
        print(f"\n净值已导出: {args.export_equity}")

    if args.export_rebalance:
        with open(args.export_rebalance, "w", encoding="utf-8") as f:
            json.dump(result.rebalance_log, f, indent=2, ensure_ascii=False)
        print(f"调仓记录已导出: {args.export_rebalance}")


if __name__ == "__main__":
    main()
