# 历史入池合约查询功能 - 实现总结

## 功能概述

针对cache/monitor_history下的所有历史数据，新增了一个专门的tab用于查询历史入池合约的列表，并可以查看他们在池期间的记录历史资金费率。

## 实现功能

### ✅ 已完成的功能

1. **API端点创建**
   - `/funding_monitor/history-contracts` - 获取历史入池合约列表
   - `/funding_monitor/history-contract/{symbol}` - 获取指定合约的历史详情

2. **Web界面新增Tab**
   - 添加了"历史入池合约"标签页
   - 包含历史数据统计显示
   - 历史合约列表表格
   - 历史详情弹窗

3. **历史合约列表展示**
   - 合约名称、创建时间、记录总数
   - 时间范围、资金费率统计、价格统计
   - 最后记录信息、操作按钮

4. **历史资金费率查看**
   - 统计信息卡片（资金费率统计、价格统计、记录统计）
   - 历史数据图表（资金费率和价格趋势图）
   - 详细数据表格（所有历史记录）

5. **历史数据统计和筛选**
   - 自动计算最高/最低/平均资金费率
   - 自动计算最高/最低/平均价格
   - 按创建时间排序（最新的在前）

## 技术实现

### API实现 (`api/routes.py`)

#### 历史合约列表API
```python
@app.get("/funding_monitor/history-contracts")
def get_history_contracts():
    """获取历史入池合约列表"""
    # 扫描cache/monitor_history目录
    # 读取所有_history.json文件
    # 计算统计信息（最高/最低/平均资金费率和价格）
    # 按创建时间排序返回
```

#### 历史合约详情API
```python
@app.get("/funding_monitor/history-contract/{symbol}")
def get_history_contract_detail(symbol: str):
    """获取指定合约的历史资金费率详情"""
    # 读取指定合约的历史文件
    # 格式化历史记录
    # 返回完整的历史数据
```

### Web界面实现 (`web/interface.py`)

#### 新增Tab结构
```python
dbc.Tab([
    dbc.Row([
        dbc.Col([
            html.H3("历史入池合约"),
            html.P("查看所有历史入池合约的列表和在池期间的记录历史资金费率。"),
            # 刷新按钮和统计信息
            # 历史合约列表表格
            # 历史详情弹窗
        ])
    ])
], label="历史入池合约", tab_id="history-contracts")
```

#### 回调函数
- `load_history_contracts()` - 加载历史合约列表
- `open_history_contract_modal()` - 打开历史详情弹窗

## 数据结构

### 历史文件格式
```json
{
  "symbol": "BTCUSDT",
  "created_time": "2025-08-31T23:30:05.400284",
  "history": [
    {
      "timestamp": "2025-08-31T23:30:05.400306",
      "funding_rate": 0.001,
      "mark_price": 50000,
      "index_price": 50001,
      "last_updated": "2025-08-31T23:30:05.400306",
      "data_source": "real_time"
    }
  ]
}
```

### API返回格式
```json
{
  "status": "success",
  "contracts": [
    {
      "symbol": "BTCUSDT",
      "created_time": "2025-08-31T23:30:05.400284",
      "total_records": 65,
      "start_time": "2025-08-31T23:30:05",
      "end_time": "2025-09-05T22:30:05",
      "max_funding_rate": 0.002,
      "min_funding_rate": 0.0005,
      "avg_funding_rate": 0.0012,
      "max_price": 52000,
      "min_price": 48000,
      "avg_price": 50000,
      "last_funding_rate": 0.001,
      "last_mark_price": 50000,
      "last_updated": "2025-09-05T22:30:05"
    }
  ],
  "count": 22,
  "timestamp": "2025-09-05T22:32:45"
}
```

## 功能特性

### 1. 历史合约列表
- **合约信息**: 名称、创建时间、记录总数
- **时间范围**: 开始时间到结束时间
- **资金费率统计**: 最高、最低、平均资金费率
- **价格统计**: 最高、最低、平均价格
- **最后记录**: 最新的资金费率和价格
- **操作按钮**: 查看详情

### 2. 历史详情弹窗
- **统计卡片**: 资金费率统计、价格统计、记录统计
- **趋势图表**: 资金费率趋势图、价格趋势图
- **详细表格**: 所有历史记录的详细信息

### 3. 数据统计
- **自动计算**: 最高/最低/平均资金费率和价格
- **时间排序**: 按创建时间排序（最新的在前）
- **实时更新**: 支持刷新历史数据

## 测试验证

### 测试结果
- ✅ 历史目录存在: cache/monitor_history
- ✅ 历史文件统计: 22个文件
- ✅ 文件格式正确: JSON格式，包含完整历史记录
- ✅ 数据丰富: 包含多个合约的历史数据

### 测试脚本
运行 `python test_history_contracts.py` 可以验证：
1. API端点是否正常工作
2. 历史文件是否存在和格式正确
3. Web界面功能是否完整

## 使用说明

### 启动系统
```bash
# 启动所有服务
python start.py all

# 或分别启动
python start.py api    # API服务
python start.py web    # Web界面
```

### 查看历史数据
1. 访问 http://localhost:8050
2. 切换到"历史入池合约"标签页
3. 查看历史合约列表
4. 点击"查看详情"查看具体合约的历史数据

### API调用
```bash
# 获取历史合约列表
curl http://localhost:8000/funding_monitor/history-contracts

# 获取指定合约的历史详情
curl http://localhost:8000/funding_monitor/history-contract/BTCUSDT
```

## 优势特性

1. **数据完整性**: 自动扫描所有历史文件，确保数据完整
2. **统计丰富**: 提供详细的统计信息，便于分析
3. **可视化**: 图表展示趋势，直观易懂
4. **响应式设计**: 支持移动端访问
5. **实时更新**: 支持刷新数据，保持最新状态

## 总结

成功实现了历史入池合约查询功能，包括：
- 完整的API端点支持
- 直观的Web界面展示
- 丰富的数据统计和可视化
- 详细的历史记录查看

该功能为用户提供了完整的历史数据分析能力，可以查看所有历史入池合约的详细信息和在池期间的记录历史资金费率，大大增强了系统的数据分析能力。
