# utils/allowed_symbols.py
# Lista blanca de símbolos permitidos - ACTUALIZADA 25 nov 2025
# Incluye versiones con y sin sufijo (.sml, .a, etc.) + todo lo que ya tenías

ALLOWED_SYMBOLS = {
    # FOREX - TODAS LAS VARIACIONES COMUNES
    "AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDUSD",
    "CADCHF", "CADJPY", "CHFJPY",
    "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY", "EURNOK", "EURNZD", "EURSEK", "EURUSD",
    "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPUSD", "GBPNZD",
    "NZDCAD", "NZDCHF", "NZDJPY", "NZDUSD",
    "USDCAD", "USDCHF", "USDJPY", "USDMXN", "USDNOK", "USDSEK", "USDSGD", "USDZAR",

    # Versiones con sufijos comunes de IC Markets (Raw Spread, etc.)
    "AUDUSD.sml", "EURGBP.sml", "EURUSD.sml", "GBPJPY.sml", "GBPUSD.sml", "USDJPY.sml",
    "AUDUSD.a",   "EURUSD.a",   "GBPUSD.a",   "USDJPY.a",
    "AUDUSD.pro", "EURUSD.pro", "GBPUSD.pro", "USDJPY.pro",

    # Otros forex exóticos y menores
    "XAGUSD", "SGDJPY", "USDCNH", "USDHKD", "EURCZK", "EURHUF", "EURPLN",
    "USDCZK", "USDHUF", "USDPLN", "ZARJPY", "TRYJPY", "EURTRY", "USDTRY",
    "EURDKK", "USDDKK", "GBPGBX", "GBXUSD",

    # COMMODITIES
    "COPPER", "NATGAS", "SUGAR", "WHEAT", "CORN", "SOYBN",
    "UKOIL.sml", "USOIL.sml", "UKOIL", "USOIL", "XBRUSD", "WTIUSD",

    # INDICES
    "EU50", "HK50", "JP225", "NL25", "UK100", "US100", "US2000", "US30", "US500",
    "CH20", "CHINAH", "ES35", "DE40", "AU200", "CN50", "FR40", "SG30",

    # CRYPTO
    "ADAUSD", "BCHUSD", "BNBUSD", "BTCUSD", "DOGEUSD", "DOTUSD", "ETHUSD",
    "LINKUSD", "LTCUSD", "MATICUSD", "AVAXUSD", "UNIUSD", "XTZUSD", "XLMUSD",
    "EOSUSD", "KSMUSD", "GLMRUSD", "SOLUSD",
    "BCHJPY", "BTCJPY", "ETHJPY", "LTCJPY",

    # METALES
    "XAUUSD", "XAUUSD.sml", "XAGUSD.sml",

    # ACCIONES CFD
    "AAPL_CFD.US", "AMZN_CFD.US", "TSLA_CFD.US", "NVDA_CFD.US", "GOOGL_CFD.US",
    "META_CFD.US", "MSFT_CFD.US", "NFLX_CFD.US",

    # BANCOS Y OTROS
    "BARC_CFD.UK", "LLOY_CFD.UK", "BBVA_CFD.ES", "DANSKE_CFD.DK"
}

def is_symbol_allowed(symbol: str) -> bool:
    """
    Verifica si el símbolo está permitido para el bot.
    Ahora acepta tanto con sufijo como sin sufijo.
    """
    return symbol in ALLOWED_SYMBOLS