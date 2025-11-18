# utils/allowed_symbols.py
ALLOWED_SYMBOLS = {
    # FOREX
    "XAGUSD", "AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "CADCHF", "CADJPY", "CHFJPY",
    "EURAUD", "EURCAD", "EURCHF", "EURJPY", "EURNOK", "EURNZD", "EURSEK",
    "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD", "NZDCAD", "NZDCHF", "NZDJPY", "NZDUSD",
    "SGDJPY", "USDCAD", "USDCHF", "USDCNH", "USDHKD", "USDMXN", "USDNOK", "USDSEK",
    "USDSGD", "USDZAR", "EURCZK", "EURHUF", "EURPLN", "USDCZK", "USDHUF", "USDPLN",
    "ZARJPY", "TRYJPY", "EURTRY", "USDTRY", "EURDKK", "USDDKK", "GBPGBX", "GBXUSD",
    "AUDUSD.sml", "EURGBP.sml", "EURUSD.sml", "GBPJPY.sml", "GBPUSD.sml", "USDJPY.sml",

    # COMMODITIES
    "COPPER", "NATGAS", "SUGAR", "WHEAT", "CORN", "SOYBN", "UKOIL.sml", "USOIL.sml",

    # INDICES
    "EU50", "HK50", "JP225", "NL25", "UK100", "US100", "US2000", "US30", "US500",
    "CH20", "CHINAH", "ES35", "DE40", "AU200", "CN50", "FR40", "SG30",

    # CRYPTO
    "ADAUSD", "BCHUSD", "BNBUSD", "BTCUSD", "DOGEUSD", "DOTUSD", "ETHUSD",
    "LINKUSD", "LTCUSD", "MATICUSD", "AVAXUSD", "UNIUSD", "XTZUSD", "XLMUSD",
    "EOSUSD", "KSMUSD", "GLMRUSD", "SOLUSD",
    "BCHJPY", "BTCJPY", "ETHJPY", "LTCJPY",

    # METALES
    "XAUUSD.sml",

    # ACCIONES (solo ejemplos, hay muchas más)
    "AAPL_CFD.US", "AMZN_CFD.US", "TSLA_CFD.US", "NVDA_CFD.US", "GOOGL_CFD.US",
    "META_CFD.US", "MSFT_CFD.US", "NFLX_CFD.US",

    # BANCOS
    "BARC_CFD.UK", "LLOY_CFD.UK", "BBVA_CFD.ES", "DANSKE_CFD.DK"
}

def is_symbol_allowed(symbol: str) -> bool:
    """Verifica si el símbolo está permitido."""
    return symbol in ALLOWED_SYMBOLS