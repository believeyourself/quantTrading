import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import requests
import json
from utils.binance_funding import BinanceFunding
import datetime

API_BASE_URL = "http://localhost:8000"

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "加密货币资金费率监控系统"

app.layout = dbc.Container([
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
                    dbc.Button("♻️ 刷新备选池", id="refresh-candidates-pool-btn", color="primary", className="mb-2"),
                    html.H4("当前监控合约"),
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

# 刷新合约数据回调
@app.callback(
    Output("pool-contracts-table", "children"),
    Output("candidates-table", "children"),
    [
        Input("candidates-interval", "n_intervals"),
        Input("refresh-candidates-btn", "n_clicks"),
    ]
)

def update_candidates(n, refresh_clicks):
    try:
        # 获取当前监控合约
        pool_resp = requests.get(f"{API_BASE_URL}/funding_monitor/pool")
        pool_data = pool_resp.json() if pool_resp.status_code == 200 else {}
        pool_contracts = pool_data.get("contracts", [])

        # 获取所有1小时结算合约
        candidates_resp = requests.get(f"{API_BASE_URL}/funding_monitor/all-contracts")
        candidates_data = candidates_resp.json() if candidates_resp.status_code == 200 else {}
        candidates = candidates_data.get("contracts", {})

        # 构建当前监控合约表格
        if pool_contracts:
            pool_table_header = [html.Thead(html.Tr([html.Th("合约名称"), html.Th("交易所"), html.Th("当前资金费率"), html.Th("上一次结算时间")]))]
            pool_table_rows = []
            for contract in pool_contracts:
                pool_table_rows.append(
                    html.Tr([
                        html.Td(contract.get("symbol", "")),
                        html.Td(contract.get("exchange", "")),
                        html.Td(f"{contract.get("funding_rate", 0)*100:.4f}%"),
                        html.Td(contract.get("funding_time", "")),
                    ])
                )
            pool_table = dbc.Table(pool_table_header + [html.Tbody(pool_table_rows)], bordered=True, hover=True)
        else:
            pool_table = html.P("暂无监控合约数据")

        # 构建所有备选合约表格
        if candidates:
            candidates_table_header = [html.Thead(html.Tr([html.Th("合约名称"), html.Th("交易所"), html.Th("当前资金费率"), html.Th("上一次结算时间"), html.Th("操作")]))]
            candidates_table_rows = []
            for symbol, info in candidates.items():
                candidates_table_rows.append(
                    html.Tr([
                        html.Td(symbol),
                        html.Td(info.get("exchange", "")),
                        html.Td(f"{info.get("funding_rate", 0)*100:.4f}%"),
                        html.Td(info.get("funding_time", "")),
                        html.Td(dbc.Button("查看历史", id={"type": "view-history", "index": symbol}, size="sm", color="info")),
                    ])
                )
            candidates_table = dbc.Table(candidates_table_header + [html.Tbody(candidates_table_rows)], bordered=True, hover=True)
        else:
            candidates_table = html.P("暂无备选合约数据")

        return pool_table, candidates_table
    except Exception as e:
        return f"获取合约数据失败: {str(e)}", f"获取备选合约数据失败: {str(e)}"

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

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)