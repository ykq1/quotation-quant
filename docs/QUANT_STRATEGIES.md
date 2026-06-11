# 量化策略手册

本文档说明 `quotation-quant` 模块中**已实现的全部策略**、回测方式、配置项与扩展方向。  
行情数据来自 `refinitiv-api`：`POST /v1/refinitiv/stock/kline/list/v2`。

---

## 一、回测架构概览

项目包含 **两套回测体系**：

```
┌─────────────────────────────────────────────────────────────────┐
│  单标的择时回测（run_backtest.py）                                │
│  一只股 → 生成 signal → 全仓买卖 → 净值曲线                        │
├─────────────────────────────────────────────────────────────────┤
│  组合选股回测（run_portfolio_backtest.py）                       │
│  股票池 → 截面排名/打分 → 等权调仓 → 组合净值                      │
└─────────────────────────────────────────────────────────────────┘
```

| 体系 | 入口 | 引擎 | 策略工厂 |
|------|------|------|----------|
| 单标的 | `run_backtest.py` | `BacktestEngine` | `strategy/factory.py` |
| 组合 | `run_portfolio_backtest.py` | `PortfolioBacktestEngine` | `strategy/portfolio_factory.py` |

**共性约束**（当前版本）：

- 仅做多，不做空
- 默认 `trade_on: next_open`（信号日次日开盘成交）
- 含单边手续费 `commission_rate`、滑点 `slippage_rate`
- 日 K 数据，周期参数单位均为 **交易日**

---

## 二、已实现策略总览

### 2.1 单标的策略（7 种）

| 策略 ID | 类型 | 源文件 | 一句话 |
|---------|------|--------|--------|
| `ma_cross` | 趋势跟踪 | `ma_cross.py` | 双均线金叉买、死叉卖 |
| `macd` | 趋势跟踪 | `macd.py` | DIF/DEA 金叉死叉 |
| `donchian` | 趋势跟踪 | `donchian.py` | 唐奇安通道突破（海龟法则） |
| `bollinger_breakout` | 趋势跟踪 | `bollinger_breakout.py` | 突破布林上轨买、跌破中轨卖 |
| `momentum` | 趋势跟踪 | `momentum.py` | 单股 N 日涨幅动量择时 |
| `rsi` | 均值回归 | `rsi.py` | RSI 超卖买、超买卖 |
| `bollinger` | 均值回归 | `bollinger.py` | 跌破布林下轨买、突破上轨卖 |

### 2.2 组合选股策略（2 种）

| 策略 ID | 类型 | 源文件 | 一句话 |
|---------|------|--------|--------|
| `momentum_rank` | 因子选股 | `momentum_rank.py` | 股票池按 N 日涨幅排名，持 Top N |
| `factor_rank` | 因子选股 | `factor_rank.py` | 多因子 z-score 加权，持 Top N |

---

## 三、单标的策略详解

统一信号语义：`signal=1` 买入，`signal=-1` 平仓，`signal=0` 不操作。  
引擎仅在 **空仓时响应买入、持仓时响应卖出**。

### 3.1 双均线交叉 `ma_cross`

| 信号 | 条件 |
|------|------|
| 买入 | MA(快) 上穿 MA(慢) |
| 卖出 | MA(快) 下穿 MA(慢) |

```yaml
backtest:
  strategy: ma_cross
  fast_period: 20    # 必须 < slow_period
  slow_period: 60
```

```bash
python3 run_backtest.py -c config.yaml --strategy ma_cross
python3 run_backtest.py --csv sample_data/demo_kline.csv --strategy ma_cross
```

---

### 3.2 MACD 交叉 `macd`

| 信号 | 条件 |
|------|------|
| 买入 | DIF 上穿 DEA |
| 卖出 | DIF 下穿 DEA |

默认参数：12 / 26 / 9。输出列：`macd_dif`、`macd_dea`、`macd_hist`。

```yaml
backtest:
  strategy: macd
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9
```

---

### 3.3 唐奇安通道 `donchian`

海龟交易法风格，需 `high`/`low` 列（API 与 demo CSV 均提供）。

| 信号 | 条件 |
|------|------|
| 买入 | 收盘价突破前 N 日最高价 |
| 卖出 | 收盘价跌破前 M 日最低价 |

通道用 `shift(1)` 计算，不含当日高低点。

```yaml
backtest:
  strategy: donchian
  donchian_entry_period: 20   # 入场突破周期
  donchian_exit_period: 10    # 出场跌破周期
```

---

### 3.4 布林带突破 `bollinger_breakout`

与 `bollinger`（均值回归）**方向相反**，同属布林带指标。

| 信号 | 条件 |
|------|------|
| 买入 | 收盘价突破上轨 |
| 卖出 | 收盘价跌破中轨（均线） |

```yaml
backtest:
  strategy: bollinger_breakout
  bollinger_breakout_period: 20
  bollinger_breakout_std: 2.0
```

---

### 3.5 单标的动量 `momentum`

> 注意：与组合策略 `momentum_rank` 不同，本策略只对 **一只股票** 做择时。

| 信号 | 条件 |
|------|------|
| 买入 | N 日动量向上突破 `entry_threshold` |
| 卖出 | N 日动量向下跌破 `exit_threshold` |

动量 = `close / close[N日前] - 1`。默认阈值为 0（由负转正买、由正转负卖）。

```yaml
backtest:
  strategy: momentum
  momentum_lookback: 20
  momentum_entry_threshold: 0.0   # 如 0.05 = 20 日涨幅超 5% 才买
  momentum_exit_threshold: 0.0
```

---

### 3.6 RSI 均值回归 `rsi`

Wilder RSI。

| 信号 | 条件 |
|------|------|
| 买入 | RSI 跌入超卖区（前日 ≥ 阈值，当日 < 超卖线） |
| 卖出 | RSI 涨入超买区（前日 ≤ 阈值，当日 > 超买线） |

```yaml
backtest:
  strategy: rsi
  rsi_period: 14
  rsi_oversold: 30
  rsi_overbought: 70
```

---

### 3.7 布林带均值回归 `bollinger`

| 信号 | 条件 |
|------|------|
| 买入 | 收盘价跌破下轨 |
| 卖出 | 收盘价突破上轨 |

```yaml
backtest:
  strategy: bollinger
  bollinger_period: 20
  bollinger_std: 2.0
```

---

### 3.8 单标的策略对比

| 策略 | 适合行情 | 信号频率 | 典型问题 |
|------|----------|----------|----------|
| `ma_cross` | 趋势 | 低 | 震荡市假交叉 |
| `macd` | 趋势 | 中 | 滞后 |
| `donchian` | 强趋势突破 | 低 | 假突破、回撤大 |
| `bollinger_breakout` | 波动突破 | 中 | 震荡市反复止损 |
| `momentum` | 趋势延续 | 中 | 反转时追高杀跌 |
| `rsi` | 震荡 | 中 | 趋势市过早平仓/逆势加仓 |
| `bollinger` | 震荡 | 中 | 趋势市过早卖出 |

**布林带一对策略**：

```
bollinger         → 跌穿下轨买、突破上轨卖（均值回归，低吸高抛）
bollinger_breakout → 突破上轨买、跌破中轨卖（趋势跟踪，追涨）
```

---

## 四、组合选股策略详解

入口：`run_portfolio_backtest.py`  
每 `rebalance_days` 个交易日调仓一次，选中标的 **等权** 持有。

### 4.1 动量因子选股 `momentum_rank`

| 步骤 | 说明 |
|------|------|
| 计算 | 每只股票 N 日收益率 |
| 过滤 | 动量 ≥ `min_momentum` |
| 选取 | 降序排名，取 Top `top_n` |

```yaml
portfolio:
  strategy: momentum_rank
  symbols: ["600519.SH", "603986.SH", ...]
  top_n: 3
  momentum_lookback: 20
  min_momentum: 0.0
  rebalance_days: 20
```

```bash
python3 run_portfolio_backtest.py -c config.yaml --strategy momentum_rank
python3 run_portfolio_backtest.py --universe-dir sample_data/universe --strategy momentum_rank
```

---

### 4.2 多因子选股 `factor_rank`

每个调仓日，对股票池各因子做 **截面 z-score**，再加权求综合分：

| 因子 | 计算 | 偏好 |
|------|------|------|
| `momentum` | N 日收益率 | 越高越好 |
| `low_vol` | N 日收益波动率（取负） | 低波动异象 |
| `reversal` | 短周期收益率取反 | 短期超跌 |
| `volume` | N 日平均成交量对数 | 流动性好 |

> 当前仅用 K 线价量，**无 PE/PB/ROE 等基本面因子**。无成交量数据时自动剔除 `volume` 因子并重新归一化权重。

```yaml
portfolio:
  strategy: factor_rank
  top_n: 3
  factor_lookback: 20
  reversal_lookback: 5
  factor_weights:
    momentum: 0.40
    low_vol: 0.30
    reversal: 0.20
    volume: 0.10
  # min_factor_score: 0.0   # 可选：综合得分下限
```

调仓日志示例：

```json
{
  "time": 1733184000000,
  "selected": ["DEMO_A", "DEMO_C", "DEMO_F"],
  "scores": {"DEMO_A": 1.24, "DEMO_C": 0.87, "DEMO_F": 0.65}
}
```

---

### 4.3 动量选股 vs 单标的动量

| | `momentum`（单标的） | `momentum_rank`（组合） |
|--|---------------------|------------------------|
| 标的数 | 1 | 多 |
| 决策 | 该股动量过线就买/卖 | 比谁涨得多，买最强的几只 |
| 入口 | `run_backtest.py` | `run_portfolio_backtest.py` |
| 仓位 | 全仓进出 | 等权组合 |

---

## 五、快速开始

### 5.1 安装

```bash
cd quotation-quant
pip3 install -r requirements.txt
```

### 5.2 单标的离线演示

```bash
python3 sample_data/generate_demo.py
python3 run_backtest.py --csv sample_data/demo_kline.csv --strategy ma_cross
python3 run_backtest.py --csv sample_data/demo_kline.csv --strategy macd --export result.csv
```

### 5.3 组合离线演示

```bash
python3 sample_data/generate_universe_demo.py
python3 run_portfolio_backtest.py --universe-dir sample_data/universe --strategy factor_rank
```

### 5.4 对接真实行情

```bash
# 单标的：修改 config.yaml 的 backtest.symbol / market
python3 run_backtest.py -c config.yaml --strategy donchian

# 组合：修改 config.yaml 的 portfolio.symbols
python3 run_portfolio_backtest.py -c config.yaml --strategy momentum_rank
```

---

## 六、配置文件说明

完整示例见 [config.yaml](../config.yaml)，分为两段：

| 配置段 | 对应入口 | 主要字段 |
|--------|----------|----------|
| `quotation` | 共用 | `base_url`、`kline_path` |
| `backtest` | `run_backtest.py` | `strategy`、`symbol`、`page_size`、各策略参数 |
| `portfolio` | `run_portfolio_backtest.py` | `strategy`、`symbols`、`top_n`、`rebalance_days` |

**单标的通用字段**：

```yaml
backtest:
  initial_capital: 1000000
  commission_rate: 0.0003
  slippage_rate: 0.0001
  trade_on: next_open      # close | next_open
  page_size: 300           # 建议 ≥ 慢线周期 2～3 倍
```

**组合通用字段**：

```yaml
portfolio:
  market: "SH"
  page_size: 300
  top_n: 3
  rebalance_days: 20
  trade_on: next_open
```

---

## 七、绩效指标

两套回测输出相同的 `BacktestMetrics`：

| 指标 | 含义 |
|------|------|
| `total_return` | 总收益率 |
| `annual_return` | 年化收益率（复利，按 252 交易日） |
| `max_drawdown` | 最大回撤（负数，如 -0.15 = 15%） |
| `sharpe_ratio` | 夏普比率（简化版，未扣无风险利率） |
| `win_rate` | 盈利笔数 / 全部交易笔数（买+卖） |
| `round_trip_win_rate` | 盈利卖出次数 / 卖出总次数（回合胜率） |
| `trade_count` | 交易总笔数 |
| `final_equity` | 期末净值 |
| `benchmark_total_return` | 买入持有基准总收益率（单标的持该股；组合等权持全部标的） |
| `benchmark_annual_return` | 买入持有基准年化收益率 |
| `excess_return` | 超额收益 = 策略总收益 − 基准总收益 |

**年化计算公式**（2 年赚 20% → 年化约 9.54%）：

```
annual_return = (1 + total_return) ^ (252 / 交易日数) - 1
```

---

## 八、回测注意事项

### 单标的

1. **`page_size` 要够长**：如 MA(60) 建议 `page_size ≥ 200`，否则窗口内可能 0 成交。
2. **最后一根 K 线信号**：`next_open` 模式下无法成交（没有次日）。
3. **有 signal ≠ 有 trade**：死叉在无持仓时不记成交；接口有缓存/mock 不代表 Job 跑过。
4. **CSV 离线模式**：`--csv` 时周期参数写死为 MA(20/60)，不读 config；其他策略用 `--strategy` 指定。

### 组合

1. **股票池**：`symbols` 需带市场后缀（如 `600519.SH`）；拉取失败标的会跳过。
2. **等权调仓**：每次调仓按总资产均分到选中标的；不足 `top_n` 只时按实际可选数量持仓。
3. **因子数据**：`factor_rank` 的 `volume` 因子依赖 CSV/API 中的 `volume` 列。

---

## 九、策略分类与未实现方向

### 9.1 分类总览

| 类别 | 本项目已实现 | 未实现 |
|------|-------------|--------|
| 趋势跟踪 | ma_cross, macd, donchian, bollinger_breakout, momentum | 三重均线 |
| 均值回归 | rsi, bollinger | 配对交易、统计套利 |
| 因子选股 | momentum_rank, factor_rank | 价值/质量/市值因子（需基本面） |
| 事件驱动 | — | 财报、公告 NLP |
| 套利 | — | 期现、AH 溢价 |
| 机器学习 | — | XGBoost、LSTM |
| 风控增强 | 手续费/滑点 | 止损止盈、仓位管理、多策略组合 |

### 9.2 选型参考

| 市场状态 | 相对更适合 |
|----------|-----------|
| 单边趋势 | ma_cross、macd、donchian、bollinger_breakout、momentum |
| 横盘震荡 | rsi、bollinger |
| 多股轮动 | momentum_rank、factor_rank |
| 追求稳健 | 多因子 + 低波权重 + 严格风控（待扩展） |

```
趋势跟踪：涨了继续涨 → 顺势
均值回归：涨多了会跌   → 逆势低吸高抛
因子选股：比谁更强     → 截面选优
```

---

## 十、扩展开发指南

### 10.1 新增单标的策略

1. 在 `src/strategy/` 继承 `Strategy`，实现 `generate_signals()`
2. 注册到 `factory.py` 的 `STRATEGIES` 与 `build_strategy()`
3. 在 `config.yaml` 的 `backtest` 段增加参数

### 10.2 新增组合选股策略

1. 继承 `PortfolioSelector`（`portfolio_selector.py`）
2. 实现 `warmup_period`、`select()`、`label()`，可选覆盖 `score_snapshot()`
3. 注册到 `portfolio_factory.py` 的 `PORTFOLIO_STRATEGIES`

### 10.3 建议后续扩展

1. 码表 `/market/all` 自动构建股票池
2. 基本面因子（PE、PB、ROE）接入 datasource
3. 市值加权、行业中性
4. `BacktestEngine` 层止损/分批建仓
5. 与 Java 侧 `SmaCalculator` 指标对齐

---

## 十一、目录结构

```
quotation-quant/
├── run_backtest.py              # 单标的回测入口
├── run_portfolio_backtest.py    # 组合回测入口
├── config.yaml
├── docs/
│   └── QUANT_STRATEGIES.md      # 本文档
├── src/
│   ├── data/
│   │   ├── kline_client.py      # 单标的 K 线
│   │   └── universe_loader.py   # 多标的加载与宽表
│   ├── strategy/
│   │   ├── base.py              # 单标的策略基类
│   │   ├── factory.py           # 单标的策略工厂
│   │   ├── portfolio_selector.py
│   │   ├── portfolio_factory.py
│   │   ├── ma_cross.py / macd.py / donchian.py
│   │   ├── bollinger.py / bollinger_breakout.py
│   │   ├── rsi.py / momentum.py
│   │   ├── momentum_rank.py / factor_rank.py
│   └── backtest/
│       ├── engine.py            # 单标的引擎
│       ├── portfolio_engine.py  # 组合引擎
│       └── metrics.py           # 绩效指标
└── sample_data/
    ├── generate_demo.py         # 单标的 demo
    ├── generate_universe_demo.py # 组合 demo（8 只股票）
    ├── demo_kline.csv
    └── universe/                # DEMO_A.csv ...
```

---

## 十二、相关链接

- 项目入门：[README.md](../README.md)
- 配置文件：[config.yaml](../config.yaml)
- 策略源码：[src/strategy/](../src/strategy/)
