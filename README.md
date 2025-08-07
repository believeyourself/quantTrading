# 加密货币资金费率监控系统

一个专注于监控1小时资金费率结算合约的系统，支持备选合约管理和入池出池监控。

## 功能特性

### 📊 资金费率监控
- **1小时结算监控**：实时监控加密货币永续合约的1小时资金费率
- **多交易所支持**：支持Binance、OKX、Bybit等主流交易所
- **费率阈值告警**：当资金费率超过设定阈值时触发通知

### 🔄 合约池管理
- **备选合约管理**：维护备选合约列表
- **入池出池监控**：监控合约根据资金费率变化进出池子的状态
- **成交量过滤**：基于24小时成交量设置过滤条件

### 📬 实时通知
- **Telegram推送**：通过Telegram实时推送合约进出池子通知
- **日志记录**：详细记录监控活动和状态变化

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
│   └── funding_rate_arbitrage.py # 资金费率监控策略
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
- `DATA_SOURCE`: 数据源（ccxt）
- `TELEGRAM_TOKEN`: Telegram机器人token（用于通知）
- `TELEGRAM_CHAT_ID`: Telegram聊天ID
- `EXCHANGES`: 要监控的交易所列表

### 4. 启动系统

#### 方法一：启动Web界面
```bash
python start_web.py
# 或者双击 start_web.bat
```

#### 方法二：直接运行主程序
```bash
python main.py
```

**访问地址**：
- Web界面：http://localhost:8050

## 使用指南

### 1. 资金费率监控策略

**配置示例**：
```json
{
    "funding_rate_threshold": 0.005,    // 资金费率阈值 (0.5%)
    "contract_refresh_interval": 60,    // 合约池刷新间隔(分钟)
    "funding_rate_check_interval": 60,  // 资金费率检测间隔(秒)
    "max_pool_size": 20,                // 最大池子大小
    "min_volume": 1000000,              // 最小24小时成交量
    "exchanges": ["binance", "okx", "bybit"]  // 支持的交易所
}
```

**策略说明**：
- 自动监控多个交易所的永续合约资金费率
- 当资金费率绝对值 ≥ 0.5% 时，将合约加入待选池
- 当资金费率绝对值 < 0.5% 时，将合约移出待选池
- 通过Telegram实时推送合约进出池子的通知
- 支持设置最大池子大小和最小成交量过滤
- 每小时自动刷新合约池

**使用示例**：
```python
from strategies.factory import StrategyFactory

# 创建资金费率监控策略
strategy = StrategyFactory.create_strategy("funding_rate_arbitrage", {
    "funding_rate_threshold": 0.005,  # 0.5%
    "contract_refresh_interval": 60,  # 60分钟
    "funding_rate_check_interval": 60,  # 60秒
    "max_pool_size": 20,
    "min_volume": 1000000,
    "exchanges": ["binance", "okx", "bybit"]
})

# 启动监控
strategy.start_monitoring()

# 查看池子状态
pool_status = strategy.get_pool_status()
print(f"当前池子有 {pool_status['pool_size']} 个合约")
```

### 2. Web界面

访问 `http://localhost:8050` 使用Web界面：

- **监控面板**：查看当前监控的合约和资金费率
- **池子状态**：查看当前在池合约和历史变动
- **配置管理**：修改监控参数和通知设置
- **日志查看**：查看系统运行日志

## 配置说明

### 监控参数

```json
{
    "funding_rate_threshold": 0.005,    // 资金费率阈值 (0.5%)
    "contract_refresh_interval": 60,    // 合约池刷新间隔(分钟)
    "funding_rate_check_interval": 60,  // 资金费率检测间隔(秒)
    "max_pool_size": 20,                // 最大池子大小
    "min_volume": 1000000,              // 最小24小时成交量
    "exchanges": ["binance", "okx", "bybit"]  // 支持的交易所
}
```

### 通知配置

- `TELEGRAM_ENABLED`: 是否启用Telegram通知
- `TELEGRAM_TOKEN`: Telegram机器人token
- `TELEGRAM_CHAT_ID`: Telegram聊天ID
- `LOG_LEVEL`: 日志级别（DEBUG/INFO/WARNING/ERROR）

## 开发指南

### 添加新功能

1. 在相应模块中实现新功能
2. 更新配置文件和环境变量
3. 编写测试用例
4. 更新文档