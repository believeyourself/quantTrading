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
                    html.H3("资金费率套利策略"),
                    html.P("自动化资金费率套利交易系统", className="text-muted"),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col([
                            dbc.Button("🚀 启动策略", id="start-funding-strategy", color="success", className="me-2"),
                            dbc.Button("🛑 停止策略", id="stop-funding-strategy", color="danger", className="me-2"),
                            dbc.Button("📊 平掉所有持仓", id="close-all-funding-positions", color="warning", className="me-2"),
                            dbc.Button("🔄 更新缓存", id="update-funding-cache", color="info"),
                        ], width=12)
                    ], className="mb-4"),
                    html.H4("策略状态"),
                    html.Div(id="funding-strategy-status", className="mb-4"),
                    html.H4("当前持仓"),
                    html.Div(id="funding-positions", className="mb-4"),
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
        Input("close-all-funding-positions", "n_clicks"),
        Input("update-funding-cache", "n_clicks"),
    ]
)
def unified_notification_callback(start_clicks, stop_clicks, close_clicks, update_clicks):
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
        elif btn_id == "close-all-funding-positions":
            resp = requests.post(f"{API_BASE_URL}/funding-arbitrage/close-all")
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
        else:
            return "", False
    except Exception as e:
        return f"请求异常: {str(e)}", True

@app.callback(
    Output("funding-strategy-status", "children"),
    Output("funding-positions", "children"),
    Output("funding-stats", "children"),
    Input("funding-status-interval", "n_intervals")
)
def update_funding_status(n):
    try:
        resp = requests.get(f"{API_BASE_URL}/funding-arbitrage/status")
        if resp.status_code != 200:
            return "无法获取策略状态", "暂无持仓", "暂无统计信息"
        data = resp.json().get("data", {})
        status_html = [
            html.P(f"状态: {data.get('status', '')}"),
            html.P(f"策略名称: {data.get('strategy_name', '')}"),
            html.P(f"合约池大小: {data.get('pool_status', {}).get('pool_size', 0)}"),
            html.P(f"当前持仓: {data.get('pool_status', {}).get('current_positions', 0)}"),
            html.P(f"总盈亏: {data.get('pool_status', {}).get('total_pnl', 0.0):.2f}"),
            html.P(f"胜率: {data.get('pool_status', {}).get('win_rate', 0):.1%}")
        ]
        positions = data.get("positions", [])
        if positions:
            positions_html = [html.H5("持仓列表")]
            for pos in positions:
                positions_html.append(html.P(
                    f"{pos['symbol']}: {pos['side']} {pos['quantity']:.4f} @ {pos['entry_price']:.4f}"
                ))
        else:
            positions_html = [html.P("暂无持仓")]
        stats = data.get("pool_status", {})
        stats_html = [
            html.P(f"总交易次数: {stats.get('total_trades', 0)}"),
            html.P(f"盈利交易: {stats.get('winning_trades', 0)}"),
            html.P(f"总敞口: {stats.get('total_exposure', 0.0):.2f}"),
            html.P(f"可用资金: {stats.get('available_capital', 0.0):.2f}")
        ]
        return status_html, positions_html, stats_html
    except Exception as e:
        return f"获取状态失败: {str(e)}", "暂无持仓", "暂无统计信息"

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
                html.Th("价格"),
                html.Th("手续费"),
                html.Th("盈亏"),
                html.Th("资金费率"),
                html.Th("资金费率收益")
            ]))]
            table_body = [
                html.Tr([
                    html.Td(str(t.get('timestamp', ''))[:13] + ':00' if t.get('timestamp', '') else ''),
                    html.Td(str(t.get('symbol', ''))),
                    html.Td(str(t.get('side', ''))),
                    html.Td(f"{float(t.get('quantity', 0) or 0):.4f}"),
                    html.Td(f"{float(t.get('price', 0) or 0):.4f}"),
                    html.Td(f"{float(t.get('commission', 0) or 0):.4f}"),
                    html.Td(f"{float(t.get('pnl', 0) or 0):.2f}"),
                    html.Td(f"{float(t.get('funding_rate', 0) or 0):.6f}"),
                    html.Td(f"{float(t.get('funding_income', 0) or 0):.2f}")
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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050) 