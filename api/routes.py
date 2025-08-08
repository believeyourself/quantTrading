from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import threading
import time
import traceback
import os

from utils.models import Strategy, SessionLocal, get_db
from strategies.factory import StrategyFactory
from strategies.funding_rate_arbitrage import FundingRateMonitor
from data.manager import data_manager
from config.settings import settings
from utils.notifier import send_telegram_message

# 在文件顶部导入os
import os

app = FastAPI(title="加密货币资金费率监控系统", version="1.0.0")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic模型
class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    strategy_type: str
    parameters: Optional[Dict[str, Any]] = None

class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class FundingMonitorRequest(BaseModel):
    parameters: Optional[Dict[str, Any]] = None

# 全局资金费率监控策略实例
funding_monitor_instance = None
funding_monitor_thread = None
funding_monitor_running = False

def create_funding_monitor(params: dict = None):
    """创建资金费率监控策略实例"""
    global funding_monitor_instance
    
    default_params = {
        'funding_rate_threshold': 0.005,
        'contract_refresh_interval': 60,
        'funding_rate_check_interval': 60,
        'max_pool_size': 20,
        'min_volume': 1000000,
        'exchanges': ['binance', 'okx', 'bybit']
    }
    
    if params:
        default_params.update(params)
    
    funding_monitor_instance = FundingRateMonitor(default_params)
    return funding_monitor_instance

def funding_monitor_loop():
    """资金费率监控循环"""
    global funding_monitor_running, funding_monitor_instance
    
    while funding_monitor_running:
        try:
            if funding_monitor_instance:
                # 获取监控状态
                status = funding_monitor_instance.get_pool_status()
                
                # 这里可以添加更多的监控逻辑
                # 比如检查监控是否正常运行，发送定期报告等
                
            time.sleep(60)  # 每分钟检查一次
            
        except Exception as e:
            print(f"资金费率监控错误: {e}")
            time.sleep(30)

# 策略管理API
@app.get("/strategies", response_model=List[Dict[str, Any]])
def get_strategies(db: SessionLocal = Depends(get_db)):
    """获取所有策略"""
    try:
        strategies = db.query(Strategy).filter(Strategy.strategy_type == "funding_rate_arbitrage").all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "strategy_type": s.strategy_type,
                "parameters": s.get_parameters(),
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat()
            }
            for s in strategies
        ]
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取策略失败: {str(e)}")

@app.get("/strategies/available")
def get_available_strategies():
    """获取可用策略类型"""
    try:
        strategies = StrategyFactory.get_available_strategies()
        return {
            "strategies": [
                {
                    "type": s,
                    "name": "资金费率监控策略"
                }
                for s in strategies
            ]
        }
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取可用策略失败: {str(e)}")

@app.post("/strategies", response_model=Dict[str, Any])
def create_strategy(strategy: StrategyCreate, db: SessionLocal = Depends(get_db)):
    """创建新策略"""
    try:
        # 验证策略类型
        if strategy.strategy_type not in StrategyFactory.get_available_strategies():
            raise HTTPException(status_code=400, detail="不支持的策略类型")
        
        # 检查策略名称是否已存在
        existing = db.query(Strategy).filter(Strategy.name == strategy.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="策略名称已存在")
        
        # 创建策略
        db_strategy = Strategy(
            name=strategy.name,
            description=strategy.description,
            strategy_type=strategy.strategy_type,
            parameters=json.dumps(strategy.parameters or {})
        )
        
        db.add(db_strategy)
        db.commit()
        db.refresh(db_strategy)
        
        return {
            "id": db_strategy.id,
            "name": db_strategy.name,
            "description": db_strategy.description,
            "strategy_type": db_strategy.strategy_type,
            "parameters": db_strategy.get_parameters(),
            "is_active": db_strategy.is_active,
            "created_at": db_strategy.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建策略失败: {str(e)}")

@app.put("/strategies/{strategy_id}", response_model=Dict[str, Any])
def update_strategy(strategy_id: int, strategy_update: StrategyUpdate, 
                   db: SessionLocal = Depends(get_db)):
    """更新策略"""
    try:
        # 查找策略
        db_strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not db_strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        # 更新策略
        if strategy_update.name is not None:
            db_strategy.name = strategy_update.name
        if strategy_update.description is not None:
            db_strategy.description = strategy_update.description
        if strategy_update.parameters is not None:
            db_strategy.parameters = json.dumps(strategy_update.parameters)
        if strategy_update.is_active is not None:
            db_strategy.is_active = strategy_update.is_active
        
        db.commit()
        db.refresh(db_strategy)
        
        return {
            "id": db_strategy.id,
            "name": db_strategy.name,
            "description": db_strategy.description,
            "strategy_type": db_strategy.strategy_type,
            "parameters": db_strategy.get_parameters(),
            "is_active": db_strategy.is_active,
            "updated_at": db_strategy.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新策略失败: {str(e)}")

@app.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int, db: SessionLocal = Depends(get_db)):
    """删除策略"""
    try:
        # 查找策略
        db_strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not db_strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        db.delete(db_strategy)
        db.commit()
        
        return {"message": "策略删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除策略失败: {str(e)}")

# 资金费率监控API
@app.post("/funding_monitor/start")
def start_funding_monitor(request: FundingMonitorRequest = None, background_tasks: BackgroundTasks = None):
    """启动资金费率监控"""
    global funding_monitor_running, funding_monitor_thread
    
    try:
        if funding_monitor_running:
            return {"status": "success", "message": "资金费率监控已经在运行中"}
        
        # 创建监控实例
        params = request.parameters if request else None
        create_funding_monitor(params)
        
        # 启动监控线程
        funding_monitor_running = True
        funding_monitor_thread = threading.Thread(target=funding_monitor_loop, daemon=True)
        funding_monitor_thread.start()
        
        # 启动实际监控
        funding_monitor_instance.start_monitoring()
        
        send_telegram_message("资金费率监控已启动")
        return {"status": "success", "message": "资金费率监控已成功启动"}
        
    except Exception as e:
        print(f"启动资金费率监控异常: {e}\n{traceback.format_exc()}")
        funding_monitor_running = False
        raise HTTPException(status_code=500, detail=f"启动监控失败: {str(e)}")

@app.post("/funding_monitor/stop")
def stop_funding_monitor():
    """停止资金费率监控"""
    global funding_monitor_running, funding_monitor_instance
    
    try:
        if not funding_monitor_running:
            return {"status": "success", "message": "资金费率监控未运行"}
        
        funding_monitor_running = False
        if funding_monitor_instance:
            funding_monitor_instance.stop_monitoring()
        
        send_telegram_message("资金费率监控已停止")
        return {"status": "success", "message": "资金费率监控已成功停止"}
        
    except Exception as e:
        print(f"停止资金费率监控异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"停止监控失败: {str(e)}")

@app.get("/funding_monitor/status")
def get_funding_monitor_status():
    """获取资金费率监控状态"""
    global funding_monitor_running, funding_monitor_instance
    
    try:
        if not funding_monitor_running or not funding_monitor_instance:
            return {
                "running": False,
                "status": "监控未运行"
            }
        
        # 获取监控状态
        pool_status = funding_monitor_instance.get_pool_status()
        
        return {
            "running": True,
            "pool_status": pool_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"获取资金费率监控状态异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取监控状态失败: {str(e)}")

# 移除重复的路由定义，保留下面的 get_funding_pool 函数

# 数据API
@app.get("/symbols")
def get_symbols():
    """获取所有交易对"""
    try:
        symbols = data_manager.get_symbols()
        return {
            "symbols": symbols,
            "count": len(symbols)
        }
    except Exception as e:
        print(f"获取交易对异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取交易对失败: {str(e)}")

@app.get("/funding_rates")
def get_funding_rates(symbol: Optional[str] = None, exchange: Optional[str] = None):
    """获取资金费率"""
    try:
        if symbol:
            rates = data_manager.get_funding_rate(symbol, exchange)
            return {
                "symbol": symbol,
                "exchange": exchange,
                "funding_rate": rates
            }
        else:
            rates = data_manager.get_all_funding_rates(exchange)
            return {
                "exchange": exchange,
                "funding_rates": rates,
                "count": len(rates)
            }
    except Exception as e:
        print(f"获取资金费率异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取资金费率失败: {str(e)}")

# 系统状态API
@app.get("/system/status")
def get_system_status():
    """获取系统状态"""
    try:
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "funding_monitor_running": funding_monitor_running
        }
    except Exception as e:
        print(f"获取系统状态异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {str(e)}")

@app.post("/funding_monitor/refresh-candidates")
def refresh_funding_candidates():
    """刷新备选合约池"""
    global funding_monitor_instance

    try:
        # 如果监控未启动，临时创建一个实例
        if not funding_monitor_instance:
            from strategies.funding_rate_arbitrage import FundingRateMonitor
            funding_monitor_instance = FundingRateMonitor()
            print("临时创建监控实例用于刷新备选池")

        funding_monitor_instance.refresh_contract_pool()
        return {
            "status": "success",
            "message": "备选合约池刷新成功",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"刷新备选合约池异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"刷新备选合约池失败: {str(e)}")

@app.get("/funding_monitor/pool")
def get_funding_pool():
    """获取当前监控合约池"""
    global funding_monitor_instance

    try:
        if not funding_monitor_instance:
            from strategies.funding_rate_arbitrage import FundingRateMonitor
            funding_monitor_instance = FundingRateMonitor()
            print("临时创建监控实例用于获取合约池数据")

        contracts = funding_monitor_instance.contract_pool
        return {
            "status": "success",
            "contracts": list(contracts),
            "count": len(contracts),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"获取合约池异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取合约池失败: {str(e)}")

@app.get("/funding_monitor/candidates")
def get_funding_candidates():
    """获取备选合约池"""
    global funding_monitor_instance

    try:
        if not funding_monitor_instance:
            from strategies.funding_rate_arbitrage import FundingRateMonitor
            funding_monitor_instance = FundingRateMonitor()
            print("临时创建监控实例用于获取备选合约数据")

        candidates = funding_monitor_instance.candidate_contracts
        return {
            "status": "success",
            "contracts": candidates,
            "count": len(candidates),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"获取备选合约异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取备选合约失败: {str(e)}")

@app.get("/funding_monitor/all-contracts")
def get_all_1h_contracts():
    """获取所有1小时结算合约"""
    try:
        from utils.binance_funding import BinanceFunding
        funding = BinanceFunding()
        all_contracts = funding.get_1h_contracts_from_cache()
        
        # 转换数据格式以匹配Web界面期望的格式
        formatted_contracts = {}
        for symbol, info in all_contracts.items():
            formatted_contracts[symbol] = {
                "symbol": symbol,
                "exchange": "binance",
                "funding_rate": float(info.get("current_funding_rate", 0)),
                "funding_time": info.get("next_funding_time", ""),
                "volume_24h": info.get("volume_24h", 0),
                "mark_price": info.get("mark_price", 0)
            }
        
        return {
            "status": "success",
            "contracts": formatted_contracts,
            "count": len(formatted_contracts),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"获取所有1小时结算合约异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取所有1小时结算合约失败: {str(e)}")