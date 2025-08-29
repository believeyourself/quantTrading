# 🚀 服务管理脚本使用说明

## 📋 概述

这些脚本让你能够将加密货币资金费率监控系统作为后台服务运行，即使断开SSH连接也能继续运行。

## 🔧 可用的脚本

| 脚本名称 | 功能 | 使用场景 |
|---------|------|----------|
| `start_service.sh` | 启动服务 | 首次启动、重启后启动 |
| `stop_service.sh` | 停止服务 | 需要停止服务时 |
| `restart_service.sh` | 重启服务 | 更新代码后重启 |
| `status_service.sh` | 查看状态 | 检查服务运行状态 |

## 🚀 快速开始

### 1. 给脚本添加执行权限

```bash
chmod +x start_service.sh stop_service.sh restart_service.sh status_service.sh
```

### 2. 启动服务

```bash
./start_service.sh
```

这个脚本会：
- 在后台启动服务
- 创建日志文件
- 保存进程ID
- 显示服务状态

### 3. 查看服务状态

```bash
./status_service.sh
```

这个脚本会显示：
- 服务运行状态
- 进程信息
- 端口监听状态
- 网络连接测试
- 系统资源使用情况

### 4. 停止服务

```bash
./stop_service.sh
```

这个脚本会：
- 优雅停止服务
- 清理进程
- 清理PID文件

### 5. 重启服务

```bash
./restart_service.sh
```

这个脚本会：
- 先停止现有服务
- 等待完全停止
- 启动新服务
- 验证服务状态

## 📊 服务状态说明

### 服务运行中
```bash
✅ 服务正在运行
✅ 端口8000正在监听
✅ 绑定到0.0.0.0 (外部可访问)
✅ 端口8050正在监听
✅ 绑定到0.0.0.0 (外部可访问)
```

### 服务未运行
```bash
❌ 服务未运行
启动服务请运行: ./start_service.sh
```

## 📁 文件结构

启动服务后，会创建以下文件：

```
logs/
├── service_20250830_003334.log  # 服务日志文件
├── service.pid                   # 进程ID文件
└── quant_trading.log            # 应用日志文件

cache/                           # 缓存目录
```

## 🔍 日志管理

### 查看实时日志

```bash
# 查看最新的服务日志
tail -f logs/service_*.log

# 查看应用日志
tail -f logs/quant_trading.log
```

### 日志轮转

日志文件会按时间戳命名，避免单个文件过大：
- `service_20250830_003334.log` - 2025年8月30日 00:33:34启动的日志

## 🛠️ 故障排除

### 1. 服务启动失败

**检查依赖**:
```bash
python3 -c "import fastapi, uvicorn, dash, plotly, requests, flask, flask_cors"
```

**检查端口占用**:
```bash
netstat -tlnp | grep -E ":8000|:8050"
```

**查看启动日志**:
```bash
tail -f logs/service_*.log
```

### 2. 服务无法访问

**检查服务状态**:
```bash
./status_service.sh
```

**检查防火墙**:
```bash
# CentOS/RHEL
firewall-cmd --list-ports

# Ubuntu/Debian
ufw status
```

**检查云服务器安全组设置**

### 3. 服务无法停止

**强制停止**:
```bash
pkill -f 'python.*start.py'
pkill -9 -f 'python.*start.py'
```

**检查进程**:
```bash
ps aux | grep 'python.*start.py'
```

## 📋 常用命令组合

### 完整的服务管理流程

```bash
# 1. 启动服务
./start_service.sh

# 2. 查看状态
./status_service.sh

# 3. 查看实时日志
tail -f logs/service_*.log

# 4. 重启服务（如果需要）
./restart_service.sh

# 5. 停止服务
./stop_service.sh
```

### 快速重启

```bash
./restart_service.sh
```

### 查看所有信息

```bash
./status_service.sh
```

## ⚠️ 注意事项

1. **目录要求**: 必须在项目根目录运行脚本
2. **权限要求**: 脚本需要执行权限
3. **Python环境**: 确保Python 3.13环境已激活
4. **依赖完整**: 确保所有依赖包已安装
5. **端口冲突**: 确保端口8000和8050未被占用

## 🔒 安全建议

1. **防火墙配置**: 只开放必要的端口
2. **访问控制**: 考虑添加身份验证
3. **日志监控**: 定期检查日志文件
4. **进程监控**: 使用系统监控工具

## 📞 技术支持

如果遇到问题：

1. **查看服务状态**: `./status_service.sh`
2. **查看启动日志**: `tail -f logs/service_*.log`
3. **检查系统日志**: `tail -f /var/log/messages`
4. **检查网络配置**: `netstat -tlnp | grep -E ":8000|:8050"`

## 🎯 成功标志

当你看到以下信息时，说明服务管理脚本工作正常：

```bash
✅ 服务启动成功!
进程ID: 12345
日志文件: logs/service_20250830_003334.log

✅ 服务已在后台启动，可以安全断开SSH连接
```

---

**建议使用顺序**: 启动 → 查看状态 → 监控日志 → 需要时重启/停止
