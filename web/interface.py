import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import requests
import json
import traceback
import datetime

API_BASE_URL = "http://localhost:8000"

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "加密货币资金费率监控系统"

def load_cached_data(interval="1h"):
    """加载缓存数据"""
    try:
        print(f"📋 开始加载缓存数据，结算周期: {interval}")
        
        # 获取当前监控合约（从缓存）
        print("📡 正在获取监控合约数据...")
        pool_resp = requests.get(f"{API_BASE_URL}/funding_monitor/pool")
        print(f"📡 监控合约API响应状态: {pool_resp.status_code}")
        pool_data = pool_resp.json() if pool_resp.status_code == 200 else {}
        pool_contracts = pool_data.get("contracts", [])
        print(f"📋 从缓存加载了 {len(pool_contracts)} 个监控合约")

        # 根据结算周期获取对应的缓存数据
        print(f"📡 正在获取{interval}结算周期合约数据...")
        candidates_resp = requests.get(f"{API_BASE_URL}/funding_monitor/contracts-by-interval/{interval}")
        print(f"📡 备选合约API响应状态: {candidates_resp.status_code}")
        candidates_data = candidates_resp.json() if candidates_resp.status_code == 200 else {}
        candidates = candidates_data.get("contracts", {})
        print(f"📋 从缓存加载了 {len(candidates)} 个{interval}结算周期合约")
        
        print("🔧 开始构建表格...")
        result = build_tables(pool_contracts, candidates, interval)
        print("✅ 缓存数据加载完成")
        return result
        
    except Exception as e:
        error_msg = f"加载缓存数据失败: {str(e)}"
        print(f"❌ 加载缓存数据异常: {error_msg}")
        print(f"❌ 异常详情: {traceback.format_exc()}")
        return f"加载缓存数据失败: {str(e)}", f"加载缓存数据失败: {str(e)}"

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

@app.callback(
    Output("notification", "children"),
    Output("notification", "is_open"),
    [
        Input("refresh-candidates-pool-btn", "n_clicks"),
    ]
)

def unified_notification_callback(refresh_pool_clicks):
    ctx = callback_context
    if not ctx.triggered:
        return "", False
    btn_id = ctx.triggered[0]['prop_id'].split('.')[0]
    try:
        if btn_id == "refresh-candidates-pool-btn":
            resp = requests.post(f"{API_BASE_URL}/funding_monitor/refresh-candidates")
            if resp.status_code == 200:
                return "备选合约池刷新成功！", True
            else:
                return f"刷新失败: {resp.text}", True
        else:
            return "", False
    except Exception as e:
        return f"请求异常: {str(e)}", True

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
    prevent_initial_call=True
)
def update_candidates_data(refresh_clicks):
    """只加载缓存数据，不调用API更新"""
    try:
        # 默认使用1h结算周期，或者可以从当前选中的值获取
        interval = "1h"  # 这里可以改为从当前选中的值获取
        print(f"📋 开始加载缓存数据，结算周期: {interval}")
        
        # 获取当前监控合约（从缓存）
        print("📡 正在获取监控合约数据...")
        pool_resp = requests.get(f"{API_BASE_URL}/funding_monitor/pool")
        print(f"📡 监控合约API响应状态: {pool_resp.status_code}")
        pool_data = pool_resp.json() if pool_resp.status_code == 200 else {}
        pool_contracts = pool_data.get("contracts", [])
        print(f"📋 从缓存加载了 {len(pool_contracts)} 个监控合约")

        # 根据结算周期获取对应的缓存数据
        print(f"📡 正在获取{interval}结算周期合约数据...")
        candidates_resp = requests.get(f"{API_BASE_URL}/funding_monitor/contracts-by-interval/{interval}")
        print(f"📡 备选合约API响应状态: {candidates_resp.status_code}")
        candidates_data = candidates_resp.json() if candidates_resp.status_code == 200 else {}
        candidates = candidates_data.get("contracts", {})
        print(f"📋 从缓存加载了 {len(candidates)} 个{interval}结算周期合约")
        
        print("🔧 开始构建表格...")
        result = build_tables(pool_contracts, candidates, interval)
        print("✅ 缓存数据加载完成")
        return result
        
    except Exception as e:
        error_msg = f"加载缓存数据失败: {str(e)}"
        print(f"❌ 加载缓存数据异常: {error_msg}")
        print(f"❌ 异常详情: {traceback.format_exc()}")
        return f"加载缓存数据失败: {str(e)}", f"加载缓存数据失败: {str(e)}"
        
def build_tables(pool_contracts, candidates, interval="1h"):
    """构建表格组件"""
    try:
        print(f"🔧 开始构建表格，监控合约: {len(pool_contracts)}, 备选合约: {len(candidates)}, 结算周期: {interval}")
        
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
                    
                    pool_table_rows.append(
                        html.Tr([
                            html.Td(contract.get("symbol", "")),
                            html.Td(exchange),
                            html.Td(f"{float(funding_rate)*100:.4f}%"),
                            html.Td(funding_time),
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
                    
                    candidates_table_rows.append(
                        html.Tr([
                            html.Td(symbol),
                            html.Td(exchange),
                            html.Td(f"{float(funding_rate)*100:.4f}%"),
                            html.Td(funding_time),
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
    prevent_initial_call=True
)
def get_latest_funding_rates(latest_rates_clicks):
    if not latest_rates_clicks or latest_rates_clicks <= 0:
        return dash.no_update, "", False
    
    try:
        # 调用获取最新资金费率的API
        latest_resp = requests.get(f"{API_BASE_URL}/funding_monitor/latest-rates")
        if latest_resp.status_code != 200:
            return dash.no_update, f"获取最新资金费率失败: {latest_resp.text}", True
        
        latest_data = latest_resp.json()
        latest_contracts = latest_data.get("contracts", {})
        
        if latest_contracts:
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
            for symbol, info in latest_contracts.items():
                funding_rate = info.get("funding_rate", 0)
                next_time = info.get("next_funding_time")
                if next_time:
                    try:
                        next_time_dt = datetime.datetime.fromtimestamp(int(next_time) / 1000)
                        next_time_str = next_time_dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        next_time_str = str(next_time)
                else:
                    next_time_str = "未知"
                
                # 根据资金费率设置颜色
                rate_color = "success" if abs(funding_rate) >= 0.005 else "secondary"
                rate_text = f"{funding_rate*100:.4f}%"
                
                # 数据状态指示
                data_status = info.get("last_updated", "")
                if data_status == "cached":
                    status_badge = dbc.Badge("缓存", color="warning", className="ms-1")
                else:
                    status_badge = dbc.Badge("实时", color="success", className="ms-1")
                
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
            real_time_count = sum(1 for info in latest_contracts.values() if info.get("last_updated") != "cached")
            cached_count = len(latest_contracts) - real_time_count
            
            notification_msg = f"✅ 成功获取 {len(latest_contracts)} 个合约的最新资金费率数据 (实时: {real_time_count}, 缓存: {cached_count})"
            
            return candidates_table, notification_msg, True
        else:
            return html.P("暂无最新资金费率数据"), "⚠️ 未获取到最新资金费率数据", True
            
    except Exception as e:
        error_msg = f"❌ 获取最新资金费率异常: {str(e)}"
        return dash.no_update, error_msg, True

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)