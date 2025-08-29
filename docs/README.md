# 加密货币资金费率监控系统

一个专注于监控多结算周期资金费率结算合约的系统，支持备选合约管理和入池出池监控。

## 功能特性

### 📊 资金费率监控
- **多结算周期监控**：支持1h、2h、4h、8h等不同结算周期的合约监控
- **智能缓存系统**：使用统一缓存文件，按结算周期分组存储，避免重复扫描
- **多交易所支持**：支持Binance、OKX、Bybit等主流交易所
- **费率阈值告警**：当资金费率超过设定阈值时触发通知

### 🔄 合约池管理
- **多结算周期合约管理**：支持不同结算周期的备选合约管理
- **智能缓存更新**：自动更新各结算周期的合约缓存，支持增量更新
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
│   ├── settings.py        # 系统配置
│   └── proxy_settings.py  # 代理设置
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
│   ├── binance_funding.py # Binance资金费率工具
│   └── notifier.py       # 通知工具
├── cache/                # 缓存目录
├── logs/                 # 日志目录
├── docs/                 # 文档目录
├── main.py               # 主程序
├── start.py              # 统一启动脚本
├── requirements.txt      # 依赖包
# 环境变量示例已移除，配置直接在config/settings.py中
└── README.md            # 项目说明
```

## 安装部署

### 1. 环境要求
- Python 3.8+
- 网络连接（用于获取市场数据）

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置系统
系统配置直接在 `config/settings.py` 文件中修改，主要配置项：
- `FUNDING_RATE_THRESHOLD`: 资金费率阈值（默认0.3%）
- `TELEGRAM_BOT_TOKEN`: Telegram机器人token（用于通知）
- `TELEGRAM_CHAT_ID`: Telegram聊天ID
- `SMTP_*`: 邮件通知配置

### 4. 启动系统

#### 使用统一启动脚本（推荐）
```bash
# 交互式菜单
python start.py

# 命令行模式
python start.py web      # 启动Web界面
python start.py api      # 启动API服务
python start.py main     # 启动主程序
python start.py all      # 启动所有服务
```

#### 直接启动
```bash
# 启动主程序（监控系统）
python main.py

# 启动Web界面
python start.py web

# 启动API服务
python start.py api
```

**访问地址**：
- Web界面：http://localhost:8050
- API服务：http://localhost:8000

## 使用指南

### 1. 资金费率监控策略

**配置说明**：
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

### 代码结构说明

- **策略模块**：所有交易策略都在 `strategies/` 目录下
- **工具模块**：通用工具函数在 `utils/` 目录下
- **配置管理**：系统配置在 `config/` 目录下