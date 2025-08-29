#!/bin/bash

# 加密货币资金费率监控系统 - 服务启动脚本
# 在后台启动服务，支持日志记录和进程管理

echo "🚀 启动加密货币资金费率监控系统服务"
echo "=================================================="

# 检查项目目录
if [ ! -f "start.py" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 创建必要的目录
mkdir -p logs
mkdir -p cache

# 检查服务是否已经运行
check_service() {
    if pgrep -f "python.*start.py" > /dev/null; then
        return 0
    else
        return 1
    fi
}

if check_service; then
    echo "⚠️  服务已经在运行中"
    echo "进程信息:"
    ps aux | grep "python.*start.py" | grep -v grep
    echo ""
    echo "如需重启服务，请先运行: ./stop_service.sh"
    exit 0
fi

# 生成时间戳
timestamp=$(date +"%Y%m%d_%H%M%S")
log_file="logs/service_${timestamp}.log"
pid_file="logs/service.pid"

echo "📋 服务信息:"
echo "项目目录: $(pwd)"
echo "日志文件: $log_file"
echo "PID文件: $pid_file"
echo ""

# 启动服务
echo "🔧 启动服务..."
echo "启动时间: $(date)"
echo "=================================================="

# 使用nohup在后台运行，并重定向输出到日志文件
nohup python3 start.py > "$log_file" 2>&1 &

# 获取进程ID
service_pid=$!

# 等待一下确保服务启动
sleep 3

# 检查服务是否成功启动
if check_service; then
    echo "✅ 服务启动成功!"
    echo "进程ID: $service_pid"
    echo "日志文件: $log_file"
    
    # 保存PID到文件
    echo $service_pid > "$pid_file"
    
    echo ""
    echo "📋 服务状态:"
    echo "=================================================="
    ps aux | grep "python.*start.py" | grep -v grep
    
    echo ""
    echo "🔍 查看实时日志:"
    echo "tail -f $log_file"
    
    echo ""
    echo "🛑 停止服务:"
    echo "./stop_service.sh"
    
    echo ""
    echo "📊 查看服务状态:"
    echo "./status_service.sh"
    
    echo ""
    echo "✅ 服务已在后台启动，可以安全断开SSH连接"
    echo "=================================================="
else
    echo "❌ 服务启动失败"
    echo "请检查日志文件: $log_file"
    echo "常见问题:"
    echo "1. 依赖包未安装"
    echo "2. 端口被占用"
    echo "3. 配置文件错误"
    exit 1
fi
