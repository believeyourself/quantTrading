@echo off
chcp 65001 >nul
title 加密货币资金费率监控系统

echo ========================================
echo 🚀 加密货币资金费率监控系统
echo ========================================
echo.
echo 请选择启动模式:
echo 1. 🌐 Web界面 (端口8050)
echo 2. 🔌 API服务 (端口8000)
echo 3. 🚀 主程序 (监控系统)
echo 4. 🎯 全部启动 (Web + API)
echo 5. ❌ 退出
echo.
echo ========================================

set /p choice=请输入选择 (1-5): 

if "%choice%"=="1" (
    echo 🌐 启动Web界面...
    python start.py web
) else if "%choice%"=="2" (
    echo 🔌 启动API服务...
    python start.py api
) else if "%choice%"=="3" (
    echo 🚀 启动主程序...
    python start.py main
) else if "%choice%"=="4" (
    echo 🎯 启动所有服务...
    python start.py all
) else if "%choice%"=="5" (
    echo 👋 再见!
    pause
    exit
) else (
    echo ❌ 无效选择
    pause
)
