@echo off
chcp 65001 >nul
echo 🚀 启动资金费率合约池监控器
echo ========================================
echo.
echo 📊 功能说明:
echo   • 缓存1小时结算周期合约
echo   • 监控资金费率 >= 0.5%% 或 <= -0.5%% 的合约
echo   • 合约池变化时发送TG消息
echo   • 定时更新缓存和检测
echo.
echo ⏰ 默认配置:
echo   • 资金费率阈值: 0.5%%
echo   • 扫描间隔: 30分钟
echo   • 缓存更新间隔: 6小时
echo.
echo 按任意键开始运行...
pause >nul

python monitor_funding_pool.py

echo.
echo 监控已结束，按任意键退出...
pause >nul 