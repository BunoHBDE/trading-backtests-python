import requests
import pandas as pd
import numpy as np

# Configurações
symbol = "SBTCSUSDT"  # Par de negociação
initial_balance = 10000  # Saldo inicial em USDT
size = 0.001  # Quantidade de BTC comprada/vendida por operação

# 🔹 Baixar histórico da Bitget
def get_historical_data(symbol):
    params = {
        "symbol": symbol,
        "productType": "susdt-futures",
        "granularity": "1m",  # Timeframe de 1 minuto
        "limit": "200"  # Pegamos o máximo de dados possíveis
    }

    response = requests.get("https://api.bitget.com/api/v2/mix/market/history-candles", params=params)

    if response.status_code == 200:
        data = response.json()["data"]
        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "quote_volume"])
        
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)

        # Cálculo dos Indicadores Técnicos
        df["MME9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["MME21"] = df["close"].ewm(span=21, adjust=False).mean()

        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # OBV
        df["OBV"] = np.where(df["close"] > df["close"].shift(1), df["volume"], 
                            np.where(df["close"] < df["close"].shift(1), -df["volume"], 0)).cumsum()

        # ADX
        df["TR"] = np.maximum(df["high"] - df["low"], 
                              np.maximum(abs(df["high"] - df["close"].shift(1)), 
                                         abs(df["low"] - df["close"].shift(1))))
        df["ATR"] = df["TR"].rolling(window=14, min_periods=1).mean()

        df["DM+"] = np.where((df["high"] - df["high"].shift(1)) > (df["low"].shift(1) - df["low"]),
                              np.maximum(df["high"] - df["high"].shift(1), 0), 0)
        df["DM-"] = np.where((df["low"].shift(1) - df["low"]) > (df["high"] - df["high"].shift(1)),
                              np.maximum(df["low"].shift(1) - df["low"], 0), 0)

        df["DI+"] = 100 * (df["DM+"].rolling(window=14, min_periods=1).mean() / df["ATR"])
        df["DI-"] = 100 * (df["DM-"].rolling(window=14, min_periods=1).mean() / df["ATR"])
        df["DX"] = 100 * (abs(df["DI+"] - df["DI-"]) / (df["DI+"] + df["DI-"]))

        df["ADX"] = df["DX"].rolling(window=14, min_periods=1).mean()
        df["ADX"] = df["ADX"].fillna(0) 
    
        return df
    else:
        print("Erro ao buscar histórico:", response.text)
        return None

# 🔹 Simulação do Backtesting
def backtest(df, initial_balance, size):
    btc_balance = 0
    usd_balance = initial_balance
    operations = []
    position_open = False
    entry_price = 0
    stop_loss = 0
    take_profit = 0
    trade_type = None  # Define se é "long" ou "short"

    win_trades = 0
    loss_trades = 0

    for i in range(1, len(df)):
        last_row = df.iloc[i]
        previous_row = df.iloc[i - 1]

        buy_signal_tendencia = (
            (previous_row["MME9"] < previous_row["MME21"]) & 
            (last_row["MME9"] > last_row["MME21"]) &
            (last_row["ADX"] > 15) & 
            (last_row["OBV"] > previous_row["OBV"])
        )

        sell_signal_tendencia = (
            (previous_row["MME9"] > previous_row["MME21"]) & 
            (last_row["MME9"] < last_row["MME21"]) &
            (last_row["ADX"] > 15) & 
            (last_row["OBV"] < previous_row["OBV"])
        )

        price = last_row["close"]

        # 🔹 Verifica Stop Loss e Take Profit corretamente para Long e Short
        if position_open:
            if trade_type == "long":
                if last_row["high"] >= take_profit:  # TP atingido para compra
                    usd_balance = btc_balance * take_profit
                    btc_balance = 0
                    win_trades += 1
                    operations.append(("WIN (TP)", take_profit, last_row["timestamp"]))
                    print(f"✅ 🎯 Take Profit atingido na COMPRA! Fechando posição em {take_profit:.2f}")
                    position_open = False

                elif last_row["low"] <= stop_loss:  # SL atingido para compra
                    usd_balance = btc_balance * stop_loss
                    btc_balance = 0
                    loss_trades += 1
                    operations.append(("LOSS (SL)", stop_loss, last_row["timestamp"]))
                    print(f"🚨 Stop Loss atingido na COMPRA! Fechando posição em {stop_loss:.2f}")
                    position_open = False

            elif trade_type == "short":
                if last_row["low"] <= take_profit:  # TP atingido para venda
                    usd_balance += (entry_price - take_profit) * size  # ❗️ Correção para Shorts
                    btc_balance = 0
                    win_trades += 1
                    operations.append(("WIN (TP)", take_profit, last_row["timestamp"]))
                    print(f"✅ 🎯 Take Profit atingido na VENDA! Fechando posição em {take_profit:.2f}")
                    position_open = False

                elif last_row["high"] >= stop_loss:  # SL atingido para venda
                    usd_balance += (entry_price - stop_loss) * size  # ❗️    Correção para Shorts
                    btc_balance = 0
                    loss_trades += 1
                    operations.append(("LOSS (SL)", stop_loss, last_row["timestamp"]))
                    print(f"🚨 Stop Loss atingido na VENDA! Fechando posição em {stop_loss:.2f}")
                    position_open = False

        # 🔹 Entrada na Compra (Long) mercado de tendencia
        if buy_signal_tendencia and usd_balance > 0 and not position_open:
            btc_balance = usd_balance / price
            usd_balance = 0
            entry_price = price
            stop_loss = price * 0.995  # SL -0,5% para compra
            take_profit = price * 1.01  # TP +1 para compra
            position_open = True
            trade_type = "long"
            operations.append(("BUY", price, last_row["timestamp"]))
            print(f"✅ 🔵 COMPRA: {price:.2f} | Data: {last_row['timestamp']}")

        # 🔹 Entrada na Venda (Short) mercado de tendencia
        elif sell_signal_tendencia and usd_balance > 0 and not position_open:
            entry_price = price  # Registra o preço da venda
            stop_loss = price * 1.005  # SL +1% para venda
            take_profit = price * 0.99  # TP -1.5% para venda
            position_open = True
            trade_type = "short"
            operations.append(("SELL", price, last_row["timestamp"]))
            print(f"✅ 🔴 VENDA: {price:.2f} | Data: {last_row['timestamp']}")

    # 🔹 Fechar posição se ainda estiver aberta no final do histórico
    if position_open:
        if trade_type == "long":
            usd_balance = btc_balance * df.iloc[-1]["close"]
        elif trade_type == "short":
            usd_balance += (entry_price - df.iloc[-1]["close"]) * size  # ❗️ Correção para Shorts
        btc_balance = 0
        operations.append(("FECHAMENTO FORÇADO", df.iloc[-1]["close"], df.iloc[-1]["timestamp"]))
        print(f"⚠️ Fechando posição automaticamente no final do backtest: {df.iloc[-1]['close']:.2f}")
        position_open = False

    return operations, usd_balance, win_trades, loss_trades

# 🚀 Execute o backtest
df = get_historical_data(symbol)
if df is not None:
    operations, final_balance, win_trades, loss_trades = backtest(df, initial_balance, size)

    print(f"\n📊 **Resultado do Backtesting** 📊")
    print(f"🔹 Saldo Final: ${final_balance:.2f}")
    print(f"✅ Acertos (Take Profit): {win_trades}")
    print(f"❌ Erros (Stop Loss): {loss_trades}")

    for op in operations:
        print(f"{op[0]} | Preço: {op[1]:.2f} | Data: {op[2]}")
