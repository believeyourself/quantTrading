import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import requests
import json
import traceback
from datetime import datetime, timezone, timedelta
import os # Added for file operations

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
                
                # 如果没有监控合约池，则进行筛选（向后兼容）
                if not monitor_pool:
                    try:
                        from config.settings import settings
                        threshold = settings.FUNDING_RATE_THRESHOLD
                        min_volume = settings.MIN_VOLUME
                    except ImportError:
                        threshold = 0.005  # 0.5% 默认值
                        min_volume = 1000000  # 100万USDT 默认值
                    
                    # 筛选符合条件的合约
                    contracts_by_interval = cache_data.get('contracts_by_interval', {})
                    for interval, contracts in contracts_by_interval.items():
                        for symbol, info in contracts.items():
                            try:
                                funding_rate = abs(float(info.get('current_funding_rate', 0)))
                                volume_24h = float(info.get('volume_24h', 0))
                                
                                if funding_rate >= threshold and volume_24h >= min_volume:
                                    monitor_pool[symbol] = info
                            except (ValueError, TypeError) as e:
                                print(f"⚠️ 处理监控合约 {symbol} 时出错: {e}")
                                continue
                
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
                html.Th("交易所"), 
                html.Th("当前资金费率"), 
                html.Th("上一次结算时间"),
                html.Th("24小时成交量"),
                html.Th("标记价格"),
                html.Th("缓存时间")
            ]))]
            pool_table_rows = []
            for contract in pool_contracts:
                try:
                    # 兼容不同的字段名
                    funding_rate = contract.get("funding_rate") or contract.get("current_funding_rate", 0)
                    funding_time = contract.get("funding_time") or contract.get("next_funding_time", "")
                    exchange = contract.get("exchange", "binance")
                    volume_24h = contract.get("volume_24h", 0)
                    mark_price = contract.get("mark_price", 0)
                    
                    # 格式化时间
                    formatted_time = format_time(funding_time)
                    
                    # 格式化成交量和价格
                    formatted_volume = f"{float(volume_24h):,.0f}" if volume_24h else "未知"
                    formatted_price = f"${float(mark_price):.4f}" if mark_price else "未知"
                    
                    pool_table_rows.append(
                        html.Tr([
                            html.Td(contract.get("symbol", "")),
                            html.Td(exchange),
                            html.Td(f"{float(funding_rate)*100:.4f}%"),
                            html.Td(formatted_time),
                            html.Td(formatted_volume),
                            html.Td(formatted_price),
                            html.Td(update_time),  # 使用全局的update_time
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
                html.Th("交易所"), 
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
                    exchange = info.get("exchange", "binance")
                    volume_24h = info.get("volume_24h", 0)
                    mark_price = info.get("mark_price", 0)
                    
                    # 格式化时间
                    formatted_time = format_time(funding_time)
                    
                    # 格式化成交量和价格
                    formatted_volume = f"{float(volume_24h):,.0f}" if volume_24h else "未知"
                    formatted_price = f"${float(mark_price):.4f}" if mark_price else "未知"
                    
                    candidates_table_rows.append(
                        html.Tr([
                            html.Td(symbol),
                            html.Td(exchange),
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
        Input({"type": "view-history", "index": dash.ALL}, "n_clicks")
    ],
    [State("history-rate-modal", "is_open")],
    prevent_initial_call=True
)
def open_history_modal(n_clicks, is_open):
    ctx = callback_context
    
    if not ctx.triggered:
        return False, "", {}, ""

    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # 检查是否真的是历史按钮被点击
    if not ('"type":"view-history"' in triggered_id and '"index":' in triggered_id):
        return False, "", {}, ""
    
    # 检查是否有实际的点击事件
    if not any(n_clicks):
        return False, "", {}, ""
    
    # 找到被点击的按钮索引
    clicked_index = None
    for i, clicks in enumerate(n_clicks):
        if clicks and clicks > 0:
            clicked_index = i
            break
    
    if clicked_index is None:
        return False, "", {}, ""
    
    try:
        # 解析symbol - 支持两种ID格式
        parsed_id = json.loads(triggered_id)
        symbol = parsed_id.get('index') or parsed_id.get('symbol')
        if not symbol:
            return False, "", {}, ""
        
        # 调用API获取历史数据
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
                
                # 检查资金费率并发送通知（统一通知逻辑）
                try:
                    from utils.funding_rate_utils import FundingRateUtils
                    from config.settings import settings
                    
                    # 从settings.py获取阈值配置
                    threshold = settings.FUNDING_RATE_THRESHOLD
                    
                    # 使用工具类检查资金费率
                    warning_count, messages = FundingRateUtils.check_funding_rates(
                        latest_contracts, 
                        threshold, 
                        "Web界面"
                    )
                    
                    if warning_count > 0:
                        print(f"📢 Web界面: 发送了 {warning_count} 个资金费率警告通知")
                        
                except ImportError:
                    warning_count = 0
                except Exception as e:
                    print(f"❌ Web界面: 资金费率检查失败: {e}")
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)