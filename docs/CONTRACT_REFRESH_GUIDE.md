# 合约池定时刷新功能使用指南

## 概述

本功能允许策略在运行过程中自动定时刷新合约池配置，确保策略始终使用最新的1小时结算周期合约列表，而无需手动干预。

## 功能特性

### 1. 自动定时刷新
- 策略启动后会自动启动合约池定时刷新线程
- 刷新间隔可配置，默认24小时
- 刷新过程在后台进行，不影响策略正常运行

### 2. 智能更新机制
- 只更新配置文件中新增的合约
- 保留已有合约的资金费率等数据
- 自动移除配置文件中已删除的合约

### 3. 强制刷新功能
- 提供手动强制刷新接口
- 完全重新扫描和更新合约池
- 适用于紧急情况或配置异常时

## 配置参数

### 策略参数
```python
strategy_params = {
    'funding_rate_threshold': 0.005,      # 资金费率阈值
    'max_positions': 5,                   # 最大持仓数量
    'min_volume': 1000000,                # 最小成交量
    'exchanges': ['binance'],             # 交易所列表
    'cache_duration': 7200,               # 资金费率缓存时间（秒）
    'update_interval': 3600,              # 资金费率更新间隔（秒）
    'funding_interval': 3600,             # 资金费率结算周期（秒）
    'contract_refresh_interval': 86400    # 合约池刷新间隔（秒）- 可配置
}
```

### 时间间隔说明
- **cache_duration**: 资金费率缓存有效期，超过此时间会重新获取
- **update_interval**: 资金费率定时更新间隔
- **contract_refresh_interval**: 合约池配置刷新间隔

### 推荐配置
```python
# 生产环境配置
'contract_refresh_interval': 86400    # 24小时刷新一次

# 测试环境配置
'contract_refresh_interval': 3600     # 1小时刷新一次

# 开发调试配置
'contract_refresh_interval': 300      # 5分钟刷新一次
```

## 使用方法

### 1. 基本使用
```python
from strategies.factory import StrategyFactory

# 创建策略实例
strategy_params = {
    'contract_refresh_interval': 86400,  # 24小时刷新一次
    # ... 其他参数
}
strategy = StrategyFactory.create_strategy("funding_rate_arbitrage", strategy_params)

# 策略会自动启动定时刷新线程
print("✅ 合约池定时刷新线程已启动")
```

### 2. 手动强制刷新
```python
# 强制刷新合约池配置
success = strategy.force_refresh_contract_pool()
if success:
    print("✅ 强制刷新成功")
else:
    print("❌ 强制刷新失败")
```

### 3. 监控刷新状态
```python
# 获取策略状态
pool_status = strategy.get_pool_status()
print(f"缓存合约数量: {pool_status['cached_contracts_count']}")
print(f"缓存是否有效: {pool_status['cache_valid']}")
print(f"最后更新时间: {pool_status['last_update_time']}")
```

## 工作流程

### 1. 策略启动流程
```
1. 初始化合约配置管理器
2. 加载现有合约配置
3. 启动定时更新线程（资金费率）
4. 启动合约池定时刷新线程
5. 策略开始正常运行
```

### 2. 定时刷新流程
```
1. 检查是否到达刷新时间
2. 重新加载合约配置文件
3. 对比新旧合约列表
4. 保留已有合约的数据
5. 获取新增合约的资金费率
6. 移除已删除的合约
7. 更新缓存和保存
8. 发送通知（如有变化）
```

### 3. 强制刷新流程
```
1. 调用合约管理器更新配置
2. 重新扫描1小时结算合约
3. 清空现有缓存
4. 重新获取所有合约资金费率
5. 更新缓存和保存
6. 发送通知
```

## 监控和通知

### 1. 自动通知
- 合约数量变化时发送Telegram通知
- 刷新失败时发送错误通知
- 强制刷新完成时发送成功通知

### 2. 日志输出
```
🔄 开始定时刷新合约池配置...
✅ 新增合约 BTC/USDT 资金费率: 0.0123%
✅ 合约池配置刷新完成，耗时: 2.34秒
  原合约数量: 18
  新合约数量: 20
  变化: +2
```

### 3. 状态监控
```python
# 定期检查策略状态
def monitor_strategy(strategy):
    while True:
        pool_status = strategy.get_pool_status()
        print(f"合约数量: {pool_status['cached_contracts_count']}")
        print(f"缓存有效: {pool_status['cache_valid']}")
        time.sleep(300)  # 每5分钟检查一次
```

## 故障排除

### 1. 刷新失败
**问题**: 合约池刷新失败
**解决**: 
- 检查网络连接和代理设置
- 检查交易所API是否正常
- 查看错误日志获取详细信息

### 2. 刷新间隔异常
**问题**: 刷新间隔不按预期执行
**解决**:
- 检查 `contract_refresh_interval` 参数设置
- 确认时间单位为秒
- 检查系统时间是否正常

### 3. 合约数量异常
**问题**: 合约数量突然变化
**解决**:
- 检查合约配置文件是否被手动修改
- 查看刷新日志了解变化原因
- 确认交易所是否下架了某些合约

## 最佳实践

### 1. 生产环境配置
```python
# 推荐的生产环境配置
strategy_params = {
    'contract_refresh_interval': 86400,  # 24小时刷新一次
    'cache_duration': 7200,             # 2小时缓存
    'update_interval': 3600,            # 1小时更新资金费率
}
```

### 2. 测试环境配置
```python
# 推荐的测试环境配置
strategy_params = {
    'contract_refresh_interval': 3600,   # 1小时刷新一次
    'cache_duration': 1800,             # 30分钟缓存
    'update_interval': 900,             # 15分钟更新资金费率
}
```

### 3. 监控建议
- 定期检查策略日志
- 监控合约数量变化
- 设置Telegram通知
- 记录刷新历史

## 注意事项

1. **网络要求**: 刷新过程需要稳定的网络连接
2. **API限制**: 注意交易所API调用频率限制
3. **资源消耗**: 刷新过程会消耗一定的系统资源
4. **数据一致性**: 刷新过程中策略仍可正常运行，使用缓存数据
5. **错误处理**: 刷新失败不会影响策略正常运行

## 相关文件

- `strategies/funding_rate_arbitrage.py`: 策略实现
- `config/contract_manager.py`: 合约配置管理器
- `config/settings.py`: 系统配置文件
- `test_funding_with_refresh.py`: 测试脚本 