"""生成离线演示用日 K CSV。"""

import os
import numpy as np
import pandas as pd

np.random.seed(42)
n = 300
base = 100.0
rets = np.random.normal(0.0003, 0.015, n)
close = base * np.cumprod(1 + rets)
high = close * (1 + np.abs(np.random.normal(0, 0.005, n)))
low = close * (1 - np.abs(np.random.normal(0, 0.005, n)))
open_ = np.roll(close, 1)
open_[0] = base
times = pd.date_range("2024-01-02", periods=n, freq="B").astype("int64") // 10**6

df = pd.DataFrame({
    "time": times,
    "open": open_,
    "high": high,
    "low": low,
    "close": close,
    "volume": np.random.randint(1_000_000, 5_000_000, n),
})

out = os.path.join(os.path.dirname(__file__), "demo_kline.csv")
df.to_csv(out, index=False)
print(f"written {out}")
