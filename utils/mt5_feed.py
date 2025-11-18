# utils/feed_selector.py
import MetaTrader5 as mt5
from utils.mt5_connector import is_market_open, get_candles

class MT5Feed:
    def get_candles(self, pair, timeframe, n):
        return get_candles(pair, timeframe, n)
    
    def is_market_open(self, pair):
        return is_market_open(pair)
    
    def get_current_price(self, pair):
        if not is_market_open(pair):
            return None, None
        tick = mt5.symbol_info_tick(pair)
        if tick:
            return tick.bid, tick.ask
        return None, None
    
    def get_symbol_info(self, pair):
        return mt5.symbol_info(pair)

def get_feed(settings):
    broker = settings.get("BROKER", "mt5").lower()
    if broker == "mt5":
        return MT5Feed()
    raise ValueError(f"Broker no soportado: {broker}")