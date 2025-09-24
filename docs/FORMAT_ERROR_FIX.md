# 字符串格式化错误修复说明

## 问题描述

Web界面在获取合约历史详情时出现字符串格式化错误：

```
获取合约 NMRUSDT 历史详情失败: Unknown format code 'f' for object of type 'str'
```

## 问题原因

**数据类型不匹配**：历史数据中的数值字段可能包含字符串而不是数字类型
- `funding_rate` 字段可能为字符串 `"0.001"` 而不是数字 `0.001`
- `mark_price` 字段可能为字符串 `"100.5"` 而不是数字 `100.5`
- `index_price` 字段可能为字符串 `"100.2"` 而不是数字 `100.2`

当代码尝试使用f-string格式化时：
```python
f"{funding_rate*100:.4f}%"  # 如果funding_rate是字符串，会出错
f"${mark_price:.4f}"        # 如果mark_price是字符串，会出错
```

## 解决方案

添加了完整的数据类型检查和转换机制

### 修复的位置

1. **统计信息构建**（第1330-1364行）
2. **图表数据构建**（第1399-1424行）
3. **表格数据构建**（第1480-1523行）

### 修复内容

1. **类型检查**：
   ```python
   if isinstance(funding_rate, str):
       funding_rate = float(funding_rate) if funding_rate else 0.0
   else:
       funding_rate = float(funding_rate) if funding_rate is not None else 0.0
   ```

2. **异常处理**：
   ```python
   try:
       # 数据类型转换
       funding_rate = float(funding_rate) if funding_rate else 0.0
   except (ValueError, TypeError) as e:
       print(f"⚠️ 处理历史记录时数据类型转换失败: {e}")
       funding_rate = 0.0  # 使用默认值
   ```

3. **安全格式化**：
   - 确保所有数值都是数字类型后再进行f-string格式化
   - 提供默认值处理异常情况

## 修改的文件

- ✅ `web/interface.py` - 修复了历史合约详情页面的数据类型转换问题

## 验证方法

运行测试脚本：
```bash
python test_format_fix.py
```

## 技术说明

- **支持的数据类型**：数字、字符串、None、空字符串
- **转换逻辑**：字符串 → float，None/空 → 0.0
- **异常处理**：转换失败时使用默认值 0.0
- **错误日志**：记录转换失败的情况用于调试

## 预期效果

- ✅ 不再显示 "Unknown format code 'f'" 错误
- ✅ 支持各种数据类型的资金费率和价格数据
- ✅ 历史详情页面能够正常显示统计信息、图表和表格
- ✅ 即使数据格式异常，页面也能正常显示（使用默认值）

## 处理的数据类型

| 输入类型 | 处理方式 | 输出 |
|---------|---------|------|
| `float(0.001)` | 直接使用 | `0.001` |
| `str("0.001")` | 转换为float | `0.001` |
| `None` | 使用默认值 | `0.0` |
| `str("")` | 使用默认值 | `0.0` |
| `str("invalid")` | 异常处理，使用默认值 | `0.0` |

## 使用场景

1. **历史详情页面**：显示合约的资金费率统计、图表和详细数据表格
2. **数据兼容性**：支持不同格式的历史数据文件
3. **错误恢复**：即使部分数据格式异常，页面仍能正常显示
