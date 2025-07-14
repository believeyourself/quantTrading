import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import requests
import json
from utils.binance_funding import BinanceFunding

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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050) 