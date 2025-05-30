import requests
import pandas as pd
import numpy as np

# 🔹 Configurações da Bitget
API_URL = "https://api.bitget.com/api/v2/mix/market/history-candles"
SYMBOL = "SBTCSUSDT"  # Par de negociação
GRANULARITY = "1m"  # Timeframe de 1 minuto
LIMIT = "200"  # Número máximo de candles históricos
INITIAL_BALANCE = 10000  # Saldo inicial em USDT
TAMANHO_ORDEM = 0.005  # Quantidade de BTC comprada/vendida por operação

# 🔹 Função para obter dados históricos da Bitget
def get_historical_data():
    params = {
        "symbol": SYMBOL,
        "productType": "usdt-futures",
        "granularity": GRANULARITY,
        "limit": LIMIT
    }
    response = requests.get(API_URL, params=params)
    
    if response.status_code == 200:
        data = response.json()["data"]
        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "quote_volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df
    else:
        print("Erro ao buscar histórico:", response.text)
        return None

# 🔹 Funções para calcular indicadores técnicos
def calcular_adx(df, periodo=14):
    df["high_diff"] = df["high"].diff()
    df["low_diff"] = df["low"].diff()
    
    df["+DM"] = ((df["high_diff"] > df["low_diff"]) & (df["high_diff"] > 0)) * df["high_diff"]
    df["-DM"] = ((df["low_diff"] > df["high_diff"]) & (df["low_diff"] > 0)) * df["low_diff"]

    df["+DI"] = 100 * (df["+DM"].ewm(span=periodo, adjust=False).mean() / df["close"])
    df["-DI"] = 100 * (df["-DM"].ewm(span=periodo, adjust=False).mean() / df["close"])
    
    df["DX"] = 100 * abs(df["+DI"] - df["-DI"]) / (df["+DI"] + df["-DI"])
    df["ADX"] = df["DX"].ewm(span=periodo, adjust=False).mean()
    df["adx_delta"] = df["ADX"].diff()
    return df

def calcular_trix(df, periodo=18):
    df["ema1"] = df["close"].ewm(span=periodo, adjust=False).mean()
    df["ema2"] = df["ema1"].ewm(span=periodo, adjust=False).mean()
    df["ema3"] = df["ema2"].ewm(span=periodo, adjust=False).mean()
    df["trix"] = df["ema3"].pct_change() * 100
    df["trix_delta"] = df["trix"].diff()
    return df

def calcular_estocastico(df, periodo=14):
    df["low_min"] = df["low"].rolling(window=periodo).min()
    df["high_max"] = df["high"].rolling(window=periodo).max()
    df["%K"] = ((df["close"] - df["low_min"]) / (df["high_max"] - df["low_min"])) * 100
    df["%D"] = df["%K"].rolling(window=3).mean()
    return df

# 🔹 Estratégia de trading baseada nos indicadores
def estrategia_trix_estocastico(df, i):
    if i < 14:
        return None
    
    trix = df.iloc[i]["trix"]
    k = df.iloc[i]["%K"]
    trix_delta = df.iloc[i]["trix_delta"]
    adx = df.iloc[i]["ADX"]
    adx_delta = df.iloc[i]["adx_delta"]

    if trix > 0 and k < 30 and adx > 20:
        return "BUY"
    elif trix < 0 and k > 70 and adx > 20:
        return "SELL"
    return None

# 🔹 Função para executar o backtesting
def executar_backtesting(df):
    btc_balance = 0
    usd_balance = INITIAL_BALANCE
    operations = []
    position_open = False
    entry_price = 0
    stop_loss = 0
    take_profit = 0
    trade_type = None
    win_trades = 0
    loss_trades = 0

    for i in range(1, len(df)):
        last_row = df.iloc[i]
        price = last_row["close"]
        ordem = estrategia_trix_estocastico(df, i)
        
        # Verifica se há posição aberta e aplica Stop Loss ou Take Profit
        if position_open:
            if trade_type == "long":
                if last_row["high"] >= take_profit:
                    usd_balance = btc_balance * take_profit
                    btc_balance = 0
                    win_trades += 1
                    operations.append(("WIN (TP)", take_profit, last_row["timestamp"]))
                    position_open = False
                elif last_row["low"] <= stop_loss:
                    usd_balance = btc_balance * stop_loss
                    btc_balance = 0
                    loss_trades += 1
                    operations.append(("LOSS (SL)", stop_loss, last_row["timestamp"]))
                    position_open = False
            elif trade_type == "short":
                if last_row["low"] <= take_profit:
                    usd_balance += (entry_price - take_profit) * TAMANHO_ORDEM
                    btc_balance = 0
                    win_trades += 1
                    operations.append(("WIN (TP)", take_profit, last_row["timestamp"]))
                    position_open = False
                elif last_row["high"] >= stop_loss:
                    usd_balance += (entry_price - stop_loss) * TAMANHO_ORDEM
                    btc_balance = 0
                    loss_trades += 1
                    operations.append(("LOSS (SL)", stop_loss, last_row["timestamp"]))
                    position_open = False

        # Executa novas ordens se não houver posição aberta
        if not position_open:
            if ordem == "BUY":
                btc_balance = usd_balance / price
                usd_balance = 0
                entry_price = price
                stop_loss = price * 0.995
                take_profit = price * 1.01
                position_open = True
                trade_type = "long"
                operations.append(("BUY", price, last_row["timestamp"]))
            elif ordem == "SELL":
                entry_price = price
                stop_loss = price * 1.005
                take_profit = price * 0.99
                position_open = True
                trade_type = "short"
                operations.append(("SELL", price, last_row["timestamp"]))

    # Fechar posição se ainda estiver aberta no final do histórico
    if position_open:
        if trade_type == "long":
            usd_balance = btc_balance * df.iloc[-1]["close"]
        elif trade_type == "short":
            usd_balance += (entry_price - df.iloc[-1]["close"]) * TAMANHO_ORDEM
        btc_balance = 0
        operations.append(("FECHAMENTO FORÇADO", df.iloc[-1]["close"], df.iloc[-1]["timestamp"]))
        position_open = False

    return operations, usd_balance, win_trades, loss_trades

# 🚀 Rodando o backtest com dados da Bitget
df = get_historical_data()

if df is not None:
    df = calcular_trix(df)
    df = calcular_estocastico(df)
    df = calcular_adx(df)

    operations, final_balance, win_trades, loss_trades = executar_backtesting(df)

    print(f"\n📊 **Resultado do Backtesting** 📊")
    print(f"🔹 Saldo Final: ${final_balance:.2f}")
    print(f"✅ Acertos (Take Profit): {win_trades}")
    print(f"❌ Erros (Stop Loss): {loss_trades}")
