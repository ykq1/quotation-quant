"""从 refinitiv-api 拉取 K 线数据。"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests


class KlineClient:
    """对接 POST /v1/refinitiv/stock/kline/list/v2"""

    def __init__(self, base_url: str, kline_path: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.kline_path = kline_path if kline_path.startswith("/") else f"/{kline_path}"
        self.timeout = timeout

    def fetch_daily(
        self,
        symbol: str,
        market: str,
        page_size: int = 500,
        end_timestamp_ms: Optional[int] = None,
    ) -> pd.DataFrame:
        url = f"{self.base_url}{self.kline_path}"
        body = {
            "symbol": symbol,
            "type": "D",
            "marketType": market,
            "pageNum": 1,
            "pageSize": page_size,
            "sessionId": 1,
            "endTimeStamp": end_timestamp_ms or int(time.time() * 1000),
            "lag": False,
        }
        resp = requests.post(url, json=body, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()

        rows = self._extract_rows(payload)
        if not rows:
            raise ValueError(f"K线为空: symbol={symbol}, response={payload}")

        df = pd.DataFrame(rows)
        df = self._normalize(df)
        return df.sort_values("time").reset_index(drop=True)

    @staticmethod
    def _extract_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if isinstance(payload.get("data"), list):
            return payload["data"]
        if isinstance(payload.get("result"), list):
            return payload["result"]
        if payload.get("code") in (0, "0", 200, "200") and isinstance(payload.get("data"), list):
            return payload["data"]
        return []

    @staticmethod
    def _normalize(df: pd.DataFrame) -> pd.DataFrame:
        rename = {
            "closePrice": "close",
            "openPrice": "open",
            "highPrice": "high",
            "lowPrice": "low",
            "tradeDate": "date",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

        for col in ("open", "high", "low", "close", "volume", "amount"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "time" not in df.columns and "date" in df.columns:
            df["time"] = pd.to_datetime(df["date"]).astype("int64") // 10**6

        df["time"] = pd.to_numeric(df["time"], errors="coerce")
        df = df.dropna(subset=["close", "time"])
        return df


def load_csv(path: str) -> pd.DataFrame:
    """离线回测：CSV 需含 time, open, high, low, close 列。"""
    df = pd.read_csv(path)
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "time" not in df.columns and "date" in df.columns:
        df["time"] = pd.to_datetime(df["date"]).astype("int64") // 10**6
    return df.sort_values("time").reset_index(drop=True)
