from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import json
import threading
import time
import traceback
import os

from utils.models import Strategy, Backtest, Trade, SessionLocal, get_db
from strategies.factory import StrategyFactory
from strategies.funding_rate_arbitrage import FundingRateArbitrageStrategy
from backtest.engine import BacktestEngine, BacktestManager
from trading.manager import TradingManager, trading_manager
from data.manager import data_manager
from config.settings import settings
from utils.notifier import send_telegram_message

app = FastAPI(title="量化交易系统", version="1.0.0")

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

class BacktestRequest(BaseModel):
    strategy_id: int
    symbol: str
    timeframe: str = "1d"
    start_date: str
    end_date: str
    initial_capital: float = 10000.0

class TradingRequest(BaseModel):
    engine_name: str
    strategy_type: str
    symbol: str
    timeframe: str = "1d"
    trade_type: str = "paper"  # paper 或 live
    parameters: Optional[Dict[str, Any]] = None

class FundingArbitrageRequest(BaseModel):
    parameters: Optional[Dict[str, Any]] = None

# 全局资金费率套利策略实例
funding_strategy_instance = None
funding_strategy_thread = None
funding_strategy_running = False

def create_funding_strategy(params: dict = None):
    """创建资金费率套利策略实例"""
    global funding_strategy_instance
    
    default_params = {
        'funding_rate_threshold': 0.005,
        'max_positions': 20,
        'min_volume': 1000000,
        'position_size_ratio': 0.05,
        'max_total_exposure': 0.8,
        'stop_loss_ratio': 0.05,
        'take_profit_ratio': 0.10,
        'auto_trade': True,
        'paper_trading': True,
        'min_position_hold_time': 3600
    }
    
    if params:
        default_params.update(params)
    
    funding_strategy_instance = FundingRateArbitrageStrategy(default_params)
    return funding_strategy_instance

def funding_strategy_monitor_loop():
    """资金费率套利策略监控循环"""
    global funding_strategy_running, funding_strategy_instance
    
    while funding_strategy_running:
        try:
            if funding_strategy_instance:
                # 获取策略状态
                status = funding_strategy_instance.get_pool_status()
                
                # 这里可以添加更多的监控逻辑
                # 比如检查策略是否正常运行，发送定期报告等
                
            time.sleep(60)  # 每分钟检查一次
            
        except Exception as e:
            print(f"资金费率策略监控错误: {e}")
            time.sleep(30)

# 策略管理API
@app.get("/strategies", response_model=List[Dict[str, Any]])
def get_strategies(db: SessionLocal = Depends(get_db)):
    """获取所有策略"""
    try:
        strategies = db.query(Strategy).all()
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
                    "name": StrategyFactory.get_strategy_description(s)
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
        db_strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not db_strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        # 更新字段
        if strategy_update.name is not None:
            db_strategy.name = strategy_update.name
        if strategy_update.description is not None:
            db_strategy.description = strategy_update.description
        if strategy_update.parameters is not None:
            db_strategy.set_parameters(strategy_update.parameters)
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

@app.get("/strategies/{strategy_id}/pool-status")
def get_strategy_pool_status(strategy_id: int, db: SessionLocal = Depends(get_db)):
    """获取策略池子状态（适用于资金费率套利策略）"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    if strategy.strategy_type == "funding_rate_arbitrage":
        # 创建策略实例获取池子状态
        strategy_instance = StrategyFactory.create_strategy(
            strategy.strategy_type, 
            json.loads(strategy.parameters)
        )
        return strategy_instance.get_pool_status()
    else:
        raise HTTPException(status_code=400, detail="该策略不支持池子状态查询")

@app.post("/strategies/{strategy_id}/run-funding-arbitrage")
def run_funding_arbitrage(strategy_id: int, db: SessionLocal = Depends(get_db)):
    """运行资金费率套利策略"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    if strategy.strategy_type != "funding_rate_arbitrage":
        raise HTTPException(status_code=400, detail="该策略不是资金费率套利策略")
    
    try:
        # 创建策略实例
        strategy_instance = StrategyFactory.create_strategy(
            strategy.strategy_type, 
            json.loads(strategy.parameters)
        )
        
        # 运行策略生成信号
        signals = strategy_instance.generate_signals(pd.DataFrame())
        
        return {
            "message": "资金费率套利策略运行成功",
            "signals_count": len(signals),
            "pool_status": strategy_instance.get_pool_status()
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"策略运行失败: {str(e)}")

@app.post("/strategies/{strategy_id}/update-cache")
def update_funding_cache(strategy_id: int, db: SessionLocal = Depends(get_db)):
    """强制更新资金费率套利策略缓存"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    if strategy.strategy_type != "funding_rate_arbitrage":
        raise HTTPException(status_code=400, detail="该策略不是资金费率套利策略")
    
    try:
        # 创建策略实例
        strategy_instance = StrategyFactory.create_strategy(
            strategy.strategy_type, 
            json.loads(strategy.parameters)
        )
        
        # 强制更新缓存
        update_result = strategy_instance.force_update_cache()
        
        return {
            "message": "缓存更新成功",
            "update_result": update_result,
            "pool_status": strategy_instance.get_pool_status()
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"缓存更新失败: {str(e)}")

@app.get("/strategies/{strategy_id}/cache-status")
def get_cache_status(strategy_id: int, db: SessionLocal = Depends(get_db)):
    """获取资金费率套利策略缓存状态"""
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    if strategy.strategy_type != "funding_rate_arbitrage":
        raise HTTPException(status_code=400, detail="该策略不是资金费率套利策略")
    
    try:
        # 创建策略实例
        strategy_instance = StrategyFactory.create_strategy(
            strategy.strategy_type, 
            json.loads(strategy.parameters)
        )
        
        # 获取缓存状态
        pool_status = strategy_instance.get_pool_status()
        
        return {
            "cache_status": {
                "cached_contracts_count": pool_status.get('cached_contracts_count', 0),
                "last_update_time": pool_status.get('last_update_time'),
                "cache_valid": pool_status.get('cache_valid', False),
                "pool_size": pool_status.get('pool_size', 0)
            },
            "strategy_info": {
                "name": strategy.name,
                "strategy_type": strategy.strategy_type,
                "parameters": strategy.get_parameters()
            }
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取缓存状态失败: {str(e)}")

# 回测API
@app.post("/backtest", response_model=Dict[str, Any])
def run_backtest(backtest_request: BacktestRequest, background_tasks: BackgroundTasks):
    """运行回测"""
    try:
        # 获取策略
        db = SessionLocal()
        strategy = db.query(Strategy).filter(Strategy.id == backtest_request.strategy_id).first()
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        # 创建策略实例
        strategy_instance = StrategyFactory.create_strategy(
            strategy.strategy_type, 
            strategy.get_parameters()
        )
        
        # 创建回测引擎
        engine = BacktestEngine(backtest_request.initial_capital)
        
        # 运行回测
        results = engine.run_backtest(
            strategy_instance,
            backtest_request.symbol,
            backtest_request.start_date,
            backtest_request.end_date,
            backtest_request.timeframe
        )
        
        # 返回简化的结果，包含权益曲线数据
        return {
            "backtest_id": results.get('backtest_id', 0),
            "results": {
                "total_return": results['results'].get('total_return', 0.0),
                "max_drawdown": results['results'].get('max_drawdown', 0.0),
                "sharpe_ratio": results['results'].get('sharpe_ratio', 0.0),
                "win_rate": results['results'].get('win_rate', 0.0),
                "total_trades": results['results'].get('total_trades', 0)
            },
            "trades": results.get('trades', []),
            "equity_curve": results.get('equity_curve', [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"回测失败: {str(e)}")

@app.get("/backtest/{backtest_id}", response_model=Dict[str, Any])
def get_backtest(backtest_id: int, db: SessionLocal = Depends(get_db)):
    """获取回测结果"""
    try:
        backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
        if not backtest:
            raise HTTPException(status_code=404, detail="回测记录不存在")
        
        return {
            "id": backtest.id,
            "name": backtest.name,
            "symbol": backtest.symbol,
            "timeframe": backtest.timeframe,
            "start_date": backtest.start_date.isoformat(),
            "end_date": backtest.end_date.isoformat(),
            "initial_capital": backtest.initial_capital,
            "final_capital": backtest.final_capital,
            "total_return": backtest.total_return,
            "max_drawdown": backtest.max_drawdown,
            "sharpe_ratio": backtest.sharpe_ratio,
            "win_rate": backtest.win_rate,
            "total_trades": backtest.total_trades,
            "status": backtest.status,
            "created_at": backtest.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取回测结果失败: {str(e)}")

@app.get("/backtest/{backtest_id}/trades", response_model=List[Dict[str, Any]])
def get_backtest_trades(backtest_id: int, db: SessionLocal = Depends(get_db)):
    """获取回测交易记录"""
    try:
        from utils.models import BacktestTrade
        trades = db.query(BacktestTrade).filter(
            BacktestTrade.backtest_id == backtest_id
        ).order_by(BacktestTrade.timestamp).all()
        
        return [
            {
                "timestamp": trade.timestamp.isoformat(),
                "symbol": trade.symbol,
                "side": trade.side,
                "quantity": trade.quantity,
                "price": trade.price,
                "commission": trade.commission,
                "pnl": trade.pnl,
                "strategy_signal": trade.strategy_signal
            }
            for trade in trades
        ]
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取交易记录失败: {str(e)}")

@app.get("/backtests", response_model=List[Dict[str, Any]])
def list_backtests(strategy_id: Optional[int] = None, db: SessionLocal = Depends(get_db)):
    """列出回测记录"""
    try:
        query = db.query(Backtest)
        if strategy_id:
            query = query.filter(Backtest.strategy_id == strategy_id)
        
        backtests = query.order_by(Backtest.created_at.desc()).all()
        
        return [
            {
                "id": b.id,
                "name": b.name,
                "symbol": b.symbol,
                "timeframe": b.timeframe,
                "start_date": b.start_date.isoformat(),
                "end_date": b.end_date.isoformat(),
                "total_return": b.total_return,
                "max_drawdown": b.max_drawdown,
                "sharpe_ratio": b.sharpe_ratio,
                "win_rate": b.win_rate,
                "total_trades": b.total_trades,
                "status": b.status,
                "created_at": b.created_at.isoformat()
            }
            for b in backtests
        ]
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取回测列表失败: {str(e)}")

# 交易API
@app.post("/trading/engine", response_model=Dict[str, Any])
def create_trading_engine(request: TradingRequest):
    """创建交易引擎"""
    try:
        engine = trading_manager.create_engine(
            request.engine_name,
            request.trade_type,
            "binance"  # 默认使用Binance
        )
        
        # 创建策略实例
        strategy = StrategyFactory.create_strategy(
            request.strategy_type,
            request.parameters
        )
        
        # 添加策略到引擎
        engine.add_strategy(strategy)
        
        return {
            "engine_name": request.engine_name,
            "trade_type": request.trade_type,
            "strategy": strategy.name,
            "status": "created"
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"创建交易引擎失败: {str(e)}")

@app.post("/trading/run", response_model=Dict[str, Any])
def run_trading(request: TradingRequest):
    """运行交易策略"""
    try:
        engine = trading_manager.get_engine(request.engine_name)
        if not engine:
            raise HTTPException(status_code=404, detail="交易引擎不存在")
        
        # 创建策略实例
        strategy = StrategyFactory.create_strategy(
            request.strategy_type,
            request.parameters
        )
        
        # 运行策略
        trading_manager.run_strategy(
            request.engine_name,
            strategy,
            request.symbol,
            request.timeframe
        )
        
        return {
            "engine_name": request.engine_name,
            "strategy": strategy.name,
            "symbol": request.symbol,
            "status": "running"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"运行交易策略失败: {str(e)}")

@app.get("/trading/engines", response_model=List[str])
def list_trading_engines():
    """列出所有交易引擎"""
    try:
        return trading_manager.list_engines()
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取交易引擎列表失败: {str(e)}")

@app.get("/trading/engine/{engine_name}/account", response_model=Dict[str, Any])
def get_account_summary(engine_name: str):
    """获取账户摘要"""
    try:
        engine = trading_manager.get_engine(engine_name)
        if not engine:
            raise HTTPException(status_code=404, detail="交易引擎不存在")
        
        return engine.get_account_summary()
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取账户摘要失败: {str(e)}")

@app.get("/trading/engine/{engine_name}/positions", response_model=List[Dict[str, Any]])
def get_positions(engine_name: str):
    """获取持仓信息"""
    try:
        engine = trading_manager.get_engine(engine_name)
        if not engine:
            raise HTTPException(status_code=404, detail="交易引擎不存在")
        
        return engine.get_positions()
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取持仓信息失败: {str(e)}")

@app.get("/trading/trades", response_model=List[Dict[str, Any]])
def get_trade_history(symbol: Optional[str] = None, limit: int = 100, 
                     db: SessionLocal = Depends(get_db)):
    """获取交易历史"""
    try:
        query = db.query(Trade)
        if symbol:
            query = query.filter(Trade.symbol == symbol)
        
        trades = query.order_by(Trade.timestamp.desc()).limit(limit).all()
        
        return [
            {
                "id": t.id,
                "timestamp": t.timestamp.isoformat(),
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "commission": t.commission,
                "status": t.status,
                "trade_type": t.trade_type
            }
            for t in trades
        ]
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取交易历史失败: {str(e)}")

# 数据API
@app.get("/data/symbols", response_model=List[str])
def get_symbols():
    """获取支持的交易对"""
    try:
        return data_manager.get_symbols()
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取交易对列表失败: {str(e)}")

@app.get("/data/{symbol}/price")
def get_latest_price(symbol: str):
    """获取最新价格"""
    try:
        price = data_manager.get_latest_price(symbol)
        if price is None:
            raise HTTPException(status_code=404, detail="无法获取价格")
        
        return {"symbol": symbol, "price": price, "timestamp": datetime.now().isoformat()}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取价格失败: {str(e)}")

@app.post("/data/{symbol}/update")
def update_market_data(symbol: str, timeframe: str = "1d"):
    """更新市场数据"""
    try:
        data_manager.update_market_data(symbol, timeframe)
        return {"message": f"成功更新 {symbol} 的 {timeframe} 数据"}
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"更新市场数据失败: {str(e)}")

# 系统状态API
@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/config")
def get_config():
    """获取系统配置"""
    return {
        "data_source": settings.DATA_SOURCE,
        "default_capital": settings.DEFAULT_CAPITAL,
        "max_position_size": settings.MAX_POSITION_SIZE,
        "stop_loss_ratio": settings.STOP_LOSS_RATIO,
        "take_profit_ratio": settings.TAKE_PROFIT_RATIO,
        "supported_exchanges": list(settings.SUPPORTED_EXCHANGES.keys()),
        "timeframes": list(settings.TIMEFRAMES.keys())
    }

# 资金费率套利API
@app.get("/funding-arbitrage/status")
def get_funding_strategy_status():
    """获取资金费率套利策略状态"""
    global funding_strategy_instance, funding_strategy_running
    
    try:
        if not funding_strategy_instance:
            return {
                'status': 'success',
                'data': {
                    'status': 'not_initialized',
                    'message': '策略未初始化'
                }
            }
        
        pool_status = funding_strategy_instance.get_pool_status()
        positions = funding_strategy_instance.get_positions()
        
        # 格式化持仓信息
        formatted_positions = []
        for symbol, pos in positions.items():
            formatted_positions.append({
                'symbol': pos.symbol,
                'side': pos.side,
                'quantity': pos.quantity,
                'entry_price': pos.entry_price,
                'entry_time': pos.entry_time.isoformat(),
                'funding_rate': pos.funding_rate,
                'unrealized_pnl': pos.unrealized_pnl,
                'realized_pnl': pos.realized_pnl
            })
        
        return {
            'status': 'success',
            'data': {
                'status': 'running' if funding_strategy_running else 'stopped',
                'strategy_name': funding_strategy_instance.name,
                'pool_status': pool_status,
                'positions': formatted_positions,
                'timestamp': datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取策略状态失败: {str(e)}")

@app.get("/funding-arbitrage/pool-status")
def get_funding_pool_status():
    """获取资金费率套利池子状态"""
    global funding_strategy_instance
    
    try:
        if not funding_strategy_instance:
            raise HTTPException(status_code=400, detail="策略未初始化")
        
        pool_status = funding_strategy_instance.get_pool_status()
        
        return {
            'status': 'success',
            'data': pool_status
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取池子状态失败: {str(e)}")

@app.post("/funding-arbitrage/start")
def start_funding_strategy(request: FundingArbitrageRequest = None):
    """启动资金费率套利策略"""
    global funding_strategy_instance, funding_strategy_thread, funding_strategy_running
    
    try:
        if request is None:
            request = FundingArbitrageRequest()
        
        # 创建策略实例
        funding_strategy_instance = create_funding_strategy(request.parameters)
        
        # 启动策略（放到新线程中，避免阻塞API）
        def start_strategy_thread():
            funding_strategy_instance.start_strategy()
        strategy_thread = threading.Thread(target=start_strategy_thread, daemon=True)
        strategy_thread.start()
        
        # 启动策略监控线程
        funding_strategy_running = True
        funding_strategy_thread = threading.Thread(target=funding_strategy_monitor_loop, daemon=True)
        funding_strategy_thread.start()
        
        # 发送启动通知
        start_message = f"🚀 资金费率套利策略已启动\n"
        start_message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        start_message += f"📊 策略: {funding_strategy_instance.name}\n"
        start_message += f"🎯 资金费率阈值: {funding_strategy_instance.parameters['funding_rate_threshold']:.4%}\n"
        start_message += f"📈 最大持仓: {funding_strategy_instance.parameters['max_positions']}个\n"
        start_message += f"💰 仓位比例: {funding_strategy_instance.parameters['position_size_ratio']:.1%}\n"
        start_message += f"📱 交易模式: {'模拟交易' if funding_strategy_instance.parameters['paper_trading'] else '实盘交易'}\n"
        start_message += f"⏰ 更新模式: 整点定时更新"
        
        send_telegram_message(start_message)
        
        return {
            'status': 'success',
            'message': '策略启动成功，等待整点开始定时更新',
            'strategy_name': funding_strategy_instance.name
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"启动策略失败: {str(e)}")

@app.post("/funding-arbitrage/stop")
def stop_funding_strategy():
    """停止资金费率套利策略"""
    global funding_strategy_running, funding_strategy_instance
    
    try:
        funding_strategy_running = False
        
        if funding_strategy_instance:
            # 停止策略
            funding_strategy_instance.stop_strategy()
            
            # 发送停止通知
            status = funding_strategy_instance.get_pool_status()
            stop_message = f"🛑 资金费率套利策略已停止\n"
            stop_message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            stop_message += f"📊 最终状态:\n"
            stop_message += f"  总盈亏: {status['total_pnl']:.2f}\n"
            stop_message += f"  总交易: {status['total_trades']}次\n"
            stop_message += f"  胜率: {status['win_rate']:.1%}\n"
            stop_message += f"  当前持仓: {status['current_positions']}个"
            
            send_telegram_message(stop_message)
        
        return {
            'status': 'success',
            'message': '策略停止成功'
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"停止策略失败: {str(e)}")

@app.get("/funding-arbitrage/positions")
def get_funding_positions():
    """获取资金费率套利当前持仓"""
    global funding_strategy_instance
    
    try:
        if not funding_strategy_instance:
            raise HTTPException(status_code=400, detail="策略未初始化")
        
        positions = funding_strategy_instance.get_positions()
        formatted_positions = []
        
        for symbol, pos in positions.items():
            formatted_positions.append({
                'symbol': pos.symbol,
                'side': pos.side,
                'quantity': pos.quantity,
                'entry_price': pos.entry_price,
                'entry_time': pos.entry_time.isoformat(),
                'funding_rate': pos.funding_rate,
                'unrealized_pnl': pos.unrealized_pnl,
                'realized_pnl': pos.realized_pnl
            })
        
        return {
            'status': 'success',
            'positions': formatted_positions,
            'count': len(formatted_positions)
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取持仓失败: {str(e)}")

@app.post("/funding-arbitrage/close-all")
def close_all_funding_positions():
    """平掉所有资金费率套利持仓"""
    global funding_strategy_instance
    
    try:
        if not funding_strategy_instance:
            raise HTTPException(status_code=400, detail="策略未初始化")
        
        # 平掉所有持仓
        closed_positions = funding_strategy_instance.close_all_positions()
        # 发送通知
        close_message = f"📊 平仓操作完成\n"
        close_message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        close_message += f"📈 平仓数量: {len(closed_positions)}个\n"
        if closed_positions:
            close_message += f"📋 平仓详情:\n"
            for pos in closed_positions:
                if isinstance(pos, dict):
                    close_message += f"  {pos['symbol']}: {pos['side']} {pos['quantity']:.4f} @ {pos['entry_price']:.4f}\n"
                else:
                    close_message += f"  [异常持仓数据]: {pos}\n"
        send_telegram_message(close_message)
        return {
            'status': 'success',
            'message': '平仓操作完成',
            'closed_positions': closed_positions
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"平仓失败: {str(e)}")

@app.post("/funding-arbitrage/update-cache")
def update_funding_cache():
    """更新资金费率套利缓存"""
    global funding_strategy_instance
    
    try:
        if not funding_strategy_instance:
            raise HTTPException(status_code=400, detail="策略未初始化")
        
        # 强制更新缓存
        update_result = funding_strategy_instance.force_update_cache()
        
        return {
            'status': 'success',
            'message': '缓存更新成功',
            'update_result': update_result,
            'pool_status': funding_strategy_instance.get_pool_status()
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"缓存更新失败: {str(e)}")

@app.get("/funding-arbitrage/parameters")
def get_funding_parameters():
    """获取资金费率套利策略参数"""
    global funding_strategy_instance
    
    try:
        if not funding_strategy_instance:
            raise HTTPException(status_code=400, detail="策略未初始化")
        
        return {
            'status': 'success',
            'parameters': funding_strategy_instance.parameters
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取参数失败: {str(e)}")

@app.put("/funding-arbitrage/parameters")
def update_funding_parameters(request: FundingArbitrageRequest):
    """更新资金费率套利策略参数"""
    global funding_strategy_instance
    
    try:
        if not funding_strategy_instance:
            raise HTTPException(status_code=400, detail="策略未初始化")
        
        if request.parameters:
            funding_strategy_instance.update_parameters(request.parameters)
        
        return {
            'status': 'success',
            'message': '参数更新成功',
            'parameters': funding_strategy_instance.parameters
        }
        
    except Exception as e:
        print(f"接口发生异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"更新参数失败: {str(e)}")

@app.get("/funding-arbitrage/health")
def funding_health_check():
    """资金费率套利健康检查"""
    global funding_strategy_instance, funding_strategy_running
    
    return {
        "status": "healthy",
        "strategy_running": funding_strategy_running,
        "strategy_initialized": funding_strategy_instance is not None,
        "timestamp": datetime.now().isoformat()
    }

class FundingArbBacktestRequest(BaseModel):
    start_date: str
    end_date: str
    initial_capital: float = 10000.0

@app.post("/funding-arbitrage/backtest", response_model=Dict[str, Any])
def run_funding_arbitrage_backtest(request: FundingArbBacktestRequest):
    """
    资金费率套利策略回测API，遍历1h_funding_contracts_full.json所有合约，分别回测，单独展示每个合约结果。
    """
    try:
        # 读取可交易池合约
        contracts_file = os.path.join("cache", "1h_funding_contracts_full.json")
        if not os.path.exists(contracts_file):
            raise HTTPException(status_code=400, detail="未找到可交易池合约缓存文件")
        with open(contracts_file, "r", encoding="utf-8") as f:
            contracts_data = json.load(f)
        contracts = contracts_data.get("contracts", {})
        symbols = list(contracts.keys())
        if not symbols:
            raise HTTPException(status_code=400, detail="可交易池合约为空")
        # 依次回测每个symbol
        results = {}
        trades = {}
        equity_curve = {}
        for symbol in symbols:
            try:
                strategy = FundingRateArbitrageStrategy({
                    'paper_trading': True,
                    'auto_trade': False,
                })
                timeframe = "1h"
                engine = BacktestEngine(request.initial_capital)
                res = engine.run_backtest(
                    strategy,
                    symbol,
                    request.start_date,
                    request.end_date,
                    timeframe
                )
                results[symbol] = res.get('results', {})
                trades[symbol] = res.get('trades', [])
                equity_curve[symbol] = res.get('equity_curve', [])
            except Exception as e:
                results[symbol] = {"error": str(e)}
                trades[symbol] = []
                equity_curve[symbol] = []
        return {
            "results": results,
            "trades": trades,
            "equity_curve": equity_curve
        }
    except Exception as e:
        print(f"资金费率套利回测异常: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"回测失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT) 