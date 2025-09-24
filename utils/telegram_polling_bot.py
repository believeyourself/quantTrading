#!/usr/bin/env python3
"""
Telegram polling bot (no external deps) that provides an inline menu to query
monitor pool data from the local FastAPI service.

Usage (Windows PowerShell):
  python utils/telegram_polling_bot.py

Environment/config:
  - Reads token/chat_id from config.settings or env vars TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
  - Assumes API is reachable at http://127.0.0.1:<settings.API_PORT>
"""

import os
import time
import json
from typing import Dict, Any, Optional, List, Tuple

import requests
from loguru import logger

from config.settings import settings


API_BASE = f"http://127.0.0.1:{settings.API_PORT}"


def _get_token_and_chat() -> Tuple[str, str]:
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID not configured; bot will accept messages from any chat")
    return token, chat_id


def _tg_api(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def send_message(token: str, chat_id: str, text: str, reply_markup: Optional[Dict[str, Any]] = None, 
                 parse_mode: Optional[str] = "HTML", disable_web_page_preview: bool = True,
                 reply_to_message_id: Optional[int] = None) -> None:
    data: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    if reply_to_message_id:
        data["reply_to_message_id"] = reply_to_message_id
    r = requests.post(_tg_api(token, "sendMessage"), data=data, timeout=15)
    r.raise_for_status()


def edit_message_text(token: str, chat_id: str, message_id: int, text: str,
                      reply_markup: Optional[Dict[str, Any]] = None, parse_mode: Optional[str] = "HTML") -> None:
    data: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    r = requests.post(_tg_api(token, "editMessageText"), data=data, timeout=15)
    r.raise_for_status()


def answer_callback_query(token: str, callback_query_id: str, text: Optional[str] = None, show_alert: bool = False) -> None:
    data: Dict[str, Any] = {"callback_query_id": callback_query_id, "show_alert": show_alert}
    if text:
        data["text"] = text
    r = requests.post(_tg_api(token, "answerCallbackQuery"), data=data, timeout=15)
    r.raise_for_status()


# Removed build_main_menu() - now using Telegram command menu instead


def fetch_pool() -> List[Dict[str, Any]]:
    try:
        r = requests.get(f"{API_BASE}/funding_monitor/pool", timeout=30)
        r.raise_for_status()
        js = r.json()
        return js.get("contracts", [])
    except Exception as e:
        logger.error(f"fetch_pool error: {e}")
        return []


def fetch_interval(interval: str) -> Dict[str, Any]:
    try:
        r = requests.get(f"{API_BASE}/funding_monitor/contracts-by-interval/{interval}", timeout=45)
        r.raise_for_status()
        return r.json().get("contracts", {})
    except Exception as e:
        logger.error(f"fetch_interval error: {e}")
        return {}


def trigger_refresh_candidates() -> str:
    try:
        r = requests.post(f"{API_BASE}/funding_monitor/refresh-candidates", timeout=120)
        r.raise_for_status()
        js = r.json()
        return js.get("message", "刷新已触发")
    except Exception as e:
        logger.error(f"trigger_refresh_candidates error: {e}")
        return f"刷新失败: {e}"


def trigger_refresh_latest_rates() -> str:
    try:
        r = requests.get(f"{API_BASE}/funding_monitor/latest-rates", params={"fast_mode": False, "cache_only": False}, timeout=120)
        r.raise_for_status()
        js = r.json()
        count = js.get("count", 0)
        return f"最新资金费率刷新完成，共处理 {count} 个合约"
    except Exception as e:
        logger.error(f"trigger_refresh_latest_rates error: {e}")
        return f"刷新失败: {e}"


def fetch_latest_detail(symbol: str) -> Optional[Dict[str, Any]]:
    # Query all-contracts (cached data for all contracts)
    try:
        r = requests.get(f"{API_BASE}/funding_monitor/all-contracts", timeout=45)
        if r.ok:
            data = r.json().get("contracts", {})
            if isinstance(data, dict) and symbol in data:
                return data[symbol]
    except Exception:
        pass

    # Fallback to monitor pool
    try:
        pool = fetch_pool()
        for item in pool:
            if item.get("symbol") == symbol:
                return item
    except Exception:
        pass
    return None


def format_pool_list(contracts: List[Dict[str, Any]], limit: int = 20) -> str:
    if not contracts:
        return "监控池为空"
    lines = ["📋 监控池（最多显示前{}个）:".format(limit)]
    shown = 0
    for c in contracts:
        try:
            symbol = c.get("symbol", "?")
            fr = float(c.get("funding_rate", 0.0))
            price = c.get("mark_price", 0)
            interval = c.get("funding_interval", "?")
            lines.append(f"• {symbol} | 费率: {fr:.4%} | 价格: {price} | {interval}")
            shown += 1
            if shown >= limit:
                break
        except Exception:
            continue
    lines.append("\n💡 提示：使用 /detail BTCUSDT 查看单个合约详情")
    return "\n".join(lines)


def format_interval_contracts(contracts: Dict[str, Any], interval: str) -> str:
    if not contracts:
        return f"{interval} 结算周期暂无合约"
    items = []
    for symbol, info in contracts.items():
        try:
            fr = float(info.get("funding_rate", 0.0))
            price = info.get("mark_price", 0)
            items.append(f"• {symbol} | 费率: {fr:.4%} | 价格: {price}")
        except Exception:
            continue
    text = f"{interval} 结算周期合约：\n" + "\n".join(items[:25])
    if len(items) > 25:
        text += f"\n\n... 还有 {len(items) - 25} 个合约"
    return text


def format_detail(info: Dict[str, Any], symbol: str) -> str:
    price = info.get("mark_price") or info.get("price") or 0
    fr_raw = info.get("funding_rate", info.get("current_funding_rate", 0))
    try:
        fr = float(fr_raw) if fr_raw is not None else 0.0
    except Exception:
        fr = 0.0
    next_time = info.get("funding_time") or info.get("next_funding_time") or ""
    interval = info.get("funding_interval", "?")
    last = info.get("last_updated") or info.get("timestamp") or ""
    return (
        f"合约: {symbol}\n"
        f"价格: {price}\n"
        f"资金费率: {fr:.4%}\n"
        f"下次结算: {next_time}\n"
        f"最近刷新: {last}"
    )


def handle_command(token: str, chat_id: str, text: str, reply_to_message_id: Optional[int] = None) -> None:
    t = text.strip()
    if t.startswith("/start") or t.startswith("/menu"):
        help_text = (
            "🤖 资金费率监控机器人\n\n"
            "可用命令：\n"
            "• /pool - 查看监控池\n"
            "• /detail BTCUSDT - 查看合约详情\n"
            "• /refresh - 刷新最新资金费率\n"
            "• /refresh_candidates - 刷新备选合约池\n"
            "• /interval1h - 查看1小时结算周期合约\n"
            "• /interval4h - 查看4小时结算周期合约\n"
            "• /interval8h - 查看8小时结算周期合约\n\n"
            "💡 提示：点击输入框左侧的⚡按钮查看所有命令"
        )
        send_message(token, chat_id, help_text, reply_to_message_id=reply_to_message_id)
        return
    if t.startswith("/id"):
        send_message(token, chat_id, f"当前 chat id: {chat_id}", reply_to_message_id=reply_to_message_id)
        return
    if t.startswith("/pool"):
        pool = fetch_pool()
        send_message(token, chat_id, format_pool_list(pool), reply_to_message_id=reply_to_message_id)
        return
    if t.startswith("/detail"):
        parts = t.split()
        if len(parts) >= 2:
            symbol = parts[1].upper()
            info = fetch_latest_detail(symbol)
            if info:
                send_message(token, chat_id, format_detail(info, symbol), reply_to_message_id=reply_to_message_id)
            else:
                send_message(token, chat_id, f"未找到合约 {symbol} 的信息", reply_to_message_id=reply_to_message_id)
        else:
            send_message(token, chat_id, "用法: /detail BTCUSDT", reply_to_message_id=reply_to_message_id)
        return
    if t.startswith("/refresh"):
        msg_text = trigger_refresh_latest_rates()
        send_message(token, chat_id, msg_text, reply_to_message_id=reply_to_message_id)
        return
    if t.startswith("/refresh_candidates"):
        msg_text = trigger_refresh_candidates()
        send_message(token, chat_id, msg_text, reply_to_message_id=reply_to_message_id)
        return
    if t.startswith("/interval1h"):
        contracts = fetch_interval("1h")
        text = format_interval_contracts(contracts, "1h")
        send_message(token, chat_id, text, reply_to_message_id=reply_to_message_id)
        return
    if t.startswith("/interval4h"):
        contracts = fetch_interval("4h")
        text = format_interval_contracts(contracts, "4h")
        send_message(token, chat_id, text, reply_to_message_id=reply_to_message_id)
        return
    if t.startswith("/interval8h"):
        contracts = fetch_interval("8h")
        text = format_interval_contracts(contracts, "8h")
        send_message(token, chat_id, text, reply_to_message_id=reply_to_message_id)
        return
    # default fall-through
    send_message(token, chat_id, "未知命令，发送 /start 查看可用命令", reply_to_message_id=reply_to_message_id)


def handle_callback_query(token: str, cq: Dict[str, Any]) -> None:
    # No longer using callback queries since we switched to command menu
    # This function is kept for compatibility but does nothing
    pass


def poll_loop() -> None:
    token, configured_chat = _get_token_and_chat()
    logger.info("Starting Telegram polling bot")
    offset = None  # last_update_id + 1
    while True:
        try:
            params: Dict[str, Any] = {"timeout": 50}
            if offset is not None:
                params["offset"] = offset
            r = requests.get(_tg_api(token, "getUpdates"), params=params, timeout=60)
            r.raise_for_status()
            updates = r.json().get("result", [])
            for upd in updates:
                offset = upd.get("update_id", 0) + 1

                # message
                if "message" in upd:
                    msg = upd["message"]
                    chat_id = str(msg.get("chat", {}).get("id"))
                    if configured_chat and chat_id != configured_chat:
                        continue
                    text = msg.get("text", "") or ""
                    mid = msg.get("message_id")
                    if text:
                        handle_command(token, chat_id, text, reply_to_message_id=mid)

                # callback query
                if "callback_query" in upd:
                    cq = upd["callback_query"]
                    chat_id = str(cq.get("message", {}).get("chat", {}).get("id"))
                    if configured_chat and chat_id != configured_chat:
                        continue
                    handle_callback_query(token, cq)

        except requests.ReadTimeout:
            # normal long-poll timeout
            continue
        except KeyboardInterrupt:
            logger.info("Polling stopped by user")
            break
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(3)


if __name__ == "__main__":
    poll_loop()


