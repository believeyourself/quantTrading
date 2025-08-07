import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import requests
import json
from utils.binance_funding import BinanceFunding
import datetime

API_BASE_URL = "http://localhost:8000"

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "资金费率套利系统"

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("资金费率套利系统", className="text-center mb-4"),
            html.Hr()
        ])
    ]),
    dbc.Tabs([
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H3("合约监控总览"),
                    html.P("查看所有1小时结算合约（备选池）和当前池中合约的详细数据。", className="text-muted"),
                    html.Hr(),
                    dbc.Button("🔄 刷新合约数据", id="refresh-candidates-btn", color="info", className="me-2 mb-2"),
                    dbc.Button("♻️ 刷新备选池", id="refresh-candidates-pool-btn", color="primary", className="mb-2"),
                    html.H4("当前池中合约"),
                    html.Div(id="pool-contracts-table", className="mb-4"),
                    html.H4("所有备选合约"),
                    html.Div(id="candidates-table", className="mb-4"),
                    dcc.Interval(id="candidates-interval", interval=60*1000, n_intervals=0),
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
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H3("资金费率套利策略"),
                    html.P("自动化资金费率监控系统 - 仅提供通知，不自动交易", className="text-muted"),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col([
                            dbc.Button("🚀 启动策略", id="start-funding-strategy", color="success", className="me-2"),
                            dbc.Button("🛑 停止策略", id="stop-funding-strategy", color="danger", className="me-2"),
                            dbc.Button("🔄 更新缓存", id="update-funding-cache", color="info"),
                        ], width=12)
                    ], className="mb-4"),
                    html.H4("策略状态"),
                    html.Div(id="funding-strategy-status", className="mb-4"),
                    html.H4("统计信息"),
                    html.Div(id="funding-stats", className="mb-4"),
                    dcc.Interval(id="funding-status-interval", interval=30*1000, n_intervals=0),
                ], width=12)
            ])
        ], label="资金费率套利", tab_id="funding-arbitrage"),
        # 新增回测Tab
        dbc.Tab([
            dbc.Row([
                dbc.Col([
                    html.H3("资金费率套利回测"),
                    html.P("对资金费率套利策略进行历史回测，支持自定义参数。", className="text-muted"),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("开始日期"),
                            dcc.DatePickerSingle(
                                id="backtest-start-date",
                                date=(datetime.date.today() - datetime.timedelta(days=30)),
                                display_format="YYYY-MM-DD",
                                className="mb-2"
                            ),
                            dbc.Label("结束日期"),
                            dcc.DatePickerSingle(
                                id="backtest-end-date",
                                date=datetime.date.today(),
                                display_format="YYYY-MM-DD",
                                className="mb-2"
                            ),
                            dbc.Label("初始资金"),
                            dcc.Input(id="backtest-initial-capital", type="number", value=10000, className="mb-2"),
                            dbc.Button("开始回测", id="run-funding-backtest", color="primary", className="mt-2"),
                        ], width=4),
                        dbc.Col([
                            html.Div(id="backtest-result-summary"),
                            html.Div(id="backtest-equity-curve"),
                            html.Div(id="backtest-trade-table")
                        ], width=8)
                    ])
                ], width=12)
            ])
        ], label="资金费率套利回测", tab_id="funding-arb-backtest"),
    ]),
    dbc.Toast(id="notification", header="通知", is_open=False, dismissable=True, duration=4000)
], fluid=True)

@app.callback(
    Output("notification", "children"),
    Output("notification", "is_open"),
    [
        Input("start-funding-strategy", "n_clicks"),
        Input("stop-funding-strategy", "n_clicks"),
        Input("update-funding-cache", "n_clicks"),
        Input("refresh-candidates-pool-btn", "n_clicks"),
    ]
)
def unified_notification_callback(start_clicks, stop_clicks, update_clicks, refresh_pool_clicks):
    ctx = callback_context
    if not ctx.triggered:
        return "", False
    btn_id = ctx.triggered[0]['prop_id'].split('.')[0]
    try:
        if btn_id == "start-funding-strategy":
            resp = requests.post(f"{API_BASE_URL}/funding-arbitrage/start")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", "操作成功"), True
            else:
                return f"操作失败: {resp.text}", True
        elif btn_id == "stop-funding-strategy":
            resp = requests.post(f"{API_BASE_URL}/funding-arbitrage/stop")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", "操作成功"), True
            else:
                return f"操作失败: {resp.text}", True
        elif btn_id == "update-funding-cache":
            resp = requests.post(f"{API_BASE_URL}/funding-arbitrage/update-cache")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", "操作成功"), True
            else:
                return f"操作失败: {resp.text}", True
        elif btn_id == "refresh-candidates-pool-btn":
            resp = requests.post(f"{API_BASE_URL}/funding-arbitrage/refresh-candidates")
            if resp.status_code == 200:
                return "备选合约池刷新成功！", True
            else:
                return f"刷新失败: {resp.text}", True
        else:
            return "", False
    except Exception as e:
        return f"请求异常: {str(e)}", True

@app.callback(
    Output("funding-strategy-status", "children"),
    Output("funding-stats", "children"),
    Input("funding-status-interval", "n_intervals")
)
def update_funding_status(n):
    try:
        resp = requests.get(f"{API_BASE_URL}/funding-arbitrage/status")
        if resp.status_code != 200:
            return "无法获取策略状态", "暂无统计信息"
        data = resp.json().get("data", {})
        status_html = [
            html.P(f"状态: {data.get('status', '')}"),
            html.P(f"策略名称: {data.get('strategy_name', '')}"),
            html.P(f"合约池大小: {data.get('pool_status', {}).get('pool_size', 0)}"),
            html.P(f"当前持仓: {data.get('pool_status', {}).get('current_positions', 0)}"),
            html.P(f"总盈亏: {data.get('pool_status', {}).get('total_pnl', 0.0):.2f}"),
            html.P(f"胜率: {data.get('pool_status', {}).get('win_rate', 0):.1%}")
        ]
        stats = data.get("pool_status", {})
        stats_html = [
            html.P(f"总交易次数: {stats.get('total_trades', 0)}"),
            html.P(f"盈利交易: {stats.get('winning_trades', 0)}"),
            html.P(f"总敞口: {stats.get('total_exposure', 0.0):.2f}"),
            html.P(f"可用资金: {stats.get('available_capital', 0.0):.2f}")
        ]
        return status_html, stats_html
    except Exception as e:
        return f"获取状态失败: {str(e)}", "暂无统计信息"

# 回测回调
@app.callback(
    Output("backtest-result-summary", "children"),
    Output("backtest-equity-curve", "children"),
    Output("backtest-trade-table", "children"),
    Input("run-funding-backtest", "n_clicks"),
    State("backtest-start-date", "date"),
    State("backtest-end-date", "date"),
    State("backtest-initial-capital", "value"),
    prevent_initial_call=True
)
def run_funding_backtest(n_clicks, start_date, end_date, initial_capital):
    if not (start_date and end_date and initial_capital):
        return "请填写完整参数", "", ""
    try:
        payload = {
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": float(initial_capital)
        }
        resp = requests.post(f"{API_BASE_URL}/funding-arbitrage/backtest", json=payload)
        if resp.status_code != 200:
            return f"回测失败: {resp.text}", "", ""
        data = resp.json()
        results = data.get("results", {})
        equity_curve = data.get("equity_curve", {})
        trades = data.get("trades", {})
        # 合并展示：每个合约一个卡片，内含摘要、资金曲线、明细
        cards = []
        import plotly.graph_objs as go
        for symbol in results.keys():
            res = results[symbol]
            eq = equity_curve.get(symbol, [])
            tr = trades.get(symbol, [])
            # 只展示有交易的合约
            if not tr:
                continue
            # 摘要
            if 'error' in res:
                summary = [html.H5(f"{symbol} 回测异常"), html.P(res['error'])]
            else:
                summary = [
                    html.H5(f"{symbol} 回测结果摘要"),
                    html.P(f"总收益率: {res.get('total_return', 0.0):.2%}"),
                    html.P(f"最大回撤: {res.get('max_drawdown', 0.0):.2%}"),
                    html.P(f"夏普比率: {res.get('sharpe_ratio', 0.0):.2f}"),
                    html.P(f"胜率: {res.get('win_rate', 0.0):.2%}"),
                    html.P(f"总交易次数: {res.get('total_trades', 0)}"),
                    html.P(f"初始资金: {res.get('initial_capital', 0.0):.2f}"),
                    html.P(f"期末资金: {res.get('final_capital', 0.0):.2f}")
                ]
            # 资金曲线
            if eq:
                df = [dict(timestamp=ec['timestamp'], equity=ec['equity']) for ec in eq]
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=[d['timestamp'] for d in df], y=[d['equity'] for d in df], mode='lines', name='资金曲线'))
                fig.update_layout(title=f"{symbol} 资金曲线", xaxis_title="时间", yaxis_title="资金")
                equity_graph = dcc.Graph(figure=fig)
            else:
                equity_graph = html.P(f"{symbol} 暂无资金曲线数据")
            # 交易明细表
            table_header = [html.Thead(html.Tr([
                html.Th("时间"),
                html.Th("合约"),
                html.Th("方向"),
                html.Th("数量"),
                html.Th("建仓价"),
                html.Th("平仓价"),
                html.Th("手续费"),
                html.Th("价差收益"),
                html.Th("资金费率"),
                html.Th("资金费率收益"),
                html.Th("总收益")
            ]))]
            table_body = [
                html.Tr([
                    html.Td(str(t.get('timestamp', ''))[:13] + ':00' if t.get('timestamp', '') else ''),
                    html.Td(str(t.get('symbol', ''))),
                    html.Td(str(t.get('side', ''))),
                    html.Td(f"{float(t.get('quantity', 0) or 0):.4f}"),
                    html.Td(f"{float(t.get('price_entry', 0) or 0):.4f}"),
                    html.Td(f"{float(t.get('price_exit', 0) or 0):.4f}"),
                    html.Td(f"{float(t.get('commission', 0) or 0):.4f}"),
                    html.Td(f"{float(t.get('pnl_price', 0) or 0):.2f}"),
                    html.Td(f"{float(t.get('funding_rate', 0) or 0):.6f}"),
                    html.Td(f"{float(t.get('funding_income', 0) or 0):.2f}"),
                    html.Td(f"{float(t.get('pnl_total', 0) or 0):.2f}")
                ]) for t in tr
            ]
            trade_table = html.Div([
                html.H6(f"{symbol} 交易明细"),
                dbc.Table(table_header + [html.Tbody(table_body)], bordered=True, striped=True, hover=True, size="sm")
            ])
            # 合并卡片
            cards.append(
                dbc.Card(dbc.CardBody([
                    *summary,
                    html.Hr(),
                    equity_graph,
                    html.Hr(),
                    trade_table
                ]), className="mb-4")
            )
        return cards, "", ""
    except Exception as e:
        return f"回测异常: {str(e)}", "", ""

@app.callback(
    Output("pool-contracts-table", "children"),
    Output("candidates-table", "children"),
    [Input("refresh-candidates-btn", "n_clicks"), Input("candidates-interval", "n_intervals")]
)
def update_candidates_table(refresh_clicks, n_intervals):
    try:
        # 获取所有备选合约
        resp = requests.get(f"{API_BASE_URL}/funding-arbitrage/candidates")
        if resp.status_code != 200:
            return "无法获取备选合约数据", ""
        data = resp.json()
        contracts = data.get("contracts", {})
        # 获取池中合约
        pool_resp = requests.get(f"{API_BASE_URL}/funding-arbitrage/pool-status")
        pool_contracts = set()
        if pool_resp.status_code == 200:
            pool_data = pool_resp.json().get("data", {})
            pool_contracts = set(pool_data.get("pool_contracts", []))
            # 兼容老格式
            if not pool_contracts and "contracts" in pool_data:
                pool_contracts = set(pool_data["contracts"].keys())
        # 构建池中合约表
        pool_rows = []
        for symbol in pool_contracts:
            info = contracts.get(symbol, {})
            pool_rows.append(html.Tr([
                html.Td(html.A(symbol, href="#", n_clicks_timestamp=0, id={"type": "symbol-link", "index": symbol})),
                html.Td(info.get("current_funding_rate", "-")),
                html.Td(info.get("mark_price", "-")),
                html.Td(info.get("last_updated", "-")),
            ]))
        pool_table = dbc.Table([
            html.Thead(html.Tr([html.Th("合约"), html.Th("资金费率"), html.Th("价格"), html.Th("更新时间")]))
        ] + [html.Tbody(pool_rows)], bordered=True, striped=True, hover=True)
        # 构建所有备选合约表
        candidate_rows = []
        for symbol, info in contracts.items():
            candidate_rows.append(html.Tr([
                html.Td(html.A(symbol, href="#", n_clicks_timestamp=0, id={"type": "symbol-link", "index": symbol})),
                html.Td(info.get("current_funding_rate", "-")),
                html.Td(info.get("mark_price", "-")),
                html.Td(info.get("last_updated", "-")),
            ]))
        candidates_table = dbc.Table([
            html.Thead(html.Tr([html.Th("合约"), html.Th("资金费率"), html.Th("价格"), html.Th("更新时间")]))
        ] + [html.Tbody(candidate_rows)], bordered=True, striped=True, hover=True)
        return pool_table, candidates_table
    except Exception as e:
        return f"获取合约数据失败: {str(e)}", ""



# 合约点击弹窗回调
from dash.dependencies import ALL
@app.callback(
    Output("history-rate-modal", "is_open"),
    Output("modal-title", "children"),
    Output("history-rate-graph", "figure"),
    Output("history-rate-table", "children"),
    Input({"type": "symbol-link", "index": ALL}, "n_clicks"),
    State({"type": "symbol-link", "index": ALL}, "id"),
    State("history-rate-modal", "is_open"),
    prevent_initial_call=True
)
def show_history_rate(n_clicks_list, id_list, is_open):
    import plotly.graph_objs as go
    ctx = callback_context
    if not ctx.triggered:
        return is_open, "", {}
    # 找到被点击的symbol
    for n, idd in zip(n_clicks_list, id_list):
        if n and n > 0:
            symbol = idd["index"]
            # 请求历史资金费率
            resp = requests.get(f"{API_BASE_URL}/funding-arbitrage/history-rate/{symbol}")
            if resp.status_code != 200:
                return True, f"{symbol} 历史资金费率获取失败", {}, html.P("数据获取失败")
            data = resp.json()
            history = data.get("history", [])
            # 按时间倒序排列
            history.reverse()
            if not history:
                return True, f"{symbol} 暂无历史资金费率数据", {}, html.P("暂无数据")
            x = [datetime.datetime.fromtimestamp(h["funding_time"] / 1000) for h in history]
            y = [float(h["funding_rate"]) for h in history]
            price = [float(h["mark_price"]) for h in history]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="资金费率"))
            fig.add_trace(go.Scatter(x=x, y=price, mode="lines", name="价格", yaxis="y2"))
            fig.update_layout(
                title=f"{symbol} 历史资金费率",
                xaxis_title="时间",
                yaxis=dict(title="资金费率", side="left"),
                yaxis2=dict(title="价格", overlaying="y", side="right", showgrid=False),
                legend=dict(x=0, y=1.1, orientation="h")
            )
            # 创建表格数据
            table_header = [html.Thead(html.Tr([
                html.Th("时间点"),
                html.Th("资金费率"),
                html.Th("合约价格")
            ]))]
            table_body = [html.Tbody([
                html.Tr([
                    html.Td(datetime.datetime.fromtimestamp(h["funding_time"] / 1000).strftime('%Y-%m-%d %H:%M:%S')),
                    html.Td(f"{float(h['funding_rate'])*100:.4f}%"),
                    html.Td(f"{float(h['mark_price']):.4f}")
                ]) for h in history
            ])]
            history_table = dbc.Table(
                table_header + table_body,
                bordered=True,
                striped=True,
                hover=True,
                size="sm"
            )
            return True, f"{symbol} 历史资金费率", fig, history_table
    return is_open, "", {}

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)