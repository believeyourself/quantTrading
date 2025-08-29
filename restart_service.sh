#!/bin/bash

# 加密货币资金费率监控系统 - 服务重启脚本
# 安全重启服务，先停止再启动

echo "🔄 重启加密货币资金费率监控系统服务"
echo "=================================================="

# 检查项目目录
if [ ! -f "start.py" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

echo "📋 重启流程:"
echo "1. 停止现有服务"
echo "2. 等待服务完全停止"
echo "3. 启动新服务"
echo "4. 验证服务状态"
echo ""

# 第一步：停止服务
echo "🛑 第一步：停止现有服务..."
echo "=================================================="

if [ -f "./stop_service.sh" ]; then
    ./stop_service.sh
else
    echo "❌ 停止脚本不存在，请确保在项目根目录运行"
    exit 1
fi

echo ""
echo "⏳ 等待服务完全停止..."
sleep 5

# 检查服务是否完全停止
check_service() {
    if pgrep -f "python.*start.py" > /dev/null; then
        return 0
    else
        return 1
    fi
}

if check_service; then
    echo "⚠️  服务仍在运行，尝试强制停止..."
    
    # 强制停止所有相关进程
    pids=$(pgrep -f "python.*start.py")
    if [ ! -z "$pids" ]; then
        echo "强制终止进程: $pids"
        for pid in $pids; do
            kill -KILL "$pid" 2>/dev/null
        done
        sleep 2
    fi
    
    # 最终检查
    if check_service; then
        echo "❌ 无法停止服务，请手动检查"
        echo "手动停止命令:"
        echo "pkill -f 'python.*start.py'"
        echo "pkill -9 -f 'python.*start.py'"
        exit 1
    else
        echo "✅ 服务已完全停止"
    fi
else
    echo "✅ 服务已完全停止"
fi

echo ""
echo "🚀 第二步：启动新服务..."
echo "=================================================="

if [ -f "./start_service.sh" ]; then
    ./start_service.sh
else
    echo "❌ 启动脚本不存在，请确保在项目根目录运行"
    exit 1
fi

echo ""
echo "🔍 第三步：验证服务状态..."
echo "=================================================="

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 检查服务状态
if [ -f "./status_service.sh" ]; then
    ./status_service.sh
else
    echo "⚠️  状态检查脚本不存在，手动检查服务状态"
    echo "检查命令:"
    echo "ps aux | grep 'python.*start.py'"
    echo "netstat -tlnp | grep -E ':8000|:8050'"
fi

echo ""
echo "✅ 服务重启完成!"
echo "=================================================="
echo ""
echo "📋 服务管理命令:"
echo "启动服务: ./start_service.sh"
echo "停止服务: ./stop_service.sh"
echo "重启服务: ./restart_service.sh"
echo "查看状态: ./status_service.sh"
echo "查看日志: tail -f logs/service_*.log"
