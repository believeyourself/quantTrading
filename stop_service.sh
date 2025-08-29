#!/bin/bash

# 加密货币资金费率监控系统 - 服务停止脚本
# 安全停止后台运行的服务

echo "🛑 停止加密货币资金费率监控系统服务"
echo "=================================================="

# 检查项目目录
if [ ! -f "start.py" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 检查服务是否运行
check_service() {
    if pgrep -f "python.*start.py" > /dev/null; then
        return 0
    else
        return 1
    fi
}

if ! check_service; then
    echo "⚠️  服务未在运行"
    exit 0
fi

# 获取PID文件
pid_file="logs/service.pid"

echo "📋 正在停止服务..."
echo "=================================================="

# 显示当前运行的进程
echo "当前运行的服务进程:"
ps aux | grep "python.*start.py" | grep -v grep

echo ""

# 尝试优雅停止
echo "🔧 尝试优雅停止服务..."

# 从PID文件读取进程ID
if [ -f "$pid_file" ]; then
    pid=$(cat "$pid_file")
    echo "从PID文件读取进程ID: $pid"
    
    # 检查进程是否存在
    if kill -0 "$pid" 2>/dev/null; then
        echo "发送SIGTERM信号到进程 $pid..."
        kill -TERM "$pid"
        
        # 等待进程优雅退出
        echo "等待进程优雅退出..."
        for i in {1..10}; do
            if ! kill -0 "$pid" 2>/dev/null; then
                echo "✅ 进程 $pid 已优雅退出"
                break
            fi
            sleep 1
            echo "等待中... ($i/10)"
        done
        
        # 如果进程仍然存在，强制终止
        if kill -0 "$pid" 2>/dev/null; then
            echo "⚠️  进程未响应SIGTERM，发送SIGKILL信号..."
            kill -KILL "$pid"
            sleep 1
        fi
    else
        echo "⚠️  PID文件中的进程ID $pid 不存在"
    fi
else
    echo "⚠️  PID文件不存在，使用进程名查找..."
fi

# 使用进程名查找并停止所有相关进程
echo "查找并停止所有相关进程..."
pids=$(pgrep -f "python.*start.py")

if [ ! -z "$pids" ]; then
    echo "找到进程: $pids"
    
    for pid in $pids; do
        echo "停止进程 $pid..."
        kill -TERM "$pid" 2>/dev/null
        
        # 等待进程退出
        sleep 2
        
        # 如果进程仍然存在，强制终止
        if kill -0 "$pid" 2>/dev/null; then
            echo "强制终止进程 $pid..."
            kill -KILL "$pid" 2>/dev/null
        fi
    done
else
    echo "未找到运行中的服务进程"
fi

# 最终检查
echo ""
echo "🔍 最终检查..."
if check_service; then
    echo "❌ 仍有服务进程在运行:"
    ps aux | grep "python.*start.py" | grep -v grep
    echo ""
    echo "如需强制停止，请手动运行:"
    echo "pkill -f 'python.*start.py'"
    echo "pkill -9 -f 'python.*start.py'"
else
    echo "✅ 所有服务进程已停止"
    
    # 清理PID文件
    if [ -f "$pid_file" ]; then
        rm -f "$pid_file"
        echo "已清理PID文件"
    fi
fi

echo ""
echo "✅ 服务停止完成!"
echo "=================================================="
