import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import requests
import json
import traceback
from datetime import datetime, timezone, timedelta
import os # Added for file operations

API_BASE_URL = "http://localhost:8000"

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "加密货币资金费率监控系统"

def load_cached_data(interval="1h"):
    """直接加载本地缓存数据，不调用API"""
    try:
        print(f"📋 开始加载本地缓存数据，结算周期: {interval}")
        
        # 直接读取监控合约缓存文件
        pool_contracts = []
        try:
            with open("cache/funding_rate_contracts.json", 'r', encoding='utf-8') as f:
                pool_data = json.load(f)
                if 'contracts' in pool_data:
                    contracts = pool_data.get('contracts', {})
                else:
                    contracts = pool_data
                
                # 转换为列表格式
                for symbol, info in contracts.items():
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
                
                print(f"📋 从本地缓存加载了 {len(pool_contracts)} 个监控合约")
        except FileNotFoundError:
            print("📋 监控合约缓存文件不存在")
        except Exception as e:
            print(f"⚠️ 读取监控合约缓存失败: {e}")

        # 直接读取指定结算周期的缓存文件
        candidates = {}
        try:
            cache_file = f"cache/{interval}_funding_contracts_full.json"
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    candidates = cache_data.get('contracts', {})
                    print(f"📋 从本地缓存加载了 {len(candidates)} 个{interval}结算周期合约")
            else:
                print(f"📋 {interval}结算周期缓存文件不存在: {cache_file}")
        except Exception as e:
            print(f"⚠️ 读取{interval}结算周期缓存失败: {e}")
        
        print("🔧 开始构建表格...")
        result = build_tables(pool_contracts, candidates, interval)
        print("✅ 本地缓存数据加载完成")
        return result
        
    except Exception as e:
        error_msg = f"加载本地缓存数据失败: {str(e)}"
        print(f"❌ 加载本地缓存数据异常: {error_msg}")
        print(f"❌ 异常详情: {traceback.format_exc()}")
        return f"加载本地缓存数据失败: {str(e)}", f"加载本地缓存数据失败: {str(e)}"

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
                            html.H5("历史资金费率表格数据"),
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
    Input("page-store", "data")
)
def initialize_page(data):
    """页面初始化时只加载缓存数据，不主动更新"""
    print(f"🚀 页面初始化 - 加载缓存数据")
    pool_table, candidates_table = load_cached_data("1h")  # 默认加载1小时结算周期
    count_text = "当前显示: 1h结算周期合约"
    return pool_table, candidates_table, count_text

# 结算周期筛选回调
@app.callback(
    Output("pool-contracts-table", "children", allow_duplicate=True),
    Output("candidates-table", "children", allow_duplicate=True),
    Output("contract-count-display", "children", allow_duplicate=True),
    Input("interval-filter", "value"),
    prevent_initial_call=True
)
def filter_by_interval(interval):
    """根据结算周期筛选合约数据"""
    print(f"🔄 切换结算周期: {interval}")
    pool_table, candidates_table = load_cached_data(interval)
    count_text = f"当前显示: {interval}结算周期合约"
    return pool_table, candidates_table, count_text

# 刷新合约数据回调 - 只在用户点击刷新按钮时触发
@app.callback(
    Output("pool-contracts-table", "children", allow_duplicate=True),
    Output("candidates-table", "children", allow_duplicate=True),
    Output("contract-count-display", "children", allow_duplicate=True),
    Input("refresh-candidates-btn", "n_clicks"),
    State("interval-filter", "value"),  # 获取当前选中的结算周期
    prevent_initial_call=True
)
def update_candidates_data(refresh_clicks, current_interval):
    """刷新时重新加载本地缓存数据"""
    try:
        # 使用当前选中的结算周期，如果没有选中则默认使用1h
        interval = current_interval if current_interval else "1h"
        print(f"🔄 刷新按钮点击 - 重新加载本地缓存数据，结算周期: {interval}")
        
        # 直接调用load_cached_data函数，它会读取本地缓存
        pool_table, candidates_table = load_cached_data(interval)
        count_text = f"当前显示: {interval}结算周期合约"
        
        print("✅ 本地缓存数据刷新完成")
        return pool_table, candidates_table, count_text
        
    except Exception as e:
        error_msg = f"刷新本地缓存数据失败: {str(e)}"
        print(f"❌ 刷新本地缓存数据异常: {error_msg}")
        print(f"❌ 异常详情: {traceback.format_exc()}")
        return f"刷新本地缓存数据失败: {str(e)}", f"刷新本地缓存数据失败: {str(e)}"
        
def build_tables(pool_contracts, candidates, interval="1h"):
    """构建表格组件"""
    try:
        print(f"🔧 开始构建表格，监控合约: {len(pool_contracts)}, 备选合约: {len(candidates)}, 结算周期: {interval}")
        
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
            print(f"🔧 构建监控合约表格，共 {len(pool_contracts)} 个合约")
            pool_table_header = [html.Thead(html.Tr([html.Th("合约名称"), html.Th("交易所"), html.Th("当前资金费率"), html.Th("上一次结算时间")]))]
            pool_table_rows = []
            for contract in pool_contracts:
                try:
                    # 兼容不同的字段名
                    funding_rate = contract.get("funding_rate") or contract.get("current_funding_rate", 0)
                    funding_time = contract.get("funding_time") or contract.get("next_funding_time", "")
                    exchange = contract.get("exchange", "binance")
                    
                    # 格式化时间
                    formatted_time = format_time(funding_time)
                    
                    pool_table_rows.append(
                        html.Tr([
                            html.Td(contract.get("symbol", "")),
                            html.Td(exchange),
                            html.Td(f"{float(funding_rate)*100:.4f}%"),
                            html.Td(formatted_time),
                        ])
                    )
                except Exception as e:
                    print(f"⚠️ 处理监控合约 {contract.get('symbol', '')} 时出错: {e}")
                    continue
            pool_table = dbc.Table(pool_table_header + [html.Tbody(pool_table_rows)], bordered=True, hover=True)
            print(f"✅ 监控合约表格构建完成，共 {len(pool_table_rows)} 行")
        else:
            pool_table = html.P("暂无监控合约数据")
            print("⚠️ 没有监控合约数据")

        # 构建所有备选合约表格
        if candidates and len(candidates) > 0:
            print(f"🔧 构建备选合约表格，共 {len(candidates)} 个合约")
            candidates_table_header = [html.Thead(html.Tr([html.Th("合约名称"), html.Th("交易所"), html.Th("当前资金费率"), html.Th("上一次结算时间"), html.Th("操作")]))]
            candidates_table_rows = []
            for symbol, info in candidates.items():
                try:
                    # 兼容不同的字段名
                    funding_rate = info.get("funding_rate") or info.get("current_funding_rate", 0)
                    funding_time = info.get("funding_time") or info.get("next_funding_time", "")
                    exchange = info.get("exchange", "binance")
                    
                    # 格式化时间
                    formatted_time = format_time(funding_time)
                    
                    candidates_table_rows.append(
                        html.Tr([
                            html.Td(symbol),
                            html.Td(exchange),
                            html.Td(f"{float(funding_rate)*100:.4f}%"),
                            html.Td(formatted_time),
                            html.Td(dbc.Button("查看历史", id={"type": "view-history", "index": symbol}, size="sm", color="info")),
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
        return f"构建表格失败: {str(e)}", f"构建表格失败: {str(e)}"

# 查看历史资金费率回调
@app.callback(
    Output("history-rate-modal", "is_open"),
    Output("modal-title", "children"),
    Output("history-rate-graph", "figure"),
    Output("history-rate-table", "children"),
    [
        Input({"type": "view-history", "index": dash.ALL}, "n_clicks")
    ],
    [State("history-rate-modal", "is_open")]
)

def open_history_modal(n_clicks, is_open):
    ctx = callback_context
    if not ctx.triggered:
        return False, "", {}, ""

    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # 检查是否真的是历史按钮被点击
    if not triggered_id.startswith('{"type":"view-history"'):
        return False, "", {}, ""
    
    try:
        symbol = json.loads(triggered_id)['index']
        resp = requests.get(f"{API_BASE_URL}/funding_rates?symbol={symbol}")
        if resp.status_code != 200:
            return not is_open, f"{symbol} 历史资金费率", {}, "无法获取历史数据"

        data = resp.json()
        funding_rates = data.get("funding_rate", [])

        if not funding_rates:
            return not is_open, f"{symbol} 历史资金费率", {}, "暂无历史数据"

        # 准备图表数据
        dates = [item.get("funding_time") for item in funding_rates]
        rates = [item.get("funding_rate") * 100 for item in funding_rates]

        figure = {
            'data': [{
                'x': dates,
                'y': rates,
                'type': 'line',
                'name': '资金费率(%)'
            }],
            'layout': {
                'title': f'{symbol} 历史资金费率',
                'xaxis': {'title': '时间'},
                'yaxis': {'title': '资金费率(%)'},
                'hovermode': 'closest'
            }
        }

        # 准备表格数据
        table_header = [html.Thead(html.Tr([html.Th("时间"), html.Th("资金费率(%)")]))]
        table_rows = []
        for item in funding_rates:
            table_rows.append(
                html.Tr([
                    html.Td(item.get("funding_time")),
                    html.Td(f"{item.get("funding_rate")*100:.4f}%")
                ])
            )
        table = dbc.Table(table_header + [html.Tbody(table_rows)], bordered=True, hover=True)

        return not is_open, f"{symbol} 历史资金费率", figure, table
    except Exception as e:
        return not is_open, "错误", {}, f"获取数据异常: {str(e)}"

# 获取最新资金费率回调
@app.callback(
    Output("candidates-table", "children", allow_duplicate=True),
    Output("notification", "children", allow_duplicate=True),
    Output("notification", "is_open", allow_duplicate=True),
    Input("get-latest-rates-btn", "n_clicks"),
    State("interval-filter", "value"),  # 获取当前选中的结算周期
    prevent_initial_call=True
)
def get_latest_funding_rates(latest_rates_clicks, current_interval):
    if not latest_rates_clicks or latest_rates_clicks <= 0:
        return dash.no_update, "", False
    
    # 使用当前选中的结算周期，如果没有选中则默认使用1h
    interval = current_interval if current_interval else "1h"
    
    try:
        print(f"🔄 Web界面: 开始获取最新资金费率，结算周期: {interval}...")
        
        # 调用获取最新资金费率的API（这会更新缓存）
        latest_resp = requests.get(f"{API_BASE_URL}/funding_monitor/latest-rates")
        if latest_resp.status_code != 200:
            error_msg = f"获取最新资金费率失败: {latest_resp.text}"
            print(f"❌ Web界面: {error_msg}")
            return dash.no_update, error_msg, True
        
        print(f"✅ Web界面: API调用成功，缓存已更新")
        
        # 直接从缓存文件读取数据
        cache_file = "cache/latest_funding_rates.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                latest_contracts = cache_data.get('contracts', {})
                real_time_count = cache_data.get('real_time_count', 0)
                cached_count = cache_data.get('cached_count', 0)
                cache_time = cache_data.get('cache_time', '')
                
                print(f"📋 Web界面: 从缓存读取到 {len(latest_contracts)} 个合约数据")
                print(f"📊 Web界面: 实时数据: {real_time_count}, 缓存数据: {cached_count}")
                
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
                    
                    # 输出所有消息
                    for msg in messages:
                        print(f"    {msg}")
                    
                    if warning_count > 0:
                        print(f"📢 Web界面: 发送了 {warning_count} 个资金费率警告通知")
                    else:
                        print(f"✅ Web界面: 所有合约资金费率都在正常范围内")
                        
                except ImportError:
                    print("⚠️ Web界面: 无法导入工具类，跳过资金费率检查")
                    warning_count = 0
                except Exception as e:
                    print(f"❌ Web界面: 资金费率检查失败: {e}")
                    warning_count = 0
                
                if latest_contracts:
                    # 根据当前选中的结算周期过滤合约
                    filtered_contracts = {}
                    for symbol, info in latest_contracts.items():
                        # 检查合约的结算周期是否匹配当前选中的值
                        contract_interval = info.get('funding_interval', '1h')
                        # 将小时数转换为对应的标签格式
                        if isinstance(contract_interval, (int, float)):
                            if abs(contract_interval - 1.0) < 0.1:
                                contract_interval = "1h"
                            elif abs(contract_interval - 2.0) < 0.1:
                                contract_interval = "2h"
                            elif abs(contract_interval - 4.0) < 0.1:
                                contract_interval = "4h"
                            elif abs(contract_interval - 8.0) < 0.1:
                                contract_interval = "8h"
                            else:
                                contract_interval = "1h"  # 默认
                        
                        if contract_interval == interval:
                            filtered_contracts[symbol] = info
                    
                    if not filtered_contracts:
                        return html.P(f"暂无{interval}结算周期的合约数据"), f"⚠️ 暂无{interval}结算周期的合约数据", True
                    
                    # 构建最新资金费率表格
                    candidates_table_header = [html.Thead(html.Tr([
                        html.Th("合约名称"), 
                        html.Th("交易所"), 
                        html.Th("最新资金费率"), 
                        html.Th("下次结算时间"), 
                        html.Th("标记价格"),
                        html.Th("数据状态")
                    ]))]
                    
                    candidates_table_rows = []
                    
                    for symbol, info in filtered_contracts.items():
                        funding_rate = info.get('funding_rate', 0)
                        next_time = info.get('next_funding_time')
                        data_source = info.get('data_source', 'unknown')
                        
                        if next_time:
                            try:
                                next_time_dt = datetime.fromtimestamp(int(next_time) / 1000)
                                next_time_str = next_time_dt.strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                next_time_str = str(next_time)
                        else:
                            next_time_str = "未知"
                        
                        # 根据资金费率设置颜色
                        rate_color = "success" if abs(funding_rate) >= threshold else "secondary"
                        rate_text = f"{funding_rate*100:.4f}%"
                        
                        # 数据状态指示
                        if data_source == "real_time":
                            status_badge = dbc.Badge("实时", color="success", className="ms-1")
                        else:
                            status_badge = dbc.Badge("缓存", color="warning", className="ms-1")
                        
                        candidates_table_rows.append(
                            html.Tr([
                                html.Td(symbol),
                                html.Td(info.get("exchange", "")),
                                html.Td(dbc.Badge(rate_text, color=rate_color)),
                                html.Td(next_time_str),
                                html.Td(f"${info.get('mark_price', 0):.4f}"),
                                html.Td(status_badge)
                            ])
                        )
                    
                    candidates_table = dbc.Table(candidates_table_header + [html.Tbody(candidates_table_rows)], bordered=True, hover=True)
                    
                    # 统计信息
                    notification_msg = f"✅ 成功获取 {len(filtered_contracts)} 个{interval}结算周期合约的最新资金费率数据 (实时: {real_time_count}, 缓存: {cached_count}) | 缓存时间: {cache_time}"
                    if warning_count > 0:
                        notification_msg += f" | 📢 发现 {warning_count} 个高资金费率合约，已发送通知"
                    
                    print(f"📊 Web界面: 表格构建完成，{interval}结算周期合约: {len(filtered_contracts)}, 实时数据: {real_time_count}, 缓存数据: {cached_count}")
                    
                    return candidates_table, notification_msg, True
                else:
                    print("⚠️ Web界面: 缓存文件中没有合约数据")
                    return html.P("暂无最新资金费率数据"), "⚠️ 缓存文件中没有合约数据", True
                    
            except Exception as e:
                error_msg = f"读取缓存文件失败: {str(e)}"
                print(f"❌ Web界面: {error_msg}")
                return dash.no_update, error_msg, True
        else:
            print("⚠️ Web界面: 缓存文件不存在")
            return html.P("缓存文件不存在"), "⚠️ 缓存文件不存在", True
            
    except Exception as e:
        error_msg = f"❌ 获取最新资金费率异常: {str(e)}"
        print(f"❌ Web界面: {error_msg}")
        print(f"❌ Web界面: 异常详情: {traceback.format_exc()}")
        return dash.no_update, error_msg, True

# 刷新备选池回调 - 刷新数据并更新页面显示
@app.callback(
    Output("pool-contracts-table", "children", allow_duplicate=True),
    Output("candidates-table", "children", allow_duplicate=True),
    Output("contract-count-display", "children", allow_duplicate=True),
    Output("notification", "children", allow_duplicate=True),
    Output("notification", "is_open", allow_duplicate=True),
    Input("refresh-candidates-pool-btn", "n_clicks"),
    State("interval-filter", "value"),  # 获取当前选中的结算周期
    prevent_initial_call=True
)
def refresh_candidates_pool(refresh_pool_clicks, current_interval):
    """刷新备选池并更新页面显示"""
    if not refresh_pool_clicks or refresh_pool_clicks <= 0:
        return dash.no_update, dash.no_update, dash.no_update, "", False
    
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
            return dash.no_update, dash.no_update, dash.no_update, error_msg, True
        
        print("✅ 备选池刷新成功，开始更新页面显示...")
        
        # 等待一下让缓存更新完成
        import time
        time.sleep(2)
        
        # 重新加载数据
        pool_table, candidates_table = load_cached_data(interval)
        count_text = f"当前显示: {interval}结算周期合约 (已刷新)"
        
        notification_msg = f"✅ 备选池刷新成功！{interval}结算周期合约数据已更新"
        
        print("✅ 页面数据更新完成")
        return pool_table, candidates_table, count_text, notification_msg, True
        
    except Exception as e:
        error_msg = f"刷新备选池异常: {str(e)}"
        print(f"❌ {error_msg}")
        print(f"❌ 异常详情: {traceback.format_exc()}")
        return dash.no_update, dash.no_update, dash.no_update, error_msg, True

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)