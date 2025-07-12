# 量化交易系统

一个功能完整的加密货币量化交易系统，支持策略配置、历史数据回测、模拟交易和实盘交易。

## 功能特性

### 🎯 策略管理
- **多种技术分析策略**：移动平均线交叉、布林带、MACD、RSI等
- **策略参数配置**：灵活调整策略参数
- **策略组合**：支持多策略组合使用

### 📊 回测系统
- **历史数据回测**：基于真实历史数据测试策略
- **性能指标**：总收益率、最大回撤、夏普比率、胜率等
- **可视化结果**：权益曲线图表展示

### 💹 交易功能
- **模拟交易**：无风险策略测试
- **实盘交易**：支持Binance等主流交易所
- **风险控制**：止损止盈、仓位管理
- **实时监控**：持仓状态、交易历史

### 📈 数据管理
- **多数据源**：Yahoo Finance、CCXT等
- **历史数据**：支持多种时间周期
- **实时数据**：最新价格获取

### 🌐 Web界面
- **可视化管理**：直观的Web界面
- **实时监控**：策略运行状态
- **图表展示**：价格走势、回测结果

## 系统架构

```
quantTrading/
├── config/                 # 配置模块
│   ├── __init__.py
│   └── settings.py        # 系统配置
├── data/                  # 数据管理模块
│   ├── __init__.py
│   ├── manager.py         # 数据管理器
│   └── models.py          # 数据模型
├── strategies/            # 策略模块
│   ├── __init__.py
│   ├── base.py           # 策略基类
│   ├── factory.py        # 策略工厂
│   ├── ma_cross.py       # 移动平均线策略
│   ├── bollinger_bands.py # 布林带策略
│   ├── macd.py           # MACD策略
│   └── rsi.py            # RSI策略
├── backtest/             # 回测模块
│   ├── __init__.py
│   ├── engine.py         # 回测引擎
│   └── manager.py        # 回测管理器
├── trading/              # 交易模块
│   ├── __init__.py
│   ├── engine.py         # 交易引擎
│   └── manager.py        # 交易管理器
├── api/                  # API模块
│   ├── __init__.py
│   └── routes.py         # API路由
├── web/                  # Web界面模块
│   ├── __init__.py
│   └── interface.py      # Web界面
├── utils/                # 工具模块
│   ├── __init__.py
│   ├── database.py       # 数据库工具
│   └── models.py         # 数据模型
├── tests/                # 测试模块
│   ├── __init__.py
│   └── system_test.py    # 系统测试
├── logs/                 # 日志目录
├── docs/                 # 文档目录
├── main.py               # 主程序
├── start_web.py          # Web界面启动脚本
├── requirements.txt      # 依赖包
├── env_example.txt       # 环境变量示例
└── README.md            # 项目说明
```

## 安装部署

### 1. 环境要求
- Python 3.8+
- SQLite数据库
- 网络连接（用于获取市场数据）

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
复制 `env_example.txt` 为 `.env` 并修改配置：
```bash
cp env_example.txt .env
```

主要配置项：
- `DATA_SOURCE`: 数据源（yfinance/ccxt）
- `DEFAULT_CAPITAL`: 默认资金
- `API_KEY/API_SECRET`: 交易所API密钥（实盘交易需要）

### 4. 启动系统

#### 方法一：分别启动（推荐）
**启动API服务**（必需）：
```bash
python start_api.py
# 或者双击 start_api.bat
```

**启动Web界面**（可选）：
```bash
python start_web.py
# 或者双击 start_web.bat
```

#### 方法二：同时启动
```bash
python start_all.py
```

**访问地址**：
- API服务：http://localhost:8000
- Web界面：http://localhost:8050
- API文档：http://localhost:8000/docs

**注意**：必须先启动API服务，再启动Web界面，因为Web界面需要调用API服务。

## 使用指南

### 1. 策略管理

#### 创建策略
```python
from strategies.factory import StrategyFactory

# 创建移动平均线交叉策略
strategy = StrategyFactory.create_strategy("ma_cross", {
    "short_window": 10,
    "long_window": 30,
    "rsi_period": 14
})
```

#### 可用策略类型
- `ma_cross`: 移动平均线交叉策略
- `bollinger_bands`: 布林带策略
- `macd`: MACD策略
- `rsi`: RSI策略
- `funding_rate_arbitrage`: 资金费率套利策略

### 2. 回测系统

#### 运行回测
```python
from backtest.engine import BacktestEngine

# 创建回测引擎
engine = BacktestEngine(initial_capital=10000.0)

# 运行回测
results = engine.run_backtest(
    strategy=strategy,
    symbol="BTC-USD",
    start_date="2023-01-01",
    end_date="2023-12-31",
    timeframe="1d"
)

print(f"总收益率: {results['results']['total_return']:.2%}")
```

#### 资金费率套利策略
```json
{
    "funding_rate_threshold": 0.005,    // 资金费率阈值 (0.5%)
    "max_positions": 10,                // 最大持仓数量
    "min_volume": 1000000,              // 最小24小时成交量
    "exchanges": ["binance", "okx", "bybit"]  // 支持的交易所
}
```

**策略说明**：
- 自动监控多个交易所的永续合约资金费率
- 当资金费率绝对值 ≥ 0.5% 时，将合约加入待选池
- 当资金费率绝对值 < 0.5% 时，将合约移出待选池
- 通过Telegram实时推送合约进出池子的通知
- 支持设置最大持仓数量和最小成交量过滤
- 正费率做多获得资金费，负费率做空获得资金费

**使用示例**：
```python
from strategies.factory import StrategyFactory

# 创建资金费率套利策略
strategy = StrategyFactory.create_strategy("funding_rate_arbitrage", {
    "funding_rate_threshold": 0.005,  # 0.5%
    "max_positions": 10,
    "min_volume": 1000000,
    "exchanges": ["binance", "okx", "bybit"]
})

# 运行策略（会自动发送Telegram通知）
signals = strategy.generate_signals(pd.DataFrame())

# 查看池子状态
pool_status = strategy.get_pool_status()
print(f"当前池子有 {pool_status['pool_size']} 个合约")
```

### 3. 交易系统

#### 模拟交易
```python
from trading.manager import TradingManager

# 创建交易管理器
trading_manager = TradingManager()

# 创建模拟交易引擎
engine = trading_manager.create_engine("demo", "paper", "binance")

# 添加策略
engine.add_strategy(strategy)

# 生成并执行信号
signals = engine.generate_signals("BTC-USD", "1d")
engine.execute_signals(signals)
```

#### 实盘交易
```python
# 创建实盘交易引擎（需要配置API密钥）
engine = trading_manager.create_engine("live", "live", "binance")
```

### 4. API接口

#### 策略管理
```bash
# 获取策略列表
GET /strategies

# 创建策略
POST /strategies
{
    "name": "我的策略",
    "strategy_type": "ma_cross",
    "parameters": {"short_window": 10, "long_window": 30}
}
```

#### 回测
```bash
# 运行回测
POST /backtest
{
    "strategy_id": 1,
    "symbol": "BTC-USD",
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "initial_capital": 10000
}
```

#### 交易
```bash
# 创建交易引擎
POST /trading/engine
{
    "engine_name": "my_engine",
    "strategy_type": "ma_cross",
    "symbol": "BTC-USD",
    "trade_type": "paper"
}
```

### 5. Web界面

访问 `http://localhost:8050` 使用Web界面：

- **策略管理**：创建、编辑、删除策略
- **回测**：配置并运行回测，查看结果
- **交易**：创建交易引擎，监控交易状态
- **市场数据**：查看价格图表，更新数据

## 配置说明

### 策略参数

#### 移动平均线交叉策略
```json
{
    "short_window": 10,      // 短期均线周期
    "long_window": 30,       // 长期均线周期
    "rsi_period": 14,        // RSI周期
    "rsi_overbought": 70,    // RSI超买阈值
    "rsi_oversold": 30       // RSI超卖阈值
}
```

#### 布林带策略
```json
{
    "window": 20,            // 布林带周期
    "num_std": 2,            // 标准差倍数
    "rsi_period": 14         // RSI周期
}
```

#### MACD策略
```json
{
    "fast_period": 12,       // 快线周期
    "slow_period": 26,       // 慢线周期
    "signal_period": 9       // 信号线周期
}
```

#### RSI策略
```json
{
    "rsi_period": 14,        // RSI周期
    "overbought": 70,        // 超买阈值
    "oversold": 30,          // 超卖阈值
    "exit_overbought": 60,   // 退出超买阈值
    "exit_oversold": 40      // 退出超卖阈值
}
```

### 风险控制

- `MAX_POSITION_SIZE`: 最大仓位比例（默认10%）
- `STOP_LOSS_RATIO`: 止损比例（默认5%）
- `TAKE_PROFIT_RATIO`: 止盈比例（默认10%）

## 开发指南

### 添加新策略

1. 在`strategies/`目录下创建新策略文件
2. 继承`BaseStrategy`类
3. 实现`generate_signals`方法
4. 在`factory.py`中注册新策略

```python
# strategies/my_strategy.py
from .base import BaseStrategy, Signal

class MyStrategy(BaseStrategy):
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        # 实现信号生成逻辑
        pass

# strategies/factory.py
from .my_strategy import MyStrategy

strategies = {
    'my_strategy': MyStrategy,
    # ... 其他策略
}
```

### 扩展数据源

1. 在`data/manager.py`中添加新数据源
2. 实现数据获取和格式转换
3. 更新配置选项

### 添加新API接口

1. 在`api/routes.py`中添加新路由
2. 定义请求和响应模型
3. 实现业务逻辑

## 模块说明

### config/ - 配置模块
- `settings.py`: 系统配置，包含数据库、API、交易等配置参数

### data/ - 数据管理模块
- `manager.py`: 数据管理器，负责获取和管理市场数据
- `models.py`: 数据模型，定义市场数据结构

### strategies/ - 策略模块
- `base.py`: 策略基类，定义策略接口
- `factory.py`: 策略工厂，用于创建策略实例
- `ma_cross.py`: 移动平均线交叉策略
- `bollinger_bands.py`: 布林带策略
- `macd.py`: MACD策略
- `rsi.py`: RSI策略

### backtest/ - 回测模块
- `engine.py`: 回测引擎，执行历史数据回测
- `manager.py`: 回测管理器，管理回测任务

### trading/ - 交易模块
- `engine.py`: 交易引擎，执行模拟和实盘交易
- `manager.py`: 交易管理器，管理交易引擎

### api/ - API模块
- `routes.py`: REST API路由，提供HTTP接口

### web/ - Web界面模块
- `interface.py`: Dash Web界面，提供可视化界面

### utils/ - 工具模块
- `database.py`: 数据库工具，提供数据库连接和操作
- `models.py`: 数据模型，定义数据库表结构

### tests/ - 测试模块
- `system_test.py`: 系统测试，验证各模块功能

## 注意事项

### 风险提示
- 量化交易存在风险，请谨慎使用
- 建议先在模拟环境中测试
- 实盘交易前请充分了解风险

### 数据限制
- Yahoo Finance有API调用限制
- 建议合理控制数据更新频率
- 考虑使用付费数据源获得更好服务

### 性能优化
- 大量数据回测时注意内存使用
- 考虑使用数据库缓存历史数据
- 优化策略计算效率

## 故障排除

### 常见问题

1. **数据获取失败**
   - 检查网络连接
   - 验证交易对名称
   - 确认数据源配置

2. **回测结果异常**
   - 检查策略参数
   - 验证历史数据完整性
   - 确认时间范围设置

3. **交易执行失败**
   - 检查API密钥配置
   - 验证账户余额
   - 确认交易对可用性

### 日志查看
```bash
tail -f logs/quant_trading.log
```

## 贡献指南

欢迎提交Issue和Pull Request！

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 发起Pull Request

## 许可证

MIT License

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交Issue
- 发送邮件

---

**免责声明**：本系统仅供学习和研究使用，不构成投资建议。使用本系统进行实际交易的风险由用户自行承担。
