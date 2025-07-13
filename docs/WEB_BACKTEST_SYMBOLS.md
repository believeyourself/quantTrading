# Web端回测功能 - 交易对配置

## 概述

项目的web端回测功能现在支持从 `1h_funding_contracts_full.json` 配置文件自动读取可选的交易对列表。

## 配置文件位置

交易对配置文件位于：
```
cache/1h_funding_contracts_full.json
```

## 配置文件结构

配置文件包含以下结构：
```json
{
  "cache_time": "2025-07-13T17:57:29.661305",
  "contracts": {
    "RVNUSDT": {
      "symbol": "RVNUSDT",
      "contract_type": "UM",
      "current_funding_rate": "0.00001250",
      "funding_interval_hours": 1.0000002777777777,
      "next_funding_time": "2025-07-13T18:00:00",
      "history_rates": [...],
      "last_updated": "2025-07-13T17:49:07.557671"
    },
    "MASKUSDT": {
      // 类似结构
    }
    // ... 更多交易对
  }
}
```

## 功能实现

### 1. 数据管理器修改

在 `data/manager.py` 中的 `DataManager.get_symbols()` 方法已被修改：

```python
def get_symbols(self) -> List[str]:
    """获取支持的交易对列表"""
    try:
        # 优先从1h_funding_contracts_full.json配置文件读取交易对
        import json
        import os
        
        cache_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                "cache", "1h_funding_contracts_full.json")
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'contracts' in data:
                    # 提取所有交易对符号
                    symbols = list(data['contracts'].keys())
                    logger.info(f"从配置文件加载了 {len(symbols)} 个交易对")
                    return symbols
        
        # 如果配置文件不存在，则使用默认方法
        # ... 默认逻辑
        
    except Exception as e:
        logger.error(f"从配置文件读取交易对失败: {e}")
        # 返回默认交易对
        return ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]
```

### 2. API端点

交易对通过以下API端点提供给web界面：

```
GET /data/symbols
```

返回格式：
```json
[
  "RVNUSDT",
  "MASKUSDT", 
  "LPTUSDT",
  // ... 更多交易对
]
```

### 3. Web界面集成

在 `web/interface.py` 中，交易对选项通过以下回调函数自动加载：

```python
@app.callback(
    [Output("backtest-strategy", "options"),
     Output("trading-strategy", "options"),
     Output("backtest-symbol", "options"),
     Output("trading-symbol", "options"),
     Output("data-symbol", "options")],
    [Input("refresh-strategies", "n_clicks")]
)
def initialize_options(n_clicks):
    """初始化下拉选项"""
    try:
        # 获取交易对选项
        symbols_response = requests.get(f"{API_BASE_URL}/data/symbols")
        if symbols_response.status_code == 200:
            symbols = symbols_response.json()
            symbol_options = [
                {"label": symbol, "value": symbol} 
                for symbol in symbols
            ]
        else:
            symbol_options = []
        
        return strategy_options, strategy_options, symbol_options, symbol_options, symbol_options
        
    except Exception as e:
        return [], [], [], [], []
```

## 使用方法

### 1. 启动Web界面

```bash
python start_web.py
```

### 2. 访问回测功能

1. 打开浏览器访问 `http://localhost:8050`
2. 点击"回测"标签
3. 在"交易对"下拉菜单中选择要回测的交易对
4. 配置其他回测参数
5. 点击"开始回测"

### 3. 更新交易对列表

如果需要更新可用的交易对：

1. 更新 `cache/1h_funding_contracts_full.json` 文件
2. 在web界面点击"刷新策略列表"按钮
3. 交易对下拉菜单将自动更新

## 测试

运行测试脚本验证功能：

```bash
python test_symbols_loading.py
```

## 注意事项

1. **配置文件优先级**：系统优先从 `1h_funding_contracts_full.json` 读取交易对
2. **容错机制**：如果配置文件不存在或读取失败，会使用默认交易对列表
3. **实时更新**：修改配置文件后，需要刷新web界面才能看到新的交易对
4. **日志记录**：系统会记录从配置文件加载的交易对数量

## 当前支持的交易对

根据配置文件，当前支持以下20个交易对：

- RVNUSDT
- MASKUSDT  
- LPTUSDT
- AXLUSDT
- VOXELUSDT
- ALPACAUSDT
- LAYERUSDT
- VICUSDT
- BROCCOLIF3BUSDT
- FUNUSDT
- 等等...

这些交易对都是1小时资金费率合约，适合进行资金费率套利策略的回测。 