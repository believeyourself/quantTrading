# 1小时结算合约缓存更新系统使用指南

## 系统架构

### 1. 主流程（策略）
- **只读取缓存**：策略运行时只调用 `get_1h_contracts_from_cache()`
- **不主动刷新**：策略不会触发扫描和更新操作
- **异常检测**：自动检测缓存是否过期，过期时发送TG通知

### 2. 定时更新进程
- **独立运行**：`update_1h_contracts_cache.py` 作为独立进程运行
- **定时刷新**：每小时自动刷新一次缓存
- **异常通知**：更新失败时发送TG通知

## 使用方法

### 启动定时更新进程

#### 方法1：直接运行
```bash
python update_1h_contracts_cache.py
```

#### 方法2：Windows批处理
```bash
start_cache_updater.bat
```

#### 方法3：后台运行（Linux/Mac）
```bash
nohup python update_1h_contracts_cache.py > cache_updater.log 2>&1 &
```

### 策略中使用缓存

```python
from utils.binance_funding import BinanceFunding
from utils.notifier import send_telegram_message

# 初始化
funding = BinanceFunding()

# 获取1小时结算合约池（只读缓存）
contracts = funding.get_1h_contracts_from_cache(tg_notifier=send_telegram_message)

# 使用合约池
if contracts:
    for symbol, info in contracts.items():
        funding_rate = float(info.get('current_funding_rate', 0))
        # 你的策略逻辑...
```

## 功能特性

### 1. 缓存有效期检测
- **有效期**：1小时（3600秒）
- **过期检测**：每次读取缓存时自动检测
- **异常通知**：缓存过期时自动发送TG消息

### 2. 异常处理
- **缓存读取失败**：发送TG通知
- **定时更新失败**：发送TG通知
- **进程异常**：自动重试，发送TG通知

### 3. 优雅退出
- **信号处理**：支持 Ctrl+C 优雅退出
- **状态保存**：退出前保存当前状态

## 通知消息格式

### 成功通知
```
✅ 缓存更新成功！找到 20 个1小时结算合约
```

### 过期警告
```
⚠️ 1小时结算合约缓存已过期 2.5 小时，定时任务可能未正常更新！
```

### 错误通知
```
❌ 缓存更新失败: [具体错误信息]
```

## 测试验证

### 运行测试脚本
```bash
python test_cache_logic.py
```

### 测试项目
1. **缓存读取逻辑**：验证正常读取和过期检测
2. **策略集成**：验证在策略中的使用方式
3. **异常通知**：验证TG通知功能

## 监控建议

### 1. 进程监控
- 确保定时更新进程持续运行
- 监控进程日志输出
- 设置进程自动重启机制

### 2. 缓存监控
- 定期检查缓存文件大小和更新时间
- 监控TG通知频率
- 关注异常通知信息

### 3. 性能监控
- 监控缓存读取速度
- 关注API调用频率
- 观察内存使用情况

## 故障排除

### 常见问题

1. **缓存过期但未收到通知**
   - 检查TG配置是否正确
   - 确认网络连接正常
   - 查看日志输出

2. **定时更新进程停止**
   - 检查进程是否被意外终止
   - 查看错误日志
   - 重启进程

3. **缓存文件损坏**
   - 删除缓存文件，重新生成
   - 检查磁盘空间
   - 验证文件权限

### 日志位置
- **控制台输出**：直接显示在终端
- **后台日志**：`cache_updater.log`（如果使用nohup）

## 配置说明

### 更新间隔
在 `update_1h_contracts_cache.py` 中修改：
```python
self.update_interval = 3600  # 1小时，可调整为其他值
```

### 缓存有效期
在 `utils/binance_funding.py` 中修改：
```python
cache_duration = 3600  # 1小时，建议与更新间隔一致
```

### Telegram通知
确保 `utils/notifier.py` 中的TG配置正确：
- Bot Token
- Chat ID
- 网络代理设置（如需要） 