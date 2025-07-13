import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import json
from typing import Dict, List, Any
from utils.binance_funding import BinanceFunding

# 配置
API_BASE_URL = "http://localhost:8000"

# 创建Dash应用
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "量化交易系统"

# 布局
app.layout = dbc.Container([
    # 标题栏
    dbc.Row([
        dbc.Col([
            html.H1("量化交易系统", className="text-center mb-4"),
            html.Hr()
        ])
    ]),
    
    # 导航标签
    dbc.Tabs([
        # 策略管理标签
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H3("策略管理"),
                    dbc.Button("刷新策略列表", id="refresh-strategies", color="primary", className="mb-3"),
                    html.Div(id="strategies-list")
                ], width=6),
                dbc.Col([
                    html.H3("创建新策略"),
                    dbc.Form([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("策略名称"),
                                dbc.Input(id="strategy-name", type="text", placeholder="输入策略名称")
                            ], width=6),
                            dbc.Col([
                                dbc.Label("策略描述"),
                                dbc.Textarea(id="strategy-description", placeholder="输入策略描述")
                            ], width=6)
                        ]),
                        # 策略类型选择
                        html.Div([
                            html.Label("策略类型:"),
                            dcc.Dropdown(
                                id='strategy-type-dropdown',
                                options=[
                                    {'label': '移动平均线交叉', 'value': 'ma_cross'},
                                    {'label': '布林带', 'value': 'bollinger_bands'},
                                    {'label': 'MACD', 'value': 'macd'},
                                    {'label': 'RSI', 'value': 'rsi'},
                                    {'label': '资金费率套利', 'value': 'funding_rate_arbitrage'}
                                ],
                                value='ma_cross'
                            )
                        ], style={'marginBottom': '10px'}),
                        # 资金费率套利策略参数
                        html.Div(id='funding-rate-params', style={'display': 'none'}, children=[
                            html.H5("资金费率套利策略参数"),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("资金费率阈值 (%):"),
                                    dcc.Input(id='funding-rate-threshold', type='number', value=0.5, step=0.1)
                                ], width=6),
                                dbc.Col([
                                    html.Label("最大持仓数量:"),
                                    dcc.Input(id='max-positions', type='number', value=10, min=1, max=50)
                                ], width=6)
                            ], style={'marginBottom': '10px'}),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("最小24小时成交量:"),
                                    dcc.Input(id='min-volume', type='number', value=1000000, step=100000)
                                ], width=6),
                                dbc.Col([
                                    html.Label("支持的交易所:"),
                                    dcc.Checklist(
                                        id='exchanges-checklist',
                                        options=[
                                            {'label': 'Binance', 'value': 'binance'},
                                            {'label': 'OKX', 'value': 'okx'},
                                            {'label': 'Bybit', 'value': 'bybit'}
                                        ],
                                        value=['binance', 'okx', 'bybit']
                                    )
                                ], width=6)
                            ], style={'marginBottom': '10px'})
                        ]),
                        # 资金费率套利策略控制
                        html.Div(id='funding-arbitrage-controls', style={'display': 'none'}, children=[
                            html.H5("资金费率套利控制"),
                            html.Button("运行策略", id='run-funding-arbitrage-btn', n_clicks=0),
                            html.Button("查看池子状态", id='view-pool-status-btn', n_clicks=0),
                            html.Div(id='pool-status-display')
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("参数配置"),
                                dcc.Textarea(id="strategy-parameters", placeholder='{"param1": value1, "param2": value2}')
                            ], width=12)
                        ]),
                        dbc.Button("创建策略", id="create-strategy", color="success", className="mt-3")
                    ])
                ], width=6)
            ])
        ], label="策略管理"),
        
        # 回测标签
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H3("回测配置"),
                    dbc.Form([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("选择策略"),
                                dcc.Dropdown(id="backtest-strategy", placeholder="选择要回测的策略")
                            ], width=6),
                            dbc.Col([
                                dbc.Label("交易对"),
                                dcc.Dropdown(id="backtest-symbol", placeholder="选择交易对")
                            ], width=6)
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("时间周期"),
                                dcc.Dropdown(
                                    id="backtest-timeframe",
                                    options=[
                                        {"label": "1分钟", "value": "1m"},
                                        {"label": "5分钟", "value": "5m"},
                                        {"label": "15分钟", "value": "15m"},
                                        {"label": "30分钟", "value": "30m"},
                                        {"label": "1小时", "value": "1h"},
                                        {"label": "4小时", "value": "4h"},
                                        {"label": "1天", "value": "1d"},
                                        {"label": "1周", "value": "1w"}
                                    ],
                                    value="1d"
                                )
                            ], width=6),
                            dbc.Col([
                                dbc.Label("开始日期"),
                                dcc.DatePickerSingle(id="backtest-start-date")
                            ], width=6)
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("结束日期"),
                                dcc.DatePickerSingle(id="backtest-end-date")
                            ], width=6),
                            dbc.Col([
                                dbc.Label("初始资金"),
                                dcc.Input(id="backtest-capital", type="number", value=10000)
                            ], width=6)
                        ]),
                        dbc.Button("开始回测", id="start-backtest", color="primary", className="mt-3")
                    ])
                ], width=4),
                dbc.Col([
                    html.H3("回测结果"),
                    html.Div(id="backtest-results"),
                    dcc.Graph(id="backtest-chart")
                ], width=8)
            ])
        ], label="回测"),
        
        # 交易标签
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H3("交易配置"),
                    dbc.Form([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("交易引擎名称"),
                                dbc.Input(id="engine-name", type="text", placeholder="输入引擎名称")
                            ], width=6),
                            dbc.Col([
                                dbc.Label("交易类型"),
                                dcc.Dropdown(
                                    id="trade-type",
                                    options=[
                                        {"label": "模拟交易", "value": "paper"},
                                        {"label": "实盘交易", "value": "live"}
                                    ],
                                    value="paper"
                                )
                            ], width=6)
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("选择策略"),
                                dcc.Dropdown(id="trading-strategy", placeholder="选择交易策略")
                            ], width=6),
                            dbc.Col([
                                dbc.Label("交易对"),
                                dcc.Dropdown(id="trading-symbol", placeholder="选择交易对")
                            ], width=6)
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("时间周期"),
                                dcc.Dropdown(
                                    id="trading-timeframe",
                                    options=[
                                        {"label": "1分钟", "value": "1m"},
                                        {"label": "5分钟", "value": "5m"},
                                        {"label": "15分钟", "value": "15m"},
                                        {"label": "30分钟", "value": "30m"},
                                        {"label": "1小时", "value": "1h"},
                                        {"label": "4小时", "value": "4h"},
                                        {"label": "1天", "value": "1d"},
                                        {"label": "1周", "value": "1w"}
                                    ],
                                    value="1d"
                                )
                            ], width=6),
                            dbc.Col([
                                dbc.Button("创建交易引擎", id="create-engine", color="success", className="mt-3"),
                                dbc.Button("运行策略", id="run-strategy", color="primary", className="mt-3 ml-2")
                            ], width=6)
                        ])
                    ])
                ], width=4),
                dbc.Col([
                    html.H3("交易状态"),
                    html.Div(id="trading-status"),
                    html.H4("持仓信息"),
                    html.Div(id="positions-info"),
                    html.H4("交易历史"),
                    html.Div(id="trade-history")
                ], width=8)
            ])
        ], label="交易"),
        
        # 数据标签
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H3("市场数据"),
                    dbc.Form([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("交易对"),
                                dcc.Dropdown(id="data-symbol", placeholder="选择交易对")
                            ], width=6),
                            dbc.Col([
                                dbc.Label("时间周期"),
                                dcc.Dropdown(
                                    id="data-timeframe",
                                    options=[
                                        {"label": "1分钟", "value": "1m"},
                                        {"label": "5分钟", "value": "5m"},
                                        {"label": "15分钟", "value": "15m"},
                                        {"label": "30分钟", "value": "30m"},
                                        {"label": "1小时", "value": "1h"},
                                        {"label": "4小时", "value": "4h"},
                                        {"label": "1天", "value": "1d"},
                                        {"label": "1周", "value": "1w"}
                                    ],
                                    value="1d"
                                )
                            ], width=6)
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Button("更新数据", id="update-data", color="primary", className="mt-3"),
                                dbc.Button("获取最新价格", id="get-price", color="info", className="mt-3 ml-2")
                            ], width=6),
                            dbc.Col([
                                html.H3("价格信息"),
                                html.Div(id="price-info")
                            ], width=6)
                        ])
                    ])
                ], width=4),
                dbc.Col([
                    html.H3("价格图表"),
                    dcc.Graph(id="price-chart"),
                    html.Div(id="price-chart-info")
                ], width=8)
            ])
        ], label="市场数据")
    ]),
    
    # 通知区域
    dbc.Toast(id="notification", header="通知", is_open=False, dismissable=True, duration=4000)
    
], fluid=True)

# 回调函数
@app.callback(
    [Output("strategies-list", "children"),
     Output("strategy-type-dropdown", "options")],
    [Input("refresh-strategies", "n_clicks")]
)
def load_strategies(n_clicks):
    """加载策略列表和可用策略类型"""
    try:
        # 获取策略列表
        response = requests.get(f"{API_BASE_URL}/strategies")
        strategies = response.json()
        
        # 获取可用策略类型
        response = requests.get(f"{API_BASE_URL}/strategies/available")
        available_strategies = response.json()
        
        # 构建策略列表显示
        strategies_cards = []
        for strategy in strategies:
            card = dbc.Card([
                dbc.CardHeader(strategy['name']),
                dbc.CardBody([
                    html.P(f"类型: {strategy['strategy_type']}"),
                    html.P(f"描述: {strategy['description'] or '无'}"),
                    html.P(f"状态: {'激活' if strategy['is_active'] else '停用'}"),
                    dbc.Button("删除", id=f"delete-strategy-{strategy['id']}", 
                              color="danger", size="sm", className="mt-2")
                ])
            ], className="mb-3")
            strategies_cards.append(card)
        
        # 构建策略类型选项
        strategy_options = [
            {"label": s['name'], "value": s['type']} 
            for s in available_strategies['strategies']
        ]
        
        return strategies_cards, strategy_options
        
    except Exception as e:
        return [html.P(f"加载策略失败: {str(e)}")], []

@app.callback(
    Output("notification", "children"),
    Output("notification", "is_open"),
    [Input("create-strategy", "n_clicks")],
    [State("strategy-name", "value"),
     State("strategy-description", "value"),
     State("strategy-type-dropdown", "value"),
     State("strategy-parameters", "value")]
)
def create_strategy(n_clicks, name, description, strategy_type, parameters):
    """创建新策略"""
    if not n_clicks:
        return "", False
    
    try:
        # 解析参数
        params = {}
        if parameters:
            try:
                params = json.loads(parameters)
            except:
                return "参数格式错误，请使用JSON格式", True
        
        # 创建策略
        data = {
            "name": name,
            "description": description,
            "strategy_type": strategy_type,
            "parameters": params
        }
        
        response = requests.post(f"{API_BASE_URL}/strategies", json=data)
        
        if response.status_code == 200:
            return "策略创建成功", True
        else:
            return f"创建策略失败: {response.json()['detail']}", True
            
    except Exception as e:
        return f"创建策略失败: {str(e)}", True

@app.callback(
    [Output("backtest-results", "children"),
     Output("backtest-chart", "figure")],
    [Input("start-backtest", "n_clicks")],
    [State("backtest-strategy", "value"),
     State("backtest-symbol", "value"),
     State("backtest-timeframe", "value"),
     State("backtest-start-date", "date"),
     State("backtest-end-date", "date"),
     State("backtest-capital", "value")]
)
def run_backtest(n_clicks, strategy_id, symbol, timeframe, start_date, end_date, capital):
    """运行回测"""
    if not n_clicks or not all([strategy_id, symbol, start_date, end_date]):
        return "", {}
    
    try:
        # 运行回测
        data = {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": capital
        }
        
        response = requests.post(f"{API_BASE_URL}/backtest", json=data)
        
        if response.status_code == 200:
            results = response.json()
            
            # 显示回测结果
            results_html = [
                html.H4("回测摘要"),
                html.P(f"总收益率: {results['results']['total_return']:.2%}"),
                html.P(f"最大回撤: {results['results']['max_drawdown']:.2%}"),
                html.P(f"夏普比率: {results['results']['sharpe_ratio']:.2f}"),
                html.P(f"胜率: {results['results']['win_rate']:.2%}"),
                html.P(f"总交易次数: {results['results']['total_trades']}")
            ]
            
            # 创建权益曲线图表
            equity_data = results.get('equity_curve', [])
            if equity_data:
                df = pd.DataFrame(equity_data)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df['timestamp'],
                    y=df['equity'],
                    mode='lines',
                    name='权益曲线'
                ))
                fig.update_layout(
                    title="回测权益曲线",
                    xaxis_title="时间",
                    yaxis_title="权益"
                )
            else:
                fig = {}
            
            return results_html, fig
        else:
            return [html.P(f"回测失败: {response.json()['detail']}")], {}
            
    except Exception as e:
        return [html.P(f"回测失败: {str(e)}")], {}

@app.callback(
    [Output("trading-status", "children"),
     Output("positions-info", "children"),
     Output("trade-history", "children")],
    [Input("create-engine", "n_clicks"),
     Input("run-strategy", "n_clicks")],
    [State("engine-name", "value"),
     State("trade-type", "value"),
     State("trading-strategy", "value"),
     State("trading-symbol", "value"),
     State("trading-timeframe", "value")]
)
def trading_operations(create_clicks, run_clicks, engine_name, trade_type, 
                      strategy_type, symbol, timeframe):
    """交易操作"""
    ctx = callback_context
    if not ctx.triggered:
        return "", "", ""
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    try:
        if button_id == "create-engine" and engine_name:
            # 创建交易引擎
            data = {
                "engine_name": engine_name,
                "strategy_type": strategy_type,
                "symbol": symbol,
                "timeframe": timeframe,
                "trade_type": trade_type
            }
            
            response = requests.post(f"{API_BASE_URL}/trading/engine", json=data)
            
            if response.status_code == 200:
                # 获取账户信息
                account_response = requests.get(f"{API_BASE_URL}/trading/engine/{engine_name}/account")
                if account_response.status_code == 200:
                    account = account_response.json()
                    status_html = [
                        html.H4("交易引擎状态"),
                        html.P(f"引擎名称: {engine_name}"),
                        html.P(f"交易类型: {trade_type}"),
                        html.P(f"账户余额: {account.get('balance', 0):.2f}"),
                        html.P(f"持仓数量: {account.get('positions_count', 0)}")
                    ]
                else:
                    status_html = [html.P("交易引擎创建成功")]
                
                # 获取持仓信息
                positions_response = requests.get(f"{API_BASE_URL}/trading/engine/{engine_name}/positions")
                if positions_response.status_code == 200:
                    positions = positions_response.json()
                    if positions:
                        positions_html = [
                            html.Table([
                                html.Thead([
                                    html.Tr([
                                        html.Th("交易对"),
                                        html.Th("数量"),
                                        html.Th("入场价格"),
                                        html.Th("当前价格"),
                                        html.Th("未实现盈亏")
                                    ])
                                ]),
                                html.Tbody([
                                    html.Tr([
                                        html.Td(pos['symbol']),
                                        html.Td(f"{pos['quantity']:.4f}"),
                                        html.Td(f"{pos['entry_price']:.2f}"),
                                        html.Td(f"{pos['current_price']:.2f}"),
                                        html.Td(f"{pos['unrealized_pnl']:.2f}")
                                    ]) for pos in positions
                                ])
                            ])
                        ]
                    else:
                        positions_html = [html.P("暂无持仓")]
                else:
                    positions_html = [html.P("获取持仓信息失败")]
                
                # 获取交易历史
                trades_response = requests.get(f"{API_BASE_URL}/trading/trades", 
                                            params={"limit": 10})
                if trades_response.status_code == 200:
                    trades = trades_response.json()
                    if trades:
                        trades_html = [
                            html.Table([
                                html.Thead([
                                    html.Tr([
                                        html.Th("时间"),
                                        html.Th("交易对"),
                                        html.Th("方向"),
                                        html.Th("数量"),
                                        html.Th("价格")
                                    ])
                                ]),
                                html.Tbody([
                                    html.Tr([
                                        html.Td(trade['timestamp'][:19]),
                                        html.Td(trade['symbol']),
                                        html.Td(trade['side']),
                                        html.Td(f"{trade['quantity']:.4f}"),
                                        html.Td(f"{trade['price']:.2f}")
                                    ]) for trade in trades
                                ])
                            ])
                        ]
                    else:
                        trades_html = [html.P("暂无交易记录")]
                else:
                    trades_html = [html.P("获取交易历史失败")]
                
                return status_html, positions_html, trades_html
            else:
                return [html.P(f"创建交易引擎失败: {response.json()['detail']}")], "", ""
        
        elif button_id == "run-strategy" and engine_name:
            # 运行策略
            data = {
                "engine_name": engine_name,
                "strategy_type": strategy_type,
                "symbol": symbol,
                "timeframe": timeframe,
                "trade_type": trade_type
            }
            
            response = requests.post(f"{API_BASE_URL}/trading/run", json=data)
            
            if response.status_code == 200:
                return [html.P("策略运行成功")], "", ""
            else:
                return [html.P(f"运行策略失败: {response.json()['detail']}")], "", ""
        
        return "", "", ""
        
    except Exception as e:
        return [html.P(f"操作失败: {str(e)}")], "", ""

@app.callback(
    [Output("price-chart", "figure"),
     Output("price-chart-info", "children")],
    [Input("update-data", "n_clicks"),
     Input("get-price", "n_clicks")],
    [State("data-symbol", "value"),
     State("data-timeframe", "value")]
)
def market_data_operations(update_clicks, get_clicks, symbol, timeframe):
    """市场数据操作"""
    ctx = callback_context
    if not ctx.triggered or not symbol:
        return {}, ""
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    try:
        if button_id == "update-data":
            # 更新市场数据
            response = requests.post(f"{API_BASE_URL}/data/{symbol}/update", 
                                   params={"timeframe": timeframe})
            
            if response.status_code == 200:
                # 这里可以添加获取历史数据并绘制图表的逻辑
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=[],
                    y=[],
                    mode='lines',
                    name=f'{symbol} 价格'
                ))
                fig.update_layout(
                    title=f"{symbol} 价格图表",
                    xaxis_title="时间",
                    yaxis_title="价格"
                )
                
                return fig, html.P("数据更新成功")
            else:
                return {}, html.P(f"更新数据失败: {response.json()['detail']}")
        
        elif button_id == "get-price":
            # 获取最新价格
            response = requests.get(f"{API_BASE_URL}/data/{symbol}/price")
            
            if response.status_code == 200:
                price_data = response.json()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=[price_data['timestamp']],
                    y=[price_data['price']],
                    mode='markers',
                    name=f'{symbol} 最新价格'
                ))
                fig.update_layout(
                    title=f"{symbol} 最新价格",
                    xaxis_title="时间",
                    yaxis_title="价格"
                )
                
                return fig, html.P(f"最新价格: {price_data['price']:.2f}")
            else:
                return {}, html.P(f"获取价格失败: {response.json()['detail']}")
        
        return {}, ""
        
    except Exception as e:
        return {}, html.P(f"操作失败: {str(e)}")

# 初始化回调
@app.callback(
    [Output("backtest-strategy", "options"),
     Output("trading-strategy", "options"),
     Output("backtest-symbol", "options"),
     Output("trading-symbol", "options"),
     Output("data-symbol", "options")],
    [Input("refresh-strategies", "n_clicks")]
)
def initialize_options(n_clicks):
    """初始化下拉选项"""
    try:
        # 获取策略选项
        strategies_response = requests.get(f"{API_BASE_URL}/strategies")
        if strategies_response.status_code == 200:
            strategies = strategies_response.json()
            strategy_options = [
                {"label": s['name'], "value": s['id']} 
                for s in strategies
            ]
        else:
            strategy_options = []
        
        # 获取交易对选项
        symbols_response = requests.get(f"{API_BASE_URL}/data/symbols")
        if symbols_response.status_code == 200:
            symbols = symbols_response.json()
            symbol_options = [
                {"label": symbol, "value": symbol} 
                for symbol in symbols
            ]
        else:
            symbol_options = []
        
        return strategy_options, strategy_options, symbol_options, symbol_options, symbol_options
        
    except Exception as e:
        return [], [], [], [], []

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050) 