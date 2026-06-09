"""生成多标的离线演示数据（用于动量因子选股回测）。"""

import os

import numpy as np
import pandas as pd

np.random.seed(42)
n = 260
base_dir = os.path.join(os.path.dirname(__file__), "universe")
os.makedirs(base_dir, exist_ok=True)

# 不同股票设置不同 drift，便于动量排名分化
profiles = {
    "DEMO_A": 0.0015,
    "DEMO_B": 0.0008,
    "DEMO_C": 0.0002,
    "DEMO_D": -0.0003,
    "DEMO_E": -0.0008,
    "DEMO_F": 0.0010,
    "DEMO_G": 0.0005,
    "DEMO_H": -0.0001,
}

times = pd.date_range("2024-01-02", periods=n, freq="B").astype("int64") // 10**6

for symbol, drift in profiles.items():
    base = 100.0 + np.random.uniform(-10, 10)
    rets = np.random.normal(drift, 0.012, n)
    close = base * np.cumprod(1 + rets)
    high = close * (1 + np.abs(np.random.normal(0, 0.004, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.004, n)))
    open_ = np.roll(close, 1)
    open_[0] = base
    df = pd.DataFrame({
        "time": times,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": np.random.randint(500_000, 3_000_000, n),
    })
    path = os.path.join(base_dir, f"{symbol}.csv")
    df.to_csv(path, index=False)
    print(f"written {path}")
