# quotation-quant

基于当前行情系统（`refinitiv-api` K 线接口）的量化回测模块，支持 **7 种单标的策略** 与 **2 种组合选股策略**。  
完整策略说明见 [docs/QUANT_STRATEGIES.md](docs/QUANT_STRATEGIES.md)。

## 架构

```
行情服务 (refinitiv-api)
    POST /v1/refinitiv/stock/kline/list/v2
              │
              ▼
    KlineClient ──► MaCrossStrategy ──► BacktestEngine ──► 绩效报告
```

与现有系统的关系：

| 能力 | 行情系统已有 | 本模块 |
|------|-------------|--------|
| 日 K 数据 | `/kline/list/v2` | `KlineClient` 调用 |
| SMA 指标 | datasource `SmaCalculator` | 策略内 pandas 计算 |
| 回测/下单 | 无 | `BacktestEngine` |

## 快速开始

### 1. 安装依赖

```bash
cd quotation-quant
pip install -r requirements.txt
```

### 2. 离线演示（无需启动行情服务）

```bash
python sample_data/generate_demo.py
python run_backtest.py --csv sample_data/demo_kline.csv
```

### 3. 对接真实行情

```bash
cp config.example.yaml config.yaml
# 修改 base_url 为 refinitiv-api 地址
python run_backtest.py -c config.yaml --export result.csv
```

### config.yaml 示例

```yaml
quotation:
  base_url: "http://127.0.0.1:8080"
  kline_path: "/v1/refinitiv/stock/kline/list/v2"

backtest:
  symbol: "00700.HK"
  market: "HK"
  fast_period: 20
  slow_period: 60
  initial_capital: 1000000
  commission_rate: 0.0003
  trade_on: "next_open"   # 信号日次日开盘成交，更贴近实盘
```

## 策略一览

**单标的**（`run_backtest.py --strategy <id>`）：`ma_cross` `macd` `donchian` `bollinger_breakout` `momentum` `rsi` `bollinger`

**组合选股**（`run_portfolio_backtest.py --strategy <id>`）：`momentum_rank` `factor_rank`

- 仅做多；默认信号日 **次日开盘价** 成交（`trade_on: next_open`）
- 详见 [docs/QUANT_STRATEGIES.md](docs/QUANT_STRATEGIES.md)

## 输出指标

| 指标 | 含义 |
|------|------|
| total_return | 总收益率 |
| annual_return | 年化收益（按 252 交易日） |
| max_drawdown | 最大回撤 |
| sharpe_ratio | 夏普比率 |
| win_rate | 胜率（盈利笔数/全部笔数） |
| round_trip_win_rate | 回合胜率（盈利卖出/卖出总数） |
| trade_count | 交易次数 |

### 4. 组合回测（动量/多因子选股）

```bash
python3 sample_data/generate_universe_demo.py
python3 run_portfolio_backtest.py --universe-dir sample_data/universe --strategy factor_rank
```

## 扩展方向

1. **实盘信号**：订阅 Socket 2102/2114，策略产出信号后对接下单系统
2. **基本面因子**：PE/PB/ROE 接入多因子选股
3. **自动股票池**：码表 `/market/all` 批量拉 K 线
4. **与 Java 指标对齐**：可改为调用 `/v1/datasource/ai/v2/stock/indicator` 的 SMA 结果

## 目录结构

```
quotation-quant/
├── run_backtest.py              # 单标的回测
├── run_portfolio_backtest.py    # 组合回测
├── config.yaml
├── docs/QUANT_STRATEGIES.md     # 策略手册
├── src/
│   ├── data/                    # kline_client, universe_loader
│   ├── strategy/                # 7 单标的 + 2 组合策略
│   └── backtest/                # engine, portfolio_engine, metrics
└── sample_data/                 # demo_kline.csv, universe/
```
