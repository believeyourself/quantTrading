#!/bin/bash

# 加密货币资金费率监控系统 - 服务状态查看脚本
# 查看服务的运行状态、进程信息、端口监听等

echo "📊 加密货币资金费率监控系统服务状态"
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

echo "🔍 服务运行状态检查..."
echo "=================================================="

if check_service; then
    echo "✅ 服务正在运行"
else
    echo "❌ 服务未运行"
    echo ""
    echo "启动服务请运行: ./start_service.sh"
    exit 0
fi

echo ""
echo "📋 进程信息..."
echo "=================================================="

# 显示进程详细信息
echo "Python进程:"
ps aux | grep "python.*start.py" | grep -v grep | while read -r line; do
    echo "  $line"
done

echo ""
echo "📋 端口监听状态..."
echo "=================================================="

# 检查端口监听状态
echo "端口8000 (API服务):"
if netstat -tlnp | grep :8000; then
    echo "✅ 端口8000正在监听"
    # 检查绑定地址
    binding=$(netstat -tlnp | grep :8000 | awk '{print $4}')
    if echo "$binding" | grep -q "0.0.0.0"; then
        echo "  ✅ 绑定到0.0.0.0 (外部可访问)"
    else
        echo "  ❌ 绑定到127.0.0.1 (仅本地访问)"
    fi
else
    echo "❌ 端口8000未监听"
fi

echo ""
echo "端口8050 (Web界面):"
if netstat -tlnp | grep :8050; then
    echo "✅ 端口8050正在监听"
    # 检查绑定地址
    binding=$(netstat -tlnp | grep :8050 | awk '{print $4}')
    if echo "$binding" | grep -q "0.0.0.0"; then
        echo "  ✅ 绑定到0.0.0.0 (外部可访问)"
    else
        echo "  ❌ 绑定到127.0.0.1 (仅本地访问)"
    fi
else
    echo "❌ 端口8050未监听"
fi

echo ""
echo "📋 网络连接测试..."
echo "=================================================="

# 获取本机IP
local_ip=$(hostname -I | awk '{print $1}')
echo "本机IP: $local_ip"

# 测试本地连接
echo ""
echo "本地连接测试:"
if curl -s http://localhost:8000 > /dev/null 2>&1; then
    echo "  ✅ 本地API服务正常: http://localhost:8000"
else
    echo "  ❌ 本地API服务异常"
fi

if curl -s http://localhost:8050 > /dev/null 2>&1; then
    echo "  ✅ 本地Web界面正常: http://localhost:8050"
else
    echo "  ❌ 本地Web界面异常"
fi

# 测试本机IP连接
echo ""
echo "本机IP连接测试:"
if curl -s http://$local_ip:8000 > /dev/null 2>&1; then
    echo "  ✅ 本机IP API服务正常: http://$local_ip:8000"
else
    echo "  ❌ 本机IP API服务异常"
fi

if curl -s http://$local_ip:8050 > /dev/null 2>&1; then
    echo "  ✅ 本机IP Web界面正常: http://$local_ip:8050"
else
    echo "  ❌ 本机IP Web界面异常"
fi

echo ""
echo "📋 日志文件信息..."
echo "=================================================="

# 检查PID文件
pid_file="logs/service.pid"
if [ -f "$pid_file" ]; then
    pid=$(cat "$pid_file")
    echo "PID文件: $pid_file"
    echo "记录PID: $pid"
    
    # 检查PID是否有效
    if kill -0 "$pid" 2>/dev/null; then
        echo "✅ PID有效"
    else
        echo "❌ PID无效或进程已退出"
    fi
else
    echo "⚠️  PID文件不存在"
fi

# 查找最新的日志文件
echo ""
echo "日志文件:"
log_files=$(ls -t logs/service_*.log 2>/dev/null | head -5)
if [ ! -z "$log_files" ]; then
    for log_file in $log_files; do
        if [ -f "$log_file" ]; then
            file_size=$(du -h "$log_file" | cut -f1)
            mod_time=$(stat -c %y "$log_file" | cut -d' ' -f1,2)
            echo "  📄 $log_file ($file_size, 修改时间: $mod_time)"
        fi
    done
else
    echo "  ⚠️  未找到日志文件"
fi

echo ""
echo "📋 系统资源使用..."
echo "=================================================="

# 显示系统资源使用情况
echo "内存使用:"
free -h | grep -E "Mem|Swap"

echo ""
echo "磁盘使用:"
df -h | grep -E "/$|/home"

echo ""
echo "📋 防火墙状态..."
echo "=================================================="

# 检查防火墙状态
if command -v firewall-cmd &> /dev/null; then
    firewall_status=$(firewall-cmd --state 2>/dev/null)
    if [ "$firewall_status" = "running" ]; then
        echo "✅ firewalld正在运行"
        if firewall-cmd --query-port=8000/tcp &>/dev/null; then
            echo "  ✅ 端口8000已开放"
        else
            echo "  ❌ 端口8000未开放"
        fi
        if firewall-cmd --query-port=8050/tcp &>/dev/null; then
            echo "  ✅ 端口8050已开放"
        else
            echo "  ❌ 端口8050未开放"
        fi
    else
        echo "⚠️  firewalld未运行"
    fi
elif command -v ufw &> /dev/null; then
    ufw_status=$(ufw status 2>/dev/null | grep "Status")
    if echo "$ufw_status" | grep -q "active"; then
        echo "✅ ufw正在运行"
        if ufw status | grep -q "8000"; then
            echo "  ✅ 端口8000已开放"
        else
            echo "  ❌ 端口8000未开放"
        fi
        if ufw status | grep -q "8050"; then
            echo "  ✅ 端口8050已开放"
        else
            echo "  ❌ 端口8050未开放"
        fi
    else
        echo "⚠️  ufw未运行"
    fi
else
    echo "⚠️  未检测到常见防火墙"
fi

echo ""
echo "📋 服务管理命令..."
echo "=================================================="

echo "启动服务: ./start_service.sh"
echo "停止服务: ./stop_service.sh"
echo "重启服务: ./stop_service.sh && ./start_service.sh"
echo "查看实时日志: tail -f logs/service_*.log"

echo ""
echo "✅ 服务状态检查完成!"
echo "=================================================="
