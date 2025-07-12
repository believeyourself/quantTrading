# 量化交易系统文档

## 项目结构

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
├── start_web.py          # Web启动脚本
├── requirements.txt      # 依赖包
├── env_example.txt       # 环境变量示例
└── README.md            # 项目说明
```

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

## 使用指南

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境
```bash
cp env_example.txt .env
# 编辑.env文件
```

### 3. 运行测试
```bash
python -m tests.system_test
```

### 4. 启动系统
```bash
# 启动API服务
python main.py

# 启动Web界面
python start_web.py
```

## 开发指南

### 添加新策略
1. 在`strategies/`目录下创建新策略文件
2. 继承`BaseStrategy`类
3. 实现`generate_signals`方法
4. 在`factory.py`中注册新策略

### 扩展数据源
1. 在`data/manager.py`中添加新数据源
2. 实现数据获取和格式转换
3. 更新配置选项

### 添加新API接口
1. 在`api/routes.py`中添加新路由
2. 定义请求和响应模型
3. 实现业务逻辑

## 部署说明

### 生产环境部署
1. 使用生产级数据库（PostgreSQL/MySQL）
2. 配置反向代理（Nginx）
3. 使用进程管理器（PM2/Supervisor）
4. 配置SSL证书
5. 设置防火墙规则

### 监控和日志
1. 配置日志轮转
2. 设置监控告警
3. 定期备份数据
4. 性能监控

## 故障排除

### 常见问题
1. 数据获取失败：检查网络连接和数据源配置
2. 回测异常：验证策略参数和历史数据
3. 交易失败：检查API密钥和账户余额

### 日志查看
```bash
tail -f logs/quant_trading.log
```

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 发起Pull Request

## 许可证

MIT License 