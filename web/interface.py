import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import requests
import json
import traceback
from datetime import datetime, timezone, timedelta
import os # Added for file operations
import plotly.graph_objects as go
from plotly.subplots import make_subplots

API_BASE_URL = "http://localhost:8000"

app = dash.Dash(__name__, external_stylesheets=[
    dbc.themes.BOOTSTRAP,
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"
])
app.title = "加密货币资金费率监控系统"

def load_cached_data(interval="1h"):
    """直接加载本地缓存数据，优先读取最新资金费率缓存"""
    try:
        print(f"📋 加载本地缓存数据，结算周期: {interval}")
        
        # 从统一缓存文件读取监控合约数据
        pool_contracts = []
        try:
            with open("cache/all_funding_contracts_full.json", 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
                # 直接从缓存中获取监控合约池
                monitor_pool = cache_data.get('monitor_pool', {})
                
                # 如果没有监控合约池，直接使用空数据
                if not monitor_pool:
                    print("⚠️ 监控合约池为空，显示空数据")
                    monitor_pool = {}
                
                # 转换为列表格式
                for symbol, info in monitor_pool.items():
                    try:
                        pool_contracts.append({
                            "symbol": symbol,
                            "exchange": info.get("exchange", "binance"),
                            "funding_rate": float(info.get("current_funding_rate", 0)),
                            "funding_time": info.get("next_funding_time", ""),
                            "volume_24h": info.get("volume_24h", 0),
                            "mark_price": info.get("mark_price", 0)
                        })
                    except (ValueError, TypeError) as e:
                        print(f"⚠️ 处理监控合约 {symbol} 时出错: {e}")
                        continue
                
                print(f"📋 加载了 {len(pool_contracts)} 个监控合约")
        except FileNotFoundError:
            print("📋 统一缓存文件不存在")
        except Exception as e:
            print(f"⚠️ 读取统一缓存失败: {e}")

        # 从合并后的全量缓存文件中读取数据
        candidates = {}
        update_time = "未知"
        
        try:
            cache_file = "cache/all_funding_contracts_full.json"
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # 优先使用latest_rates中的数据（如果存在）
                latest_rates = cache_data.get('latest_rates', {})
                if latest_rates:
                    print(f"📋 使用合并缓存中的最新资金费率数据，共 {len(latest_rates)} 个合约")
                    
                    # 筛选指定结算周期的合约
                    for symbol, info in latest_rates.items():
                        funding_interval = info.get('funding_interval')
                        if funding_interval == interval:
                            candidates[symbol] = info
                        # 删除详细的筛选日志
                    
                    # 使用最新缓存时间
                    cache_time = cache_data.get('cache_time', '')
                    if cache_time:
                        try:
                            # 解析缓存时间（缓存文件中的时间是本地时间，不需要时区转换）
                            from datetime import datetime
                            if 'T' in cache_time:
                                # ISO格式时间，直接解析为本地时间
                                dt = datetime.fromisoformat(cache_time)
                            else:
                                # 其他格式，尝试解析
                                dt = datetime.strptime(cache_time, '%Y-%m-%d %H:%M:%S')
                            
                            # 直接使用本地时间，不需要时区转换
                            update_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except Exception as e:
                            print(f"⚠️ 解析缓存时间失败: {e}")
                            update_time = cache_time
                    
                    print(f"📋 筛选出 {len(candidates)} 个{interval}结算周期合约")
                
                # 如果没有找到合约，则从contracts_by_interval中获取
                if not candidates:
                    print(f"⚠️ 最新资金费率数据中没有找到{interval}结算周期合约，使用基础合约数据")
                    contracts_by_interval = cache_data.get('contracts_by_interval', {})
                    candidates = contracts_by_interval.get(interval, {})
                    
                    # 获取缓存时间
                    cache_time = cache_data.get('cache_time', '')
                    if cache_time:
                        try:
                            # 解析缓存时间（缓存文件中的时间是本地时间，不需要时区转换）
                            from datetime import datetime
                            if 'T' in cache_time:
                                # ISO格式时间，直接解析为本地时间
                                dt = datetime.fromisoformat(cache_time)
                            else:
                                # 其他格式，尝试解析
                                dt = datetime.strptime(cache_time, '%Y-%m-%d %H:%M:%S')
                            
                            # 直接使用本地时间，不需要时区转换
                            update_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except Exception as e:
                            print(f"⚠️ 解析缓存时间失败: {e}")
                            update_time = cache_time
                    
                    print(f"📋 从基础合约数据加载了 {len(candidates)} 个{interval}结算周期合约")
            else:
                print(f"📋 全量缓存文件不存在: {cache_file}")
        except Exception as e:
            print(f"⚠️ 读取全量缓存失败: {e}")
        
        result = build_tables(pool_contracts, candidates, interval, update_time)
        print("✅ 本地缓存数据加载完成")
        return result, update_time
        
    except Exception as e:
        error_msg = f"加载本地缓存数据失败: {str(e)}"
        print(f"❌ 加载本地缓存数据异常: {error_msg}")
        print(f"❌ 异常详情: {traceback.format_exc()}")
        # 返回错误信息作为表格内容，保持返回结构一致
        error_table = html.P(f"❌ {error_msg}", className="text-danger")
        return (error_table, error_table), "加载失败"

app.layout = dbc.Container([
    # 页面初始化触发器
    dcc.Store(id="page-store", data="init"),
    dbc.Row([
        dbc.Col([
            html.H1("加密货币资金费率监控系统", className="text-center mb-4"),
            html.Hr()
        ])
    ]),
    dbc.Tabs([
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H3("合约监控总览"),
                    html.P("查看所有1小时结算合约（备选池）和当前监控合约的详细数据。", className="text-muted"),
                    html.Hr(),
                    dbc.Button("🔄 刷新合约数据", id="refresh-candidates-btn", color="info", className="me-2 mb-2"),
                    dbc.Button("📊 获取最新资金费率", id="get-latest-rates-btn", color="success", className="me-2 mb-2"),
                    dbc.Button("♻️ 刷新备选池", id="refresh-candidates-pool-btn", color="primary", className="mb-2"),
                    # 资金费率更新时间显示
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-clock me-2"),
                                html.Span("资金费率更新时间: ", className="text-muted"),
                                html.Span(id="funding-rate-update-time", className="fw-bold text-info")
                            ], className="mt-2 mb-3 p-2 bg-light rounded")
                        ], width=12)
                    ]),
                    html.H4("当前监控合约"),
                    html.Div(id="pool-contracts-table", className="mb-4"),
                    html.H4("备选合约"),
                    # 结算周期筛选
                    dbc.Row([
                        dbc.Col([
                            html.Label("结算周期:", className="me-2"),
                            dcc.Dropdown(
                                id="interval-filter",
                                options=[
                                    {"label": "1小时", "value": "1h"},
                                    {"label": "2小时", "value": "2h"},
                                    {"label": "4小时", "value": "4h"},
                                    {"label": "8小时", "value": "8h"}
                                ],
                                value="1h",  # 默认选择1小时
                                style={"width": "150px"}
                            )
                        ], width=3),
                        dbc.Col([
                            html.Span(id="contract-count-display", className="text-muted")
                        ], width=9)
                    ], className="mb-3"),
                    html.Div(id="candidates-table", className="mb-4"),
                    # 弹窗
                    dbc.Modal([
                        dbc.ModalHeader(dbc.ModalTitle(id="modal-title")),
                        dbc.ModalBody([
                            dcc.Graph(id="history-rate-graph"),
                            html.Hr(),
                            html.H5("历史资金费率与价格表格数据"),
                            html.Div(id="history-rate-table")
                        ]),
                    ], id="history-rate-modal", is_open=False, size="xl"),
                ], width=12)
            ])
        ], label="合约监控", tab_id="candidates-overview"),
        
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H3("历史入池合约"),
                    html.P("查看所有历史入池合约的列表和在池期间的记录历史资金费率。", className="text-muted"),
                    html.Hr(),
                    dbc.Button("🔄 刷新历史数据", id="refresh-history-btn", color="info", className="me-2 mb-2"),
                    # 自动刷新组件
                    dcc.Interval(
                        id="history-interval",
                        interval=30*1000,  # 30秒刷新一次
                        n_intervals=0
                    ),
                    # 历史数据统计
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-chart-bar me-2"),
                                html.Span("历史合约总数: ", className="text-muted"),
                                html.Span(id="history-contracts-count", className="fw-bold text-primary")
                            ], className="mt-2 mb-3 p-2 bg-light rounded")
                        ], width=6),
                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-clock me-2"),
                                html.Span("最后更新时间: ", className="text-muted"),
                                html.Span(id="history-last-update", className="fw-bold text-info")
                            ], className="mt-2 mb-3 p-2 bg-light rounded")
                        ], width=6)
                    ]),
                    # 历史合约列表
                    html.H4("历史入池合约列表"),
                    html.Div(id="history-contracts-table", className="mb-4"),
                    # 历史详情弹窗
                    dbc.Modal([
                        dbc.ModalHeader(dbc.ModalTitle(id="history-modal-title")),
                        dbc.ModalBody([
                            html.Div(id="history-contract-stats", className="mb-3"),
                            dcc.Graph(id="history-contract-graph"),
                            html.Hr(),
                            html.H5("历史资金费率详细数据"),
                            html.Div(id="history-contract-table")
                        ]),
                    ], id="history-contract-modal", is_open=False, size="xl"),
                ], width=12)
            ])
        ], label="历史入池合约", tab_id="history-contracts"),
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H3("合约归档数据"),
                    html.P("查看合约入池出池的归档数据，分析每次入池出池的特征。", className="text-muted"),
                    html.Hr(),
                    dbc.Button("🔄 刷新归档数据", id="refresh-archive-btn", color="info", className="me-2 mb-2"),
                    dbc.Button("🧹 清理旧归档", id="cleanup-archive-btn", color="warning", className="mb-2"),
                    # 归档统计
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-archive me-2"),
                                html.Span("总会话数: ", className="text-muted"),
                                html.Span(id="total-sessions-count", className="fw-bold text-primary")
                            ], className="mt-2 mb-3 p-2 bg-light rounded")
                        ], width=4),
                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-chart-line me-2"),
                                html.Span("总合约数: ", className="text-muted"),
                                html.Span(id="total-contracts-count", className="fw-bold text-success")
                            ], className="mt-2 mb-3 p-2 bg-light rounded")
                        ], width=4),
                        dbc.Col([
                            html.Div([
                                html.I(className="fas fa-clock me-2"),
                                html.Span("平均持续时间: ", className="text-muted"),
                                html.Span(id="avg-duration", className="fw-bold text-info")
                            ], className="mt-2 mb-3 p-2 bg-light rounded")
                        ], width=4)
                    ]),
                    # 归档合约列表
                    html.H4("归档合约列表"),
                    html.Div(id="archive-contracts-table", className="mb-4"),
                    # 归档详情弹窗
                    dbc.Modal([
                        dbc.ModalHeader(dbc.ModalTitle(id="archive-modal-title")),
                        dbc.ModalBody([
                            html.Div(id="archive-session-stats", className="mb-3"),
                            dcc.Graph(id="archive-session-graph"),
                            html.Hr(),
                            html.H5("会话详细数据"),
                            html.Div(id="archive-session-table")
                        ]),
                    ], id="archive-session-modal", is_open=False, size="xl"),
                ], width=12)
            ])
        ], label="合约归档", tab_id="archive-tab"),
    ]),
    dbc.Toast(id="notification", header="通知", is_open=False, dismissable=True, duration=4000)
], fluid=True)

# 这个回调函数现在只处理其他通知，刷新备选池由专门的回调函数处理
@app.callback(
    Output("notification", "children"),
    Output("notification", "is_open"),
    [
        Input("refresh-candidates-pool-btn", "n_clicks"),
    ]
)

def unified_notification_callback(refresh_pool_clicks):
    # 这个回调函数现在由专门的refresh_candidates_pool函数处理
    return "", False

# 页面初始化回调 - 使用dcc.Store来触发初始化
@app.callback(
    Output("pool-contracts-table", "children"),
    Output("candidates-table", "children"),
    Output("contract-count-display", "children"),
    Output("funding-rate-update-time", "children"),
    Input("page-store", "data")
)
def initialize_page(data):
    """页面初始化时只加载缓存数据，不主动更新"""

    result, update_time = load_cached_data("1h")  # 默认加载1小时结算周期
    pool_table, candidates_table = result
    count_text = "当前显示: 1h结算周期合约"
    return pool_table, candidates_table, count_text, update_time

# 结算周期筛选回调
@app.callback(
    Output("pool-contracts-table", "children", allow_duplicate=True),
    Output("candidates-table", "children", allow_duplicate=True),
    Output("contract-count-display", "children", allow_duplicate=True),
    Output("funding-rate-update-time", "children", allow_duplicate=True),
    Input("interval-filter", "value"),
    prevent_initial_call=True
)
def filter_by_interval(interval):
    """根据结算周期筛选合约数据"""
    result, update_time = load_cached_data(interval)
    pool_table, candidates_table = result
    count_text = f"当前显示: {interval}结算周期合约"
    return pool_table, candidates_table, count_text, update_time

# 刷新合约数据回调 - 只在用户点击刷新按钮时触发
@app.callback(
    Output("pool-contracts-table", "children", allow_duplicate=True),
    Output("candidates-table", "children", allow_duplicate=True),
    Output("contract-count-display", "children", allow_duplicate=True),
    Output("funding-rate-update-time", "children", allow_duplicate=True),
    Input("refresh-candidates-btn", "n_clicks"),
    State("interval-filter", "value"),  # 获取当前选中的结算周期
    prevent_initial_call=True
)
def update_candidates_data(refresh_clicks, current_interval):
    """刷新时重新加载本地缓存数据"""
    try:
        # 使用当前选中的结算周期，如果没有选中则默认使用1h
        interval = current_interval if current_interval else "1h"
        # 直接调用load_cached_data函数，它会读取本地缓存
        result, update_time = load_cached_data(interval)
        pool_table, candidates_table = result
        count_text = f"当前显示: {interval}结算周期合约"
        
        return pool_table, candidates_table, count_text, update_time
        
    except Exception as e:
        error_msg = f"刷新本地缓存数据失败: {str(e)}"
        print(f"❌ 刷新本地缓存数据异常: {error_msg}")
        print(f"❌ 异常详情: {traceback.format_exc()}")
        error_table = html.P(f"❌ {error_msg}", className="text-danger")
        return error_table, error_table, "刷新失败", "刷新失败"
        
def build_tables(pool_contracts, candidates, interval="1h", update_time="未知"):
    """构建表格组件"""
    try:

        
        def format_time(timestamp):
            """格式化时间戳为北京时间"""
            try:
                if not timestamp:
                    return "未知"
                
                # 如果是字符串，尝试转换为数字
                if isinstance(timestamp, str):
                    if timestamp.isdigit():
                        timestamp = int(timestamp)
                    else:
                        return timestamp  # 如果已经是格式化的时间字符串，直接返回
                
                # 如果是数字时间戳
                if isinstance(timestamp, (int, float)):
                    # 判断是秒还是毫秒时间戳
                    if timestamp > 1e10:  # 毫秒时间戳
                        timestamp = timestamp / 1000
                    
                    # 转换为北京时间（UTC+8）
                    utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    beijing_time = utc_time + timedelta(hours=8)
                    
                    # 格式化为常见时间格式
                    return beijing_time.strftime('%Y-%m-%d %H:%M:%S')
                
                return str(timestamp)
            except Exception as e:
                print(f"⚠️ 时间格式化失败 {timestamp}: {e}")
                return str(timestamp)
        
        # 构建当前监控合约表格
        if pool_contracts and len(pool_contracts) > 0:
            pool_table_header = [html.Thead(html.Tr([
                html.Th("合约名称"), 
                html.Th("资金费率结算周期"), 
                html.Th("当前资金费率"), 
                html.Th("上一次结算时间"),
                html.Th("24小时成交量"),
                html.Th("标记价格"),
                html.Th("缓存时间"),
                html.Th("操作")
            ]))]
            pool_table_rows = []
            for contract in pool_contracts:
                try:
                    # 兼容不同的字段名
                    funding_rate = contract.get("funding_rate") or contract.get("current_funding_rate", 0)
                    funding_time = contract.get("funding_time") or contract.get("next_funding_time", "")
                    funding_interval = contract.get("funding_interval", "1h")  # 获取结算周期
                    volume_24h = contract.get("volume_24h", 0)
                    mark_price = contract.get("mark_price", 0)
                    
                    # 格式化时间
                    formatted_time = format_time(funding_time)
                    
                    # 格式化成交量和价格
                    formatted_volume = f"{float(volume_24h):,.0f}" if volume_24h else "未知"
                    formatted_price = f"${float(mark_price):.4f}" if mark_price else "未知"
                    
                    # 格式化结算周期显示
                    interval_display = funding_interval
                    if funding_interval == "1h":
                        interval_display = "1小时"
                    elif funding_interval == "2h":
                        interval_display = "2小时"
                    elif funding_interval == "4h":
                        interval_display = "4小时"
                    elif funding_interval == "8h":
                        interval_display = "8小时"
                    
                    pool_table_rows.append(
                        html.Tr([
                            html.Td(contract.get("symbol", "")),
                            html.Td(interval_display),
                            html.Td(f"{float(funding_rate)*100:.4f}%"),
                            html.Td(formatted_time),
                            html.Td(formatted_volume),
                            html.Td(formatted_price),
                            html.Td(update_time),  # 使用全局的update_time
                            html.Td(dbc.Button("查看历史", id={"type": "view-monitor-history", "index": contract.get("symbol", "")}, size="sm", color="info", className="history-btn", title=f"查看{contract.get('symbol', '')}的监控历史数据")),
                        ])
                    )
                except Exception as e:
                    print(f"⚠️ 处理监控合约 {contract.get('symbol', '')} 时出错: {e}")
                    continue
            pool_table = dbc.Table(pool_table_header + [html.Tbody(pool_table_rows)], bordered=True, hover=True)
        else:
            pool_table = html.P("暂无监控合约数据")

        # 构建所有备选合约表格
        if candidates and len(candidates) > 0:
            
            # 创建可排序的资金费率列标题
            funding_rate_header = html.Th([
                html.Span("当前资金费率", className="me-2"),
                html.Div([
                    dbc.Button("↑", id="sort-funding-rate-asc", size="sm", color="outline-primary", className="me-1", title="按资金费率升序排列"),
                    dbc.Button("↓", id="sort-funding-rate-desc", size="sm", color="outline-primary", title="按资金费率降序排列")
                ], className="d-inline")
            ])
            
            candidates_table_header = [html.Thead(html.Tr([
                html.Th("合约名称"), 
                html.Th("资金费率结算周期"), 
                funding_rate_header, 
                html.Th("上一次结算时间"),
                html.Th("24小时成交量"),
                html.Th("标记价格"),
                html.Th("缓存时间"),
                html.Th("操作")
            ]))]
            
            candidates_table_rows = []
            for symbol, info in candidates.items():
                try:
                    # 兼容不同的字段名
                    funding_rate = info.get("funding_rate") or info.get("current_funding_rate", 0)
                    funding_time = info.get("funding_time") or info.get("next_funding_time", "")
                    funding_interval = info.get("funding_interval", "1h")  # 获取结算周期
                    volume_24h = info.get("volume_24h", 0)
                    mark_price = info.get("mark_price", 0)
                    
                    # 格式化时间
                    formatted_time = format_time(funding_time)
                    
                    # 格式化成交量和价格
                    formatted_volume = f"{float(volume_24h):,.0f}" if volume_24h else "未知"
                    formatted_price = f"${float(mark_price):.4f}" if mark_price else "未知"
                    
                    # 格式化结算周期显示
                    interval_display = funding_interval
                    if funding_interval == "1h":
                        interval_display = "1小时"
                    elif funding_interval == "2h":
                        interval_display = "2小时"
                    elif funding_interval == "4h":
                        interval_display = "4小时"
                    elif funding_interval == "8h":
                        interval_display = "8小时"
                    
                    candidates_table_rows.append(
                        html.Tr([
                            html.Td(symbol),
                            html.Td(interval_display),
                            html.Td(f"{float(funding_rate)*100:.4f}%"),
                            html.Td(formatted_time),
                            html.Td(formatted_volume),
                            html.Td(formatted_price),
                            html.Td(update_time),
                            html.Td(dbc.Button("查看历史", id={"type": "view-history", "index": symbol}, size="sm", color="info", className="history-btn", title=f"查看{symbol}的历史资金费率")),
                        ])
                    )
                except Exception as e:
                    print(f"⚠️ 处理合约 {symbol} 时出错: {e}")
                    # 跳过有问题的合约
                    continue
                    
            candidates_table = dbc.Table(candidates_table_header + [html.Tbody(candidates_table_rows)], bordered=True, hover=True)
            print(f"✅ 备选合约表格构建完成，共 {len(candidates_table_rows)} 行")
        else:
            candidates_table = html.P("暂无备选合约数据")
            print("⚠️ 没有备选合约数据")

        print(f"✅ 成功构建表格，监控合约: {len(pool_contracts)}, 备选合约: {len(candidates)}")
        return pool_table, candidates_table
        
    except Exception as e:
        error_msg = f"构建表格失败: {str(e)}"
        print(f"❌ 构建表格异常: {error_msg}")
        # 返回错误信息作为HTML组件，保持返回结构一致
        error_table = html.P(f"❌ {error_msg}", className="text-danger")
        return error_table, error_table

# 查看历史资金费率回调
@app.callback(
    Output("history-rate-modal", "is_open"),
    Output("modal-title", "children"),
    Output("history-rate-graph", "figure"),
    Output("history-rate-table", "children"),
    [
        Input({"type": "view-history", "index": dash.ALL}, "n_clicks"),
        Input({"type": "view-monitor-history", "index": dash.ALL}, "n_clicks")
    ],
    [State("history-rate-modal", "is_open")],
    prevent_initial_call=True
)
def open_history_modal(n_clicks_history, n_clicks_monitor_history, is_open):
    ctx = callback_context
    
    if not ctx.triggered:
        return False, "", {}, ""

    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # 检查是否真的是历史按钮被点击
    is_history_click = '"type":"view-history"' in triggered_id and '"index":' in triggered_id
    is_monitor_history_click = '"type":"view-monitor-history"' in triggered_id and '"index":' in triggered_id
    
    if not (is_history_click or is_monitor_history_click):
        return False, "", {}, ""
    
    # 检查是否有实际的点击事件
    all_clicks = n_clicks_history + n_clicks_monitor_history
    if not any(all_clicks):
        return False, "", {}, ""
    
    # 找到被点击的按钮索引
    clicked_index = None
    button_type = None
    
    # 检查普通历史按钮
    for i, clicks in enumerate(n_clicks_history):
        if clicks and clicks > 0:
            clicked_index = i
            button_type = "view-history"
            break
    
    # 检查监控历史按钮
    if clicked_index is None:
        for i, clicks in enumerate(n_clicks_monitor_history):
            if clicks and clicks > 0:
                clicked_index = i
                button_type = "view-monitor-history"
                break
    
    if clicked_index is None:
        return False, "", {}, ""
    
    try:
        # 解析symbol - 支持两种ID格式
        parsed_id = json.loads(triggered_id)
        symbol = parsed_id.get('index') or parsed_id.get('symbol')
        if not symbol:
            return False, "", {}, ""
        
        # 根据按钮类型调用不同的API
        if button_type == "view-monitor-history":
            # 调用监控合约历史数据API
            resp = requests.get(f"{API_BASE_URL}/funding_monitor/history/{symbol}?days=7")
            if resp.status_code != 200:
                error_msg = f"无法获取监控历史数据: {resp.text}"
                print(f"❌ {error_msg}")
                return not is_open, f"{symbol} 监控历史数据", {}, error_msg

            data = resp.json()
            if data.get("status") != "success":
                error_msg = data.get("message", "获取监控历史数据失败")
                print(f"❌ {error_msg}")
                return not is_open, f"{symbol} 监控历史数据", {}, error_msg

            history_data = data.get("history", [])
            if not history_data:
                return not is_open, f"{symbol} 监控历史数据", {}, "暂无监控历史数据"
            
            # 处理监控历史数据
            dates = []
            funding_rates = []
            mark_prices = []
            index_prices = []
            
            for record in history_data:
                try:
                    # 解析时间戳
                    timestamp = record.get('timestamp', '')
                    if timestamp:
                        if 'T' in timestamp:
                            dt = datetime.fromisoformat(timestamp)
                        else:
                            dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                        dates.append(dt.strftime('%Y-%m-%d %H:%M'))
                    else:
                        dates.append('未知时间')
                    
                    funding_rates.append(float(record.get('funding_rate', 0)) * 100)  # 转换为百分比
                    mark_prices.append(float(record.get('mark_price', 0)))
                    index_prices.append(float(record.get('index_price', 0)))
                except Exception as e:
                    print(f"⚠️ 处理历史记录时出错: {e}")
                    continue
            
            # 创建图表
            fig = {
                'data': [
                    {
                        'x': dates,
                        'y': funding_rates,
                        'type': 'scatter',
                        'mode': 'lines+markers',
                        'name': '资金费率 (%)',
                        'yaxis': 'y'
                    },
                    {
                        'x': dates,
                        'y': mark_prices,
                        'type': 'scatter',
                        'mode': 'lines+markers',
                        'name': '标记价格',
                        'yaxis': 'y2'
                    },
                    {
                        'x': dates,
                        'y': index_prices,
                        'type': 'scatter',
                        'mode': 'lines+markers',
                        'name': '指数价格',
                        'yaxis': 'y2'
                    }
                ],
                'layout': {
                    'title': f'{symbol} 监控历史数据',
                    'xaxis': {'title': '时间'},
                    'yaxis': {'title': '资金费率 (%)', 'side': 'left'},
                    'yaxis2': {'title': '价格', 'side': 'right', 'overlaying': 'y'},
                    'hovermode': 'closest'
                }
            }
            
            # 创建表格
            table_rows = []
            for i, record in enumerate(history_data):
                try:
                    timestamp = record.get('timestamp', '')
                    if timestamp:
                        if 'T' in timestamp:
                            dt = datetime.fromisoformat(timestamp)
                        else:
                            dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                        formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        formatted_time = '未知时间'
                    
                    table_rows.append(html.Tr([
                        html.Td(formatted_time),
                        html.Td(f"{float(record.get('funding_rate', 0)) * 100:.4f}%"),
                        html.Td(f"${float(record.get('mark_price', 0)):.4f}"),
                        html.Td(f"${float(record.get('index_price', 0)):.4f}"),
                        html.Td(record.get('data_source', 'unknown'))
                    ]))
                except Exception as e:
                    print(f"⚠️ 创建表格行时出错: {e}")
                    continue
            
            table_header = html.Thead(html.Tr([
                html.Th("时间"),
                html.Th("资金费率"),
                html.Th("标记价格"),
                html.Th("指数价格"),
                html.Th("数据来源")
            ]))
            
            table = dbc.Table([table_header, html.Tbody(table_rows)], bordered=True, hover=True)
            
            print(f"✅ 监控历史数据准备完成，图表数据: {len(dates)} 点，表格行数: {len(table_rows)}")
            return not is_open, f"{symbol} 监控历史数据", fig, table
            
        else:
            # 调用原有的历史数据API
            resp = requests.get(f"{API_BASE_URL}/funding_rates?symbol={symbol}")
            if resp.status_code != 200:
                error_msg = f"无法获取历史数据: {resp.text}"
                print(f"❌ {error_msg}")
                return not is_open, f"{symbol} 历史资金费率", {}, error_msg

            data = resp.json()
            funding_rates = data.get("funding_rate", [])

            if not funding_rates:
                return not is_open, f"{symbol} 历史资金费率", {}, "暂无历史数据"

        # 准备图表数据 - 双Y轴显示资金费率和价格
        dates = [item.get("funding_time") for item in funding_rates]
        rates = [item.get("funding_rate") * 100 for item in funding_rates]
        prices = [item.get("mark_price", 0) for item in funding_rates]

        figure = {
            'data': [
                {
                    'x': dates,
                    'y': rates,
                    'type': 'line',
                    'name': '资金费率(%)',
                    'yaxis': 'y',
                    'line': {'color': 'blue'}
                },
                {
                    'x': dates,
                    'y': prices,
                    'type': 'line',
                    'name': '标记价格($)',
                    'yaxis': 'y2',
                    'line': {'color': 'red'}
                }
            ],
            'layout': {
                'title': f'{symbol} 历史资金费率与价格',
                'xaxis': {'title': '时间'},
                'yaxis': {
                    'title': '资金费率(%)',
                    'side': 'left',
                    'color': 'blue'
                },
                'yaxis2': {
                    'title': '标记价格($)',
                    'side': 'right',
                    'overlaying': 'y',
                    'color': 'red'
                },
                'hovermode': 'closest',
                'legend': {'x': 0.1, 'y': 0.9}
            }
        }

        # 准备表格数据 - 添加价格列
        table_header = [html.Thead(html.Tr([
            html.Th("时间"), 
            html.Th("资金费率(%)"), 
            html.Th("标记价格($)")
        ]))]
        table_rows = []
        for item in funding_rates:
            funding_rate = item.get('funding_rate', 0)
            mark_price = item.get('mark_price', 0)
            
            # 根据资金费率设置颜色
            rate_color = "success" if abs(funding_rate) >= 0.01 else "secondary"  # 1%阈值
            
            table_rows.append(
                html.Tr([
                    html.Td(item.get("funding_time")),
                    html.Td(dbc.Badge(f"{funding_rate*100:.4f}%", color=rate_color)),
                    html.Td(f"${mark_price:.4f}" if mark_price else "未知")
                ])
            )
        table = dbc.Table(table_header + [html.Tbody(table_rows)], bordered=True, hover=True)

        print(f"✅ 历史数据准备完成，图表数据: {len(dates)} 点，表格行数: {len(table_rows)}")
        return not is_open, f"{symbol} 历史资金费率与价格", figure, table
        
    except Exception as e:
        error_msg = f"获取数据异常: {str(e)}"
        print(f"❌ 查看历史异常: {error_msg}")
        print(f"❌ 异常详情: {traceback.format_exc()}")
        return not is_open, "错误", {}, error_msg

# 获取最新资金费率回调
@app.callback(
    Output("notification", "children", allow_duplicate=True),
    Output("notification", "is_open", allow_duplicate=True),
    Input("get-latest-rates-btn", "n_clicks"),
    State("interval-filter", "value"),  # 获取当前选中的结算周期
    prevent_initial_call=True
)
def get_latest_funding_rates(latest_rates_clicks, current_interval):
    """获取最新资金费率并更新缓存，但不改变页面展示内容"""
    if not latest_rates_clicks or latest_rates_clicks <= 0:
        return "", False
    
    # 使用当前选中的结算周期，如果没有选中则默认使用1h
    interval = current_interval if current_interval else "1h"
    
    try:
        # 调用获取最新资金费率的API（这会更新缓存）
        latest_resp = requests.get(f"{API_BASE_URL}/funding_monitor/latest-rates")
        if latest_resp.status_code != 200:
            error_msg = f"获取最新资金费率失败: {latest_resp.text}"
            print(f"❌ Web界面: {error_msg}")
            return error_msg, True
        
        # 从合并后的全量缓存文件读取数据以获取统计信息
        all_cache_file = "cache/all_funding_contracts_full.json"
        if os.path.exists(all_cache_file):
            try:
                with open(all_cache_file, 'r', encoding='utf-8') as f:
                    all_cache_data = json.load(f)
                
                # 获取latest_rates字段
                latest_contracts = all_cache_data.get('latest_rates', {})
                cache_time = all_cache_data.get('cache_time', '')
                
                # 统计实时数据和缓存数据
                real_time_count = 0
                cached_count = 0
                for info in latest_contracts.values():
                    if info.get('data_source') == 'real_time':
                        real_time_count += 1
                    else:
                        cached_count += 1
                
                # 不再发送资金费率警告，避免与入池出池通知重复
                # 资金费率警告现在由API的入池出池逻辑统一处理
                warning_count = 0
                
                # 构建通知消息（不改变页面展示内容）
                notification_msg = f"✅ 缓存已更新！成功获取 {len(latest_contracts)} 个合约的最新资金费率数据 (实时: {real_time_count}, 缓存: {cached_count}) | 缓存时间: {cache_time}"
                if warning_count > 0:
                    notification_msg += f" | 📢 发现 {warning_count} 个高资金费率合约，已发送通知"
                
                # 只返回通知消息，不改变表格内容
                return notification_msg, True
                
            except Exception as e:
                error_msg = f"读取合并缓存文件失败: {str(e)}"
                print(f"❌ Web界面: {error_msg}")
                return error_msg, True
        else:
            return "⚠️ 合并缓存文件不存在", True
            
    except Exception as e:
        error_msg = f"❌ 获取最新资金费率异常: {str(e)}"
        print(f"❌ Web界面: {error_msg}")
        print(f"❌ Web界面: 异常详情: {traceback.format_exc()}")
        return error_msg, True

# 刷新备选池回调 - 刷新数据并更新页面显示
@app.callback(
    Output("pool-contracts-table", "children", allow_duplicate=True),
    Output("candidates-table", "children", allow_duplicate=True),
    Output("contract-count-display", "children", allow_duplicate=True),
    Output("funding-rate-update-time", "children", allow_duplicate=True),
    Output("notification", "children", allow_duplicate=True),
    Output("notification", "is_open", allow_duplicate=True),
    Input("refresh-candidates-pool-btn", "n_clicks"),
    State("interval-filter", "value"),  # 获取当前选中的结算周期
    prevent_initial_call=True
)
def refresh_candidates_pool(refresh_pool_clicks, current_interval):
    """刷新备选池并更新页面显示"""
    if not refresh_pool_clicks or refresh_pool_clicks <= 0:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, "", False
    
    try:
        print("🔄 开始刷新备选池...")
        
        # 使用当前选中的结算周期，如果没有选中则默认使用1h
        interval = current_interval if current_interval else "1h"
        print(f"📊 当前选中的结算周期: {interval}")
        
        # 调用刷新备选池API
        refresh_resp = requests.post(f"{API_BASE_URL}/funding_monitor/refresh-candidates")
        if refresh_resp.status_code != 200:
            error_msg = f"刷新备选池失败: {refresh_resp.text}"
            print(f"❌ {error_msg}")
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, error_msg, True
        
        print("✅ 备选池刷新成功，开始更新页面显示...")
        
        # 等待一下让缓存更新完成
        import time
        time.sleep(2)
        
        # 重新加载数据
        result, update_time = load_cached_data(interval)
        pool_table, candidates_table = result
        count_text = f"当前显示: {interval}结算周期合约 (已刷新)"
        
        notification_msg = f"✅ 备选池刷新成功！{interval}结算周期合约数据已更新"
        

        return pool_table, candidates_table, count_text, update_time, notification_msg, True
        
    except Exception as e:
        error_msg = f"刷新备选池异常: {str(e)}"
        print(f"❌ {error_msg}")
        print(f"❌ 异常详情: {traceback.format_exc()}")
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, error_msg, True

# 资金费率排序回调函数
@app.callback(
    Output("candidates-table", "children", allow_duplicate=True),
    Output("contract-count-display", "children", allow_duplicate=True),
    Output("funding-rate-update-time", "children", allow_duplicate=True),
    [
        Input("sort-funding-rate-asc", "n_clicks"),
        Input("sort-funding-rate-desc", "n_clicks")
    ],
    [State("interval-filter", "value")],
    prevent_initial_call=True
)
def sort_candidates_by_funding_rate(asc_clicks, desc_clicks, current_interval):
    """根据资金费率排序备选合约"""
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update
    
    try:
        # 确定排序方向
        sort_asc = False
        if ctx.triggered[0]['prop_id'] == 'sort-funding-rate-asc.n_clicks':
            sort_asc = True
        elif ctx.triggered[0]['prop_id'] == 'sort-funding-rate-desc.n_clicks':
            sort_asc = False
        else:
            return dash.no_update, dash.no_update
        
        # 使用当前选中的结算周期
        interval = current_interval if current_interval else "1h"
        
        # 从全量缓存文件读取原始数据
        try:
            cache_file = "cache/all_funding_contracts_full.json"
            if not os.path.exists(cache_file):
                error_msg = f"全量缓存文件不存在: {cache_file}"
                print(f"❌ {error_msg}")
                return dash.no_update, f"当前显示: {interval}结算周期合约 (排序失败: {error_msg})"
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                # 从全量缓存中获取指定结算周期的合约
                contracts_by_interval = cache_data.get('contracts_by_interval', {})
                candidates = contracts_by_interval.get(interval, {})
            
            if not candidates:
                error_msg = "没有合约数据可排序"
                print(f"❌ {error_msg}")
                return dash.no_update, f"当前显示: {interval}结算周期合约 (排序失败: {error_msg})"
            

            
            # 将字典转换为列表并排序
            candidates_list = []
            for symbol, info in candidates.items():
                try:
                    # 兼容不同的字段名
                    funding_rate = info.get("funding_rate") or info.get("current_funding_rate", 0)
                    funding_time = info.get("funding_time") or info.get("next_funding_time", "")
                    exchange = info.get("exchange", "binance")
                    
                    candidates_list.append({
                        'symbol': symbol,
                        'exchange': exchange,
                        'funding_rate': float(funding_rate),
                        'funding_time': funding_time,
                        'volume_24h': info.get('volume_24h', 0),
                        'mark_price': info.get('mark_price', 0)
                    })
                except (ValueError, TypeError) as e:
                    print(f"⚠️ 处理合约 {symbol} 时出错: {e}")
                    continue
            
            # 按资金费率排序
            candidates_list.sort(key=lambda x: x['funding_rate'], reverse=not sort_asc)
            

            
            # 重新构建表格
            def format_time(timestamp):
                """格式化时间戳为北京时间"""
                try:
                    if not timestamp:
                        return "未知"
                    
                    # 如果是字符串，尝试转换为数字
                    if isinstance(timestamp, str):
                        if timestamp.isdigit():
                            timestamp = int(timestamp)
                        else:
                            return timestamp  # 如果已经是格式化的时间字符串，直接返回
                    
                    # 如果是数字时间戳
                    if isinstance(timestamp, (int, float)):
                        # 判断是秒还是毫秒时间戳
                        if timestamp > 1e10:  # 毫秒时间戳
                            timestamp = timestamp / 1000
                        
                        # 转换为北京时间（UTC+8）
                        utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                        beijing_time = utc_time + timedelta(hours=8)
                        
                        # 格式化为常见时间格式
                        return beijing_time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    return str(timestamp)
                except Exception as e:
                    print(f"⚠️ 时间格式化失败 {timestamp}: {e}")
                    return str(timestamp)
            
            # 创建可排序的资金费率列标题
            funding_rate_header = html.Th([
                html.Span("当前资金费率", className="me-2"),
                html.Div([
                    dbc.Button("↑", id="sort-funding-rate-asc", size="sm", color="outline-primary", className="me-1", title="按资金费率升序排列"),
                    dbc.Button("↓", id="sort-funding-rate-desc", size="sm", color="outline-primary", title="按资金费率降序排列")
                ], className="d-inline")
            ])
            
            candidates_table_header = [html.Thead(html.Tr([
                html.Th("合约名称"), 
                html.Th("交易所"), 
                funding_rate_header, 
                html.Th("上一次结算时间"),
                html.Th("24小时成交量"),
                html.Th("标记价格"),
                html.Th("缓存时间"),
                html.Th("操作")
            ]))]
            
            # 获取缓存更新时间
            update_time = "未知"
            try:
                # 使用已经读取的全量缓存数据
                cache_time = cache_data.get('cache_time', '')
                if cache_time:
                    try:
                        # 解析缓存时间（缓存文件中的时间是本地时间，不需要时区转换）
                        if 'T' in cache_time:
                            # ISO格式时间，直接解析为本地时间
                            dt = datetime.fromisoformat(cache_time)
                        else:
                            # 其他格式，尝试解析
                            dt = datetime.strptime(cache_time, '%Y-%m-%d %H:%M:%S')
                        
                        # 直接使用本地时间，不需要时区转换
                        update_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        print(f"⚠️ 解析缓存时间失败: {e}")
                        update_time = cache_time
            except Exception as e:
                print(f"⚠️ 获取缓存时间失败: {e}")
            
            candidates_table_rows = []
            for item in candidates_list:
                try:
                    # 格式化时间
                    formatted_time = format_time(item['funding_time'])
                    
                    # 获取额外的数据字段
                    volume_24h = item.get('volume_24h', 0)
                    mark_price = item.get('mark_price', 0)
                    
                    # 格式化成交量和价格
                    formatted_volume = f"{float(volume_24h):,.0f}" if volume_24h else "未知"
                    formatted_price = f"${float(mark_price):.4f}" if mark_price else "未知"
                    
                    candidates_table_rows.append(
                        html.Tr([
                            html.Td(item['symbol']),
                            html.Td(item['exchange']),
                            html.Td(f"{item['funding_rate']*100:.4f}%"),
                            html.Td(formatted_time),
                            html.Td(formatted_volume),
                            html.Td(formatted_price),
                            html.Td(update_time),
                            html.Td(dbc.Button("查看历史", id={"type": "view-history", "index": item['symbol']}, size="sm", color="info", className="history-btn", title=f"查看{item['symbol']}的历史资金费率")),
                        ])
                    )
                except Exception as e:
                    print(f"⚠️ 处理排序后合约 {item['symbol']} 时出错: {e}")
                    continue
            
            # 构建排序后的表格
            sorted_table = dbc.Table(candidates_table_header + [html.Tbody(candidates_table_rows)], bordered=True, hover=True)
            
            sort_direction = "升序" if sort_asc else "降序"
            count_text = f"当前显示: {interval}结算周期合约 (已按资金费率{sort_direction}排列)"
            
            print(f"✅ 备选合约已按资金费率{sort_direction}排列")
            return sorted_table, count_text, update_time
            
        except Exception as e:
            error_msg = f"读取缓存文件失败: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"❌ 异常详情: {traceback.format_exc()}")
            return dash.no_update, f"当前显示: {interval}结算周期合约 (排序失败: {error_msg})", "排序失败"
        
    except Exception as e:
        error_msg = f"排序失败: {str(e)}"
        print(f"❌ 排序异常: {error_msg}")
        print(f"❌ 异常详情: {traceback.format_exc()}")
        return dash.no_update, f"排序失败: {error_msg}", "排序失败"

# 历史入池合约相关回调函数

@app.callback(
    [Output("history-contracts-count", "children"),
     Output("history-last-update", "children"),
     Output("history-contracts-table", "children")],
    [Input("refresh-history-btn", "n_clicks"),
     Input("page-store", "data"),
     Input("history-interval", "n_intervals")],  # 添加自动刷新输入
    prevent_initial_call=False
)
def load_history_contracts(refresh_clicks, page_data, interval_n):
    """加载历史入池合约列表"""
    try:
        # 调用API获取历史合约列表
        response = requests.get(f"{API_BASE_URL}/funding_monitor/history-contracts")
        if response.status_code != 200:
            error_msg = f"获取历史合约列表失败: {response.text}"
            print(f"❌ Web界面: {error_msg}")
            return "0", "未知", html.P(error_msg, className="text-danger")
        
        data = response.json()
        contracts = data.get('contracts', [])
        timestamp = data.get('timestamp', '')
        
        # 格式化时间
        try:
            from datetime import datetime
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                formatted_time = "未知"
        except Exception as e:
            print(f"⚠️ 时间格式化失败: {e}")
            formatted_time = timestamp
        
        # 构建历史合约表格
        if contracts:
            history_table_header = [html.Thead(html.Tr([
                html.Th("合约名称"),
                html.Th("创建时间"),
                html.Th("记录总数"),
                html.Th("时间范围"),
                html.Th("资金费率统计"),
                html.Th("价格统计"),
                html.Th("最后记录"),
                html.Th("操作")
            ]))]
            
            history_table_rows = []
            for contract in contracts:
                try:
                    # 格式化时间范围
                    start_time = contract.get('start_time', '')
                    end_time = contract.get('end_time', '')
                    time_range = f"{start_time[:10]} ~ {end_time[:10]}" if start_time and end_time else "未知"
                    
                    # 格式化资金费率统计
                    max_rate = contract.get('max_funding_rate', 0)
                    min_rate = contract.get('min_funding_rate', 0)
                    avg_rate = contract.get('avg_funding_rate', 0)
                    funding_stats = html.Div([
                        f"最高: {max_rate*100:.4f}%",
                        html.Br(),
                        f"最低: {min_rate*100:.4f}%",
                        html.Br(),
                        f"平均: {avg_rate*100:.4f}%"
                    ])
                    
                    # 格式化价格统计
                    max_price = contract.get('max_price', 0)
                    min_price = contract.get('min_price', 0)
                    avg_price = contract.get('avg_price', 0)
                    price_stats = html.Div([
                        f"最高: ${max_price:.4f}",
                        html.Br(),
                        f"最低: ${min_price:.4f}",
                        html.Br(),
                        f"平均: ${avg_price:.4f}"
                    ])
                    
                    # 格式化最后记录
                    last_rate = contract.get('last_funding_rate', 0)
                    last_price = contract.get('last_mark_price', 0)
                    last_record = html.Div([
                        f"费率: {last_rate*100:.4f}%",
                        html.Br(),
                        f"价格: ${last_price:.4f}"
                    ])
                    
                    history_table_rows.append(
                        html.Tr([
                            html.Td(contract.get('symbol', '')),
                            html.Td(contract.get('created_time', '')[:10] if contract.get('created_time') else '未知'),
                            html.Td(contract.get('total_records', 0)),
                            html.Td(time_range),
                            html.Td(funding_stats),
                            html.Td(price_stats),
                            html.Td(last_record),
                            html.Td(dbc.Button("查看详情", id={"type": "view-history-detail", "index": contract.get('symbol', '')}, size="sm", color="info", className="history-detail-btn", title=f"查看{contract.get('symbol', '')}的历史资金费率详情")),
                        ])
                    )
                except Exception as e:
                    print(f"⚠️ 处理历史合约 {contract.get('symbol', '')} 时出错: {e}")
                    continue
            
            history_table = dbc.Table(history_table_header + [html.Tbody(history_table_rows)], bordered=True, hover=True, responsive=True)
        else:
            history_table = html.P("暂无历史入池合约数据", className="text-muted")
        
        return str(len(contracts)), formatted_time, history_table
        
    except Exception as e:
        error_msg = f"加载历史合约列表失败: {e}"
        print(f"❌ Web界面: {error_msg}")
        return "0", "未知", html.P(error_msg, className="text-danger")

@app.callback(
    [Output("history-contract-modal", "is_open"),
     Output("history-modal-title", "children"),
     Output("history-contract-stats", "children"),
     Output("history-contract-graph", "figure"),
     Output("history-contract-table", "children")],
    [Input({"type": "view-history-detail", "index": dash.ALL}, "n_clicks")],
    [State("history-contract-modal", "is_open")],
    prevent_initial_call=True
)
def open_history_contract_modal(n_clicks_list, is_open):
    """打开历史合约详情弹窗"""
    if not any(n_clicks_list):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # 获取被点击的合约
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    triggered_id = ctx.triggered[0]['prop_id']
    if 'n_clicks' not in triggered_id:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # 解析合约名称
    try:
        import json
        button_id = json.loads(triggered_id.split('.')[0])
        symbol = button_id['index']
    except:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    try:
        # 调用API获取合约历史详情
        response = requests.get(f"{API_BASE_URL}/funding_monitor/history-contract/{symbol}")
        if response.status_code != 200:
            error_msg = f"获取合约 {symbol} 历史详情失败: {response.text}"
            print(f"❌ Web界面: {error_msg}")
            return not is_open, f"错误 - {symbol}", html.P(error_msg, className="text-danger"), {}, html.P(error_msg, className="text-danger")
        
        data = response.json()
        history_records = data.get('history', [])
        created_time = data.get('created_time', '')
        total_records = data.get('total_records', 0)
        
        if not history_records:
            return not is_open, f"{symbol} - 历史详情", html.P("暂无历史数据", className="text-muted"), {}, html.P("暂无历史数据", className="text-muted")
        
        # 构建统计信息
        funding_rates = [record['funding_rate'] for record in history_records]
        mark_prices = [record['mark_price'] for record in history_records]
        
        max_rate = max(funding_rates)
        min_rate = min(funding_rates)
        avg_rate = sum(funding_rates) / len(funding_rates)
        
        max_price = max(mark_prices)
        min_price = min(mark_prices)
        avg_price = sum(mark_prices) / len(mark_prices)
        
        stats_html = dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("资金费率统计", className="card-title"),
                        html.P(f"最高: {max_rate*100:.4f}%", className="mb-1"),
                        html.P(f"最低: {min_rate*100:.4f}%", className="mb-1"),
                        html.P(f"平均: {avg_rate*100:.4f}%", className="mb-0"),
                    ])
                ], color="primary", outline=True)
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("价格统计", className="card-title"),
                        html.P(f"最高: ${max_price:.4f}", className="mb-1"),
                        html.P(f"最低: ${min_price:.4f}", className="mb-1"),
                        html.P(f"平均: ${avg_price:.4f}", className="mb-0"),
                    ])
                ], color="success", outline=True)
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("记录统计", className="card-title"),
                        html.P(f"总记录数: {total_records}", className="mb-1"),
                        html.P(f"创建时间: {created_time[:10] if created_time else '未知'}", className="mb-1"),
                        html.P(f"数据源: 历史记录", className="mb-0"),
                    ])
                ], color="info", outline=True)
            ], width=6)
        ])
        
        # 构建图表
        timestamps = [record['timestamp'] for record in history_records]
        funding_rates = [record['funding_rate'] for record in history_records]
        mark_prices = [record['mark_price'] for record in history_records]
        
        # 创建图表
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=(f'{symbol} 历史资金费率', f'{symbol} 历史标记价格'),
            vertical_spacing=0.1
        )
        
        # 添加资金费率线
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=[rate * 100 for rate in funding_rates],
                mode='lines+markers',
                name='资金费率 (%)',
                line=dict(color='blue', width=2),
                marker=dict(size=4)
            ),
            row=1, col=1
        )
        
        # 添加价格线
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=mark_prices,
                mode='lines+markers',
                name='标记价格 ($)',
                line=dict(color='green', width=2),
                marker=dict(size=4)
            ),
            row=2, col=1
        )
        
        fig.update_layout(
            height=600,
            showlegend=True,
            title=f"{symbol} 历史数据图表"
        )
        
        fig.update_xaxes(title_text="时间", row=2, col=1)
        fig.update_yaxes(title_text="资金费率 (%)", row=1, col=1)
        fig.update_yaxes(title_text="价格 ($)", row=2, col=1)
        
        # 构建详细数据表格
        history_table_header = [html.Thead(html.Tr([
            html.Th("时间"),
            html.Th("资金费率"),
            html.Th("标记价格"),
            html.Th("指数价格"),
            html.Th("数据源"),
            html.Th("更新时间")
        ]))]
        
        history_table_rows = []
        for record in history_records:
            history_table_rows.append(
                html.Tr([
                    html.Td(record.get('timestamp', '')[:19] if record.get('timestamp') else '未知'),
                    html.Td(f"{record.get('funding_rate', 0)*100:.4f}%"),
                    html.Td(f"${record.get('mark_price', 0):.4f}"),
                    html.Td(f"${record.get('index_price', 0):.4f}"),
                    html.Td(record.get('data_source', 'unknown')),
                    html.Td(record.get('last_updated', '')[:19] if record.get('last_updated') else '未知')
                ])
            )
        
        history_table = dbc.Table(history_table_header + [html.Tbody(history_table_rows)], bordered=True, hover=True, responsive=True, size="sm")
        
        return not is_open, f"{symbol} - 历史详情", stats_html, fig, history_table
        
    except Exception as e:
        error_msg = f"获取合约 {symbol} 历史详情失败: {e}"
        print(f"❌ Web界面: {error_msg}")
        return not is_open, f"错误 - {symbol}", html.P(error_msg, className="text-danger"), {}, html.P(error_msg, className="text-danger")

# 归档数据相关回调函数

@app.callback(
    [Output("total-sessions-count", "children"),
     Output("total-contracts-count", "children"),
     Output("avg-duration", "children"),
     Output("archive-contracts-table", "children")],
    [Input("refresh-archive-btn", "n_clicks"),
     Input("page-store", "data")],
    prevent_initial_call=False
)
def load_archive_data(refresh_clicks, page_data):
    """加载归档数据"""
    try:
        # 调用API获取归档统计
        response = requests.get(f"{API_BASE_URL}/funding_monitor/archive/statistics")
        if response.status_code != 200:
            error_msg = f"获取归档统计失败: {response.text}"
            print(f"❌ Web界面: {error_msg}")
            return "0", "0", "0分钟", html.P(error_msg, className="text-danger")
        
        stats_data = response.json()
        statistics = stats_data.get('statistics', {})
        
        total_sessions = statistics.get('total_sessions', 0)
        total_contracts = statistics.get('total_contracts', 0)
        avg_duration = statistics.get('average_duration_minutes', 0)
        
        # 格式化平均持续时间
        if avg_duration >= 60:
            duration_text = f"{avg_duration/60:.1f}小时"
        else:
            duration_text = f"{avg_duration:.0f}分钟"
        
        # 获取归档合约列表
        contracts_response = requests.get(f"{API_BASE_URL}/funding_monitor/archive/contracts")
        if contracts_response.status_code != 200:
            contracts_table = html.P("获取归档合约列表失败", className="text-danger")
        else:
            contracts_data = contracts_response.json()
            contracts = contracts_data.get('contracts', [])
            
            if contracts:
                # 构建归档合约表格
                archive_table_header = [html.Thead(html.Tr([
                    html.Th("合约名称"),
                    html.Th("总会话数"),
                    html.Th("最新入池时间"),
                    html.Th("最新出池时间"),
                    html.Th("最新持续时间"),
                    html.Th("操作")
                ]))]
                
                archive_table_rows = []
                for contract in contracts:
                    # 格式化时间
                    latest_entry_time = contract.get('latest_entry_time', '')
                    latest_exit_time = contract.get('latest_exit_time', '')
                    
                    if latest_entry_time:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(latest_entry_time.replace('Z', '+00:00'))
                            formatted_entry_time = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            formatted_entry_time = latest_entry_time[:16]
                    else:
                        formatted_entry_time = "未知"
                    
                    if latest_exit_time:
                        try:
                            dt = datetime.fromisoformat(latest_exit_time.replace('Z', '+00:00'))
                            formatted_exit_time = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            formatted_exit_time = latest_exit_time[:16]
                    else:
                        formatted_exit_time = "进行中"
                    
                    # 格式化持续时间
                    duration_minutes = contract.get('latest_duration_minutes', 0)
                    if duration_minutes >= 60:
                        duration_text = f"{duration_minutes/60:.1f}小时"
                    else:
                        duration_text = f"{duration_minutes}分钟"
                    
                    archive_table_rows.append(
                        html.Tr([
                            html.Td(contract.get('symbol', '')),
                            html.Td(contract.get('total_sessions', 0)),
                            html.Td(formatted_entry_time),
                            html.Td(formatted_exit_time),
                            html.Td(duration_text),
                            html.Td(dbc.Button("查看会话", id={"type": "view-archive-sessions", "index": contract.get('symbol', '')}, size="sm", color="info", className="archive-sessions-btn", title=f"查看{contract.get('symbol', '')}的所有归档会话")),
                        ])
                    )
                
                contracts_table = dbc.Table(archive_table_header + [html.Tbody(archive_table_rows)], bordered=True, hover=True, responsive=True)
            else:
                contracts_table = html.P("暂无归档合约数据", className="text-muted")
        
        return str(total_sessions), str(total_contracts), duration_text, contracts_table
        
    except Exception as e:
        error_msg = f"加载归档数据失败: {e}"
        print(f"❌ Web界面: {error_msg}")
        return "0", "0", "0分钟", html.P(error_msg, className="text-danger")

@app.callback(
    Output("notification", "children", allow_duplicate=True),
    Output("notification", "is_open", allow_duplicate=True),
    Input("cleanup-archive-btn", "n_clicks"),
    prevent_initial_call=True
)
def cleanup_archive_data(cleanup_clicks):
    """清理旧归档数据"""
    try:
        response = requests.post(f"{API_BASE_URL}/funding_monitor/archive/cleanup?days_to_keep=30")
        if response.status_code == 200:
            data = response.json()
            message = data.get('message', '归档数据清理完成')
            return message, True
        else:
            error_msg = f"清理归档数据失败: {response.text}"
            return error_msg, True
    except Exception as e:
        error_msg = f"清理归档数据异常: {str(e)}"
        return error_msg, True

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)