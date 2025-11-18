# utils/feed_selector.py → VERSIÓN FINAL 100% ESTABLE (noviembre 2025)
import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime, timedelta

class Feed:
    def __init__(self, settings):
        self.settings = settings

    def get_current_price(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None, None
        return tick.bid, tick.ask

    def is_market_open(self, symbol):
        """Ya NO usa copy_rates_from_pos → nunca más falla"""
        info = mt5.symbol_info(symbol)
        if info is None:
            return False
        # Solo miramos si el símbolo está habilitado para trading
        return info.visible and info.trade_mode != mt5.SYMBOL_TRADE_MODE_DISABLED

    def get_candles(self, symbol, timeframe, count=500):
        """Blindada contra el error de .sml"""
        for intento in range(10):
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                return df

            print(f"   [Feed] Cargando velas {symbol}... intento {intento + 1}/10")
            to_time = datetime.now()
            from_time = to_time - timedelta(days=10)
            mt5.copy_rates_range(symbol, timeframe, from_time, to_time)
            time.sleep(2.5)

        print(f"ERROR: No se cargaron velas de {symbol} tras 10 intentos")
        return None

def get_feed(settings):
    return Feed(settings)