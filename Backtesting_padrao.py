import requests
import pandas as pd
import numpy as np

# Configurações
symbol = "SBTCSUSDT"  # Par de negociação
initial_balance = 10000  # Saldo inicial em USDT
tamanho_ordem = 0.001  # Quantidade de BTC comprada/vendida por operação

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
        return df
    else:
        print("Erro ao buscar histórico:", response.text)
        return None

# 🔹 Sistema de envio de ordens
def executar_ordem(df, initial_balance, tamanho_ordem, estrategia):
    btc_balance = 0
    usd_balance = initial_balance
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
        ordem = estrategia(df, i)
        
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
                    usd_balance += (entry_price - take_profit) * tamanho_ordem
                    btc_balance = 0
                    win_trades += 1
                    operations.append(("WIN (TP)", take_profit, last_row["timestamp"]))
                    position_open = False
                elif last_row["high"] >= stop_loss:
                    usd_balance += (entry_price - stop_loss) * tamanho_ordem
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
            usd_balance += (entry_price - df.iloc[-1]["close"]) * tamanho_ordem
        btc_balance = 0
        operations.append(("FECHAMENTO FORÇADO", df.iloc[-1]["close"], df.iloc[-1]["timestamp"]))
        position_open = False

    return operations, usd_balance, win_trades, loss_trades

# 🚀 Execute o backtest
df = get_historical_data(symbol)
if df is not None:
    def estrategia_exemplo(df, i):
        # Exemplo de estratégia genérica (deve ser substituída por lógica real)
        if df.iloc[i]["close"] > df.iloc[i - 1]["close"]:
            return "BUY"
        elif df.iloc[i]["close"] < df.iloc[i - 1]["close"]:
            return "SELL"
        return None
    
    operations, final_balance, win_trades, loss_trades = executar_ordem(df, initial_balance, tamanho_ordem, estrategia_exemplo)
    print(f"\n📊 **Resultado do Backtesting** 📊")
    print(f"🔹 Saldo Final: ${final_balance:.2f}")
    print(f"✅ Acertos (Take Profit): {win_trades}")
    print(f"❌ Erros (Stop Loss): {loss_trades}")
    for op in operations:
        print(f"{op[0]} | Preço: {op[1]:.2f} | Data: {op[2]}")
