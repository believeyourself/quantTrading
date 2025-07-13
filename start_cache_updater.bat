@echo off
echo 启动1小时结算合约缓存更新进程...
echo 按 Ctrl+C 停止进程
echo.

cd /d "%~dp0"
python update_1h_contracts_cache.py

pause 