"""多标的 K 线加载。"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .kline_client import KlineClient, load_csv


def load_universe_from_dir(
    directory: str,
    symbols: Optional[List[str]] = None,
) -> Dict[str, pd.DataFrame]:
    """从目录加载多只股票 CSV，文件名如 600519.SH.csv。"""
    if not os.path.isdir(directory):
        raise FileNotFoundError(f"目录不存在: {directory}")

    files = sorted(f for f in os.listdir(directory) if f.endswith(".csv"))
    if symbols:
        wanted = {s if s.endswith(".csv") else f"{s}.csv" for s in symbols}
        files = [f for f in files if f in wanted]

    if not files:
        raise ValueError(f"目录无 CSV: {directory}")

    result: Dict[str, pd.DataFrame] = {}
    for fname in files:
        symbol = fname[:-4]
        df = load_csv(os.path.join(directory, fname))
        if len(df) > 0:
            result[symbol] = df
    if not result:
        raise ValueError(f"未加载到有效 K 线: {directory}")
    return result


def fetch_universe_from_api(
    client: KlineClient,
    symbols: List[str],
    market: str,
    page_size: int = 300,
) -> Dict[str, pd.DataFrame]:
    """逐个标的拉取日 K，拉取失败的标的跳过。"""
    result: Dict[str, pd.DataFrame] = {}
    errors: List[str] = []
    for symbol in symbols:
        try:
            df = client.fetch_daily(symbol=symbol, market=market, page_size=page_size)
            if len(df) > 0:
                result[symbol] = df
        except Exception as e:
            errors.append(f"{symbol}: {e}")
    if not result:
        raise ValueError("所有标的 K 线拉取失败: " + "; ".join(errors))
    if errors:
        print(f"[warn] 跳过 {len(errors)} 只标的: {errors[0]}" + (
            f" 等" if len(errors) > 1 else ""
        ))
    return result


def build_price_panels(
    bars_by_symbol: Dict[str, pd.DataFrame],
) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame], pd.Index]:
    """
    合成宽表：index=time(ms)，columns=symbol。
    返回 close_panel, open_panel, volume_panel(可 None), time_index。
    """
    close_frames = []
    open_frames = []
    volume_frames = []
    has_volume = False
    for symbol, df in bars_by_symbol.items():
        indexed = df.set_index("time")
        close_frames.append(indexed["close"].rename(symbol))
        if "open" in indexed.columns:
            open_frames.append(indexed["open"].rename(symbol))
        else:
            open_frames.append(indexed["close"].rename(symbol))
        if "volume" in indexed.columns:
            has_volume = True
            volume_frames.append(indexed["volume"].rename(symbol))

    close_panel = pd.concat(close_frames, axis=1).sort_index()
    open_panel = pd.concat(open_frames, axis=1).sort_index()
    close_panel = close_panel.ffill()
    open_panel = open_panel.ffill()
    volume_panel = None
    if has_volume and volume_frames:
        volume_panel = pd.concat(volume_frames, axis=1).sort_index().ffill()
    times = close_panel.index.to_list()
    return close_panel, open_panel, volume_panel, pd.Index(times, name="time")
