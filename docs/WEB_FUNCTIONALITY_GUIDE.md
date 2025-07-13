# Web功能使用指南

## 概述

本指南介绍量化交易系统的Web功能，包括策略管理、回测、交易和市场数据功能，以及新集成的资金费率套利功能。

## 系统架构

```
量化交易系统
├── API服务 (端口8000) - FastAPI后端
│   ├── 策略管理
│   ├── 回测功能
│   ├── 交易功能
│   ├── 市场数据
│   └── 资金费率套利
└── Web界面 (端口8050) - Dash前端
```

## 快速启动

### 方法一：一键启动（推荐）

```bash
# 启动所有服务
python start_all_services.py

# 或者使用批处理文件（Windows）
start_all_services.bat
```

### 方法二：分别启动

```bash
# 1. 启动API服务（必需）
python start_api.py

# 2. 启动资金费率API服务（可选）
python api/funding_arbitrage_api.py

# 3. 启动Web界面（可选）
python start_web.py
```

### 访问地址

- **主Web界面**: http://localhost:8050
- **API服务**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **资金费率API**: http://localhost:5000
- **资金费率管理界面**: http://localhost:5000/web/funding_arbitrage_ui.html

## 功能模块

### 1. 策略管理

#### 功能说明
- 创建、编辑、删除交易策略
- 支持多种策略类型：移动平均线交叉、布林带、MACD、RSI、资金费率套利
- 策略参数配置和状态管理

#### 使用方法
1. 访问Web界面，选择"策略管理"标签
2. 点击"刷新策略列表"加载现有策略
3. 在右侧表单中创建新策略：
   - 输入策略名称和描述
   - 选择策略类型
   - 配置策略参数（JSON格式）
   - 点击"创建策略"

#### 策略参数示例

**移动平均线交叉策略**:
```json
{
    "short_window": 10,
    "long_window": 30
}
```

**布林带策略**:
```json
{
    "window": 20,
    "num_std": 2
}
```

**资金费率套利策略**:
```json
{
    "funding_rate_threshold": 0.005,
    "max_positions": 10,
    "min_volume": 1000000,
    "exchanges": ["binance", "okx", "bybit"]
}
```

### 2. 资金费率套利

#### 功能说明
- 自动化资金费率套利交易
- 实时监控多个交易所的永续合约资金费率
- 自动开仓和平仓
- 风险控制和持仓管理
- Telegram通知

#### 使用方法
1. 选择"资金费率套利"标签
2. 使用控制按钮：
   - **启动策略**: 开始自动交易
   - **停止策略**: 停止自动交易
   - **平掉所有持仓**: 紧急平仓
   - **更新缓存**: 刷新合约数据

#### 状态监控
- **策略状态**: 显示当前运行状态
- **当前持仓**: 显示所有持仓信息
- **统计信息**: 显示交易统计和盈亏情况

### 3. 回测系统

#### 功能说明
- 基于历史数据的策略回测
- 性能指标计算：总收益率、最大回撤、夏普比率、胜率
- 权益曲线可视化

#### 使用方法
1. 选择"回测"标签
2. 配置回测参数：
   - 选择策略
   - 选择交易对
   - 设置时间周期
   - 设置回测时间范围
   - 设置初始资金
3. 点击"开始回测"
4. 查看回测结果和图表

#### 回测结果解读
- **总收益率**: 策略在回测期间的总收益百分比
- **最大回撤**: 策略的最大亏损幅度
- **夏普比率**: 风险调整后的收益指标
- **胜率**: 盈利交易占总交易的比例
- **总交易次数**: 回测期间的总交易数量

### 4. 交易管理

#### 功能说明
- 创建和管理交易引擎
- 模拟交易和实盘交易
- 实时监控持仓和账户状态
- 交易历史记录

#### 使用方法
1. 选择"交易"标签
2. 创建交易引擎：
   - 输入引擎名称
   - 选择交易类型（模拟/实盘）
   - 选择策略和交易对
   - 设置时间周期
3. 点击"创建引擎"
4. 查看交易状态、持仓信息和交易历史

#### 交易类型
- **模拟交易**: 使用虚拟资金，无风险测试
- **实盘交易**: 使用真实资金，需要配置API密钥

### 5. 市场数据

#### 功能说明
- 获取实时市场价格
- 更新历史市场数据
- 数据可视化

#### 使用方法
1. 选择"市场数据"标签
2. 选择交易对和时间周期
3. 使用功能按钮：
   - **更新数据**: 获取最新市场数据
   - **获取最新价格**: 显示当前价格

## 测试和验证

### 运行功能测试

```bash
# 测试所有Web功能
python test_web_functionality.py
```

测试脚本会检查：
- API服务健康状态
- 策略管理功能
- 回测功能
- 交易功能
- 市场数据功能
- 资金费率套利功能

### 常见问题排查

#### 1. API服务无法访问
```bash
# 检查API服务状态
curl http://localhost:8000/health

# 重启API服务
python start_api.py
```

#### 2. Web界面无法加载数据
- 确保API服务已启动
- 检查浏览器控制台错误信息
- 验证网络连接

#### 3. 回测功能异常
- 检查策略参数格式
- 验证交易对名称
- 确认时间范围设置

#### 4. 资金费率套利无法启动
- 检查Telegram配置
- 验证API密钥设置
- 确认缓存文件存在

## 配置说明

### 环境变量配置

复制 `env_example.txt` 为 `.env` 并修改配置：

```bash
# 数据源配置
DATA_SOURCE=yfinance

# 交易配置
DEFAULT_CAPITAL=10000
MAX_POSITION_SIZE=0.1
STOP_LOSS_RATIO=0.05
TAKE_PROFIT_RATIO=0.1

# API配置
API_HOST=0.0.0.0
API_PORT=8000

# Telegram通知配置
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# 交易所API配置（实盘交易需要）
API_KEY=your_api_key
API_SECRET=your_api_secret
TESTNET=true
```

### 资金费率套利配置

编辑 `config/funding_monitor_config.json`:

```json
{
    "funding_rate_threshold": 0.005,
    "max_positions": 10,
    "min_volume": 1000000,
    "exchanges": ["binance", "okx", "bybit"],
    "update_interval": 3600,
    "telegram_notifications": true
}
```

## 安全注意事项

1. **API密钥安全**
   - 不要在代码中硬编码API密钥
   - 使用环境变量或配置文件
   - 定期更换API密钥

2. **实盘交易风险**
   - 充分测试模拟交易
   - 设置合理的止损止盈
   - 控制仓位大小

3. **网络安全**
   - 不要在生产环境中使用默认端口
   - 配置防火墙规则
   - 使用HTTPS协议

## 性能优化

1. **数据缓存**
   - 使用数据库缓存历史数据
   - 定期清理过期数据
   - 优化数据查询

2. **并发处理**
   - 使用异步处理提高性能
   - 合理设置线程池大小
   - 避免阻塞操作

3. **内存管理**
   - 及时释放不需要的数据
   - 使用生成器处理大量数据
   - 监控内存使用情况

## 故障排除

### 日志查看

```bash
# 查看系统日志
tail -f logs/quant_trading.log

# 查看错误日志
grep ERROR logs/quant_trading.log
```

### 数据库维护

```bash
# 初始化数据库
python init_database.py

# 清理过期数据
python -c "from utils.database import SessionLocal; db = SessionLocal(); db.execute('DELETE FROM market_data WHERE timestamp < date(\"now\", \"-30 days\")'); db.commit()"
```

### 服务重启

```bash
# 停止所有服务
pkill -f "python.*start_api.py"
pkill -f "python.*funding_arbitrage_api.py"
pkill -f "python.*start_web.py"

# 重新启动
python start_all_services.py
```

## 更新和维护

### 系统更新

```bash
# 更新代码
git pull origin main

# 更新依赖
pip install -r requirements.txt

# 重启服务
python start_all_services.py
```

### 数据备份

```bash
# 备份数据库
cp quant_trading.db quant_trading_backup.db

# 备份配置文件
cp -r config/ config_backup/
```

## 技术支持

如果遇到问题，请：

1. 查看日志文件获取错误信息
2. 运行测试脚本验证功能
3. 检查配置文件设置
4. 参考本文档的故障排除部分

## 更新日志

### v1.0.0
- 初始版本发布
- 基础策略管理功能
- 回测系统
- 交易管理
- 市场数据功能

### v1.1.0
- 集成资金费率套利功能
- 改进Web界面
- 添加功能测试
- 优化错误处理
- 完善文档 