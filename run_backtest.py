#!/usr/bin/env python3
"""量化策略回测入口。"""

from __future__ import annotations

import argparse
import json
import os
import sys

import yaml

# 将 src 加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from data.kline_client import KlineClient, load_csv
from strategy.factory import STRATEGIES, build_strategy, build_strategy_from_args
from backtest.engine import BacktestConfig, BacktestEngine


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="量化策略回测")
    parser.add_argument("-c", "--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--csv", help="使用本地 CSV 而非行情 API（离线演示）")
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES,
        help="策略类型（CSV 模式可用；未指定时读 config 或默认 ma_cross）",
    )
    parser.add_argument("--export", help="导出带信号与净值的结果 CSV")
    args = parser.parse_args()

    if not args.csv and not os.path.exists(args.config):
        print(f"未找到 {args.config}，请复制 config.example.yaml 为 config.yaml")
        print("或使用 --csv sample_data/demo_kline.csv 进行离线演示")
        sys.exit(1)

    if args.csv:
        bars = load_csv(args.csv)
        symbol = "CSV"
        bt = {"strategy": args.strategy or "ma_cross"}
        strategy, strategy_label = build_strategy(bt)
        bcfg = BacktestConfig(trade_on="next_open")
    else:
        cfg = load_config(args.config)
        q = cfg["quotation"]
        bt = dict(cfg["backtest"])
        if args.strategy:
            bt["strategy"] = args.strategy
        client = KlineClient(q["base_url"], q["kline_path"])
        bars = client.fetch_daily(
            symbol=bt["symbol"],
            market=bt["market"],
            page_size=bt.get("page_size", 500),
        )
        symbol = bt["symbol"]
        strategy, strategy_label = build_strategy(bt)
        bcfg = BacktestConfig(
            initial_capital=bt.get("initial_capital", 1_000_000),
            commission_rate=bt.get("commission_rate", 0.0003),
            slippage_rate=bt.get("slippage_rate", 0.0001),
            trade_on=bt.get("trade_on", "next_open"),
        )

    engine = BacktestEngine(bcfg)
    result = engine.run(strategy, bars)

    print("=" * 50)
    print(f"标的: {symbol}")
    print(f"策略: {strategy_label}")
    print(f"K线根数: {len(bars)}")
    print("-" * 50)
    print("绩效指标:")
    print(json.dumps(result.metrics.to_dict(), indent=2, ensure_ascii=False))
    print("-" * 50)
    print(f"成交笔数: {len(result.trades)}")
    if result.trades:
        last = result.trades[-10:]
        print("最近交易:")
        for t in last:
            print(f"  {t}")

    if args.export:
        out = result.bars.copy()
        out["equity"] = result.equity_curve.values
        out.to_csv(args.export, index=False)
        print(f"\n结果已导出: {args.export}")


if __name__ == "__main__":
    main()
