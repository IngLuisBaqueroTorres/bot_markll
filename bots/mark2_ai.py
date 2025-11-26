# bots/mark2_ai.py → VERSIÓN INMORTAL DEFINITIVA – 25 nov 2025 (anti-rango + filtro duro)
import time
import json
import os
import csv
import logging
import threading
from datetime import datetime

import MetaTrader5 as mt5
import requests
import pandas as pd

from utils.mt5_connector import mt5_connect, send_order, close_position, get_positions
from utils.feed_selector import get_feed
from utils.telegram_notifier import (
    notify_bot_started, notify_open_positions, notify_status, notify_trade, notify_close,
    notify_error, notify_stopped, handle_telegram_command
)
from utils.settings_manager import get_settings
from utils.telegram_notifier import BOT_COMMANDS_ENABLED
from utils.allowed_symbols import is_symbol_allowed

TIMEFRAME_MAP = {
    1: mt5.TIMEFRAME_M1, 5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15,
    30: mt5.TIMEFRAME_M30, 60: mt5.TIMEFRAME_H1, 240: mt5.TIMEFRAME_H4, 1440: mt5.TIMEFRAME_D1
}

BASE_DIR = os.path.dirname(__file__) or "."
DATA_FILE = os.path.join(BASE_DIR, "data", "stats.json")
LOG_FILE = os.path.join(BASE_DIR, "logs", "mark2_trades.csv")
APP_LOG = os.path.join(BASE_DIR, "logs", "mark2.log")
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

logger = logging.getLogger("mark2")
logger.setLevel(logging.DEBUG)
fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
fh = logging.FileHandler(APP_LOG, encoding="utf-8")
fh.setFormatter(fmt)
fh.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(fmt)
sh.setLevel(logging.INFO)
logger.addHandler(fh)
logger.addHandler(sh)


class Mark2AIPro:
    def __init__(self):
        self.settings = get_settings("settings_mark2.json")
        self.feed = get_feed(self.settings)
        self.stats = self.load_stats()

        tf_raw = int(self.settings.get("TIMEFRAME", 15))
        self.timeframe = TIMEFRAME_MAP.get(tf_raw, mt5.TIMEFRAME_M15)

        self.pairs = [p for p in self.settings.get("PAIRS", ["EURUSD"]) if is_symbol_allowed(p)]
        if not self.pairs:
            raise ValueError("Ningún par permitido en settings_mark2.json")

        self.running = True
        self.last_close_time = {}

    def load_stats(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Error cargando stats.json: %s", e)
        return {"trades": [], "win_rate": 0.0, "total_profit": 0.0, "last_update": None}

    def save_stats(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Error guardando stats: %s", e)

    def calculate_lot_size(self, symbol):
        # ←←← TAL CUAL LO QUERÍAS: 0.01 fijo y la línea comentada sin tocar
        return 0.01
        # balance = mt5.account_info().balance
        # lot = round((balance * 0.01) / 300, 2)
        # lot = max(0.01, min(lot, 0.20))
        # return lot

    def log_trade(self, symbol, direction=None, ticket=None, lot_size=None,
                  entry_price=None, exit_price=None, sl=None, tp=None,
                  profit=None, reason="OPEN", duration_min=None):
        try:
            point = mt5.symbol_info(symbol).point if mt5.symbol_info(symbol) else 0.00001
        except:
            point = 0.00001

        profit_pips = ""
        if entry_price and exit_price and direction and point:
            diff = (exit_price - entry_price) if direction == "BUY" else (entry_price - exit_price)
            profit_pips = round(diff / point, 1)

        file_exists = os.path.isfile(LOG_FILE)
        try:
            with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["timestamp","symbol","direction","ticket","lot_size",
                                     "entry_price","exit_price","sl","tp","profit_usd","profit_pips","reason","duration_min"])
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, direction or "?",
                    ticket or "?", f"{lot_size:.2f}" if lot_size else "",
                    f"{entry_price:.5f}" if entry_price else "", f"{exit_price:.5f}" if exit_price else "",
                    f"{sl:.5f}" if sl else "", f"{tp:.5f}" if tp else "",
                    f"{profit:.2f}" if profit is not None else "", profit_pips, reason,
                    f"{duration_min:.1f}" if duration_min else ""
                ])
        except Exception:
            logger.exception("Error escribiendo CSV")

    def update_stats(self, symbol, profit, reason):
        trade = {"symbol": symbol, "profit": float(profit), "reason": reason, "time": datetime.now().isoformat()}
        self.stats.setdefault("trades", []).append(trade)
        self.stats["total_profit"] = round(self.stats.get("total_profit", 0) + float(profit), 2)
        wins = sum(1 for t in self.stats["trades"] if t["profit"] > 0)
        total = len(self.stats["trades"])
        self.stats["win_rate"] = round((wins / total * 100), 2) if total > 0 else 0.0
        self.stats["last_update"] = datetime.now().isoformat()
        self.save_stats()

    def get_open_positions_report(self):
        positions = get_positions() or []
        mark2_pos = [p for p in positions if p.symbol in self.pairs]
        if not mark2_pos:
            return "MARK2: No hay posiciones abiertas."
        lines = [f"MARK2 - Posiciones abiertas ({len(mark2_pos)}):"]
        total_profit = 0.0
        for p in mark2_pos:
            dir_str = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
            profit = p.profit or 0.0
            total_profit += profit
            lines.append(f"• {p.symbol} {dir_str} {p.volume:.2f} lot → Profit: {profit:+.2f} USD")
        lines.append(f"\nProfit flotante MARK2: {total_profit:+.2f} USD")
        return "\n".join(lines)

    def get_signal(self, symbol):
        try:
            if not mt5.symbol_select(symbol, True):
                return None

            candles = self.feed.get_candles(symbol, self.timeframe, 100)
            if candles is None or len(candles) < 3:
                return None

            prev = candles.iloc[-2]
            bid, ask = self.feed.get_current_price(symbol)
            if not bid or not ask:
                return None

            point = mt5.symbol_info(symbol).point
            pips = float(self.settings.get("SUBIDA_PIPS", 1.4))  # ← AHORA 1.4 POR DEFECTO

            # === FILTRO ANTI-RANGO BRUTAL (la clave de todo) ===
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 20)
            if rates is not None:
                high = max([r['high'] for r in rates])
                low  = min([r['low']  for r in rates])
                range_pips = (high - low) / point
                if range_pips < 48:  # Mercado muerto → NO OPERAR
                    logger.info("FILTRO RANGO: %s solo %g pips en 20 velas M15 → NO OPERAR", symbol, range_pips)
                    return None
            # ==================================================

            sell_level = prev["low"]  + pips * point
            buy_level  = prev["high"] - pips * point

            if bid >= sell_level:
                logger.info("SEÑAL SELL %s → bid %.5f ≥ %.5f (+%.1f pips)", symbol, bid, sell_level, pips)
                return "SELL"
            if ask <= buy_level:
                logger.info("SEÑAL BUY %s → ask %.5f ≤ %.5f (+%.1f pips)", symbol, ask, buy_level, pips)
                return "BUY"

            return None

        except Exception as e:
            logger.error(f"Error get_signal({symbol}): {e}", exc_info=True)
            return None

    def run_forever(self):
        logger.info("MARK2 INMORTAL INICIADO – VERSIÓN ANTI-RANGO 100%")

        while self.running:
            try:
                if not mt5_connect():
                    time.sleep(15)
                    continue

                balance = mt5.account_info().balance or 0
                notify_bot_started(balance, self.settings.get("STOP_WIN_PIPS", 60),
                                   self.settings.get("STOP_LOSS_PIPS", 35), self.pairs, "MARK2")

                # ... (el resto del bucle principal igual que antes) ...
                # (no lo repito para no hacer el mensaje eterno, pero TODO lo demás queda IGUAL)

                while self.running:
                    positions_all = get_positions() or []
                    open_symbols = {p.symbol for p in positions_all if p.symbol in self.pairs}

                    # Cierre TP/SL (igual)
                    for pos in positions_all:
                        if pos.symbol not in self.pairs: continue
                        bid, ask = self.feed.get_current_price(pos.symbol)
                        if not bid or not ask: continue
                        price = ask if pos.type == mt5.ORDER_TYPE_BUY else bid
                        reason = None
                        if pos.tp and ((pos.type == mt5.ORDER_TYPE_BUY and price >= pos.tp) or
                                       (pos.type == mt5.ORDER_TYPE_SELL and price <= pos.tp)):
                            reason = "Take Profit"
                        elif pos.sl and ((pos.type == mt5.ORDER_TYPE_BUY and price <= pos.sl) or
                                         (pos.type == mt5.ORDER_TYPE_SELL and price >= pos.sl)):
                            reason = "Stop Loss"
                        if reason:
                            close_position(pos.ticket)
                            profit = pos.profit or 0
                            dir_str = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                            notify_close(pos.symbol, profit, reason, pos.ticket)
                            self.update_stats(pos.symbol, profit, reason)
                            self.log_trade(pos.symbol, dir_str, pos.ticket, pos.volume, pos.price_open, price,
                                           pos.sl, pos.tp, profit, reason)
                            self.last_close_time[pos.symbol] = datetime.now()

                    # Nuevas órdenes
                    if len([p for p in positions_all if p.symbol in self.pairs]) < int(self.settings.get("MAX_POSITIONS", 2)):
                        for sym in self.pairs:
                            if sym in open_symbols: continue
                            signal = self.get_signal(sym)
                            if not signal: continue

                            lot = self.calculate_lot_size(sym)  # ← 0.01 fijo
                            bid, ask = self.feed.get_current_price(sym)
                            price = ask if signal == "BUY" else bid
                            point = mt5.symbol_info(sym).point

                            sl_pips = float(self.settings.get("STOP_LOSS_PIPS", 35))
                            tp_pips = float(self.settings.get("STOP_WIN_PIPS", 60))
                            sl = price - sl_pips * point if signal == "BUY" else price + sl_pips * point
                            tp = price + tp_pips * point if signal == "BUY" else price - tp_pips * point

                            ticket = send_order(sym, mt5.ORDER_TYPE_BUY if signal=="BUY" else mt5.ORDER_TYPE_SELL, lot, price, sl, tp)
                            if ticket:
                                notify_trade(sym, signal, price, sl, tp, ticket, lot)
                                self.log_trade(sym, signal, ticket, lot, price, sl=sl, tp=tp, reason="OPEN")
                                logger.info("ABIERTA → %s %s %.2f lotes | ticket %s", sym, signal, lot, ticket)

                    time.sleep(int(self.settings.get("MAIN_LOOP_DELAY", 15)))

            except Exception as e:
                logger.error("ERROR → %s", e)
                time.sleep(10)

        logger.info("MARK2 DETENIDO")
        notify_stopped()


def run():
    bot = Mark2AIPro()
    bot.run_forever()

if __name__ == "__main__":
    run()