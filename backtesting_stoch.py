import requests
import pandas as pd
import numpy as np

# Configurações
symbol = "SBTCSUSDT"  # Par de negociação
initial_balance = 1000  # Saldo inicial em USDT
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

# 🔹 Calcula o indicador Estocástico
def calcular_estocastico(df, periodo=14):
    df["low_min"] = df["low"].rolling(window=periodo).min()
    df["high_max"] = df["high"].rolling(window=periodo).max()
    df["%K"] = ((df["close"] - df["low_min"]) / (df["high_max"] - df["low_min"])) * 100
    df["%D"] = df["%K"].rolling(window=3).mean()
    return df

# 🔹 Estratégia com Estocástico
def estrategia_estocastica(df, i):
    if i < 14:
        return None
    
    if df.iloc[i]["%K"] > 80 and df.iloc[i]["%D"] > 80:
        return "SELL"
    elif df.iloc[i]["%K"] < 20 and df.iloc[i]["%D"] < 20:
        return "BUY"
    return None

# 🔹 Sistema de execução de ordens
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
    win_trades_tp = 0
    win_trades_reverse = 0
    loss_trades = 0
    highest_balance = initial_balance
    max_drawdown = 0
    
    for i in range(1, len(df)):
        last_row = df.iloc[i]
        price = last_row["close"]
        ordem = estrategia(df, i)
        
        # Verifica Stop Loss ou Take Profit
        if position_open:
            if trade_type == "long":
                if ordem == "SELL":
                    usd_balance = btc_balance * price
                    btc_balance = 0
                    win_trades += 1
                    win_trades_reverse += 1
                    operations.append(("WIN (REVERSE)", price, last_row["timestamp"]))
                    position_open = False
                    
                if last_row["high"] >= take_profit:
                    usd_balance = btc_balance * take_profit
                    btc_balance = 0
                    win_trades += 1
                    win_trades_tp += 1
                    operations.append(("WIN (TP)", take_profit, last_row["timestamp"]))
                    position_open = False

                elif last_row["low"] <= stop_loss:
                    usd_balance = btc_balance * stop_loss
                    btc_balance = 0
                    loss_trades += 1
                    operations.append(("LOSS (SL)", stop_loss, last_row["timestamp"]))
                    position_open = False

            elif trade_type == "short":
                if ordem == "BUY":
                    usd_balance += (entry_price - price) * tamanho_ordem
                    btc_balance = 0
                    win_trades += 1
                    win_trades_reverse += 1
                    operations.append(("WIN (Reverse)", price, last_row["timestamp"]))
                    position_open = False

                if last_row["low"] <= take_profit:
                    usd_balance += (entry_price - take_profit) * tamanho_ordem
                    btc_balance = 0
                    win_trades += 1
                    win_trades_tp += 1
                    operations.append(("WIN (TP)", take_profit, last_row["timestamp"]))
                    print(usd_balance)
                    
                    position_open = False
                    
                elif last_row["high"] >= stop_loss:
                    usd_balance += (entry_price - stop_loss) * tamanho_ordem
                    btc_balance = 0
                    loss_trades += 1
                    operations.append(("LOSS (SL)", stop_loss, last_row["timestamp"]))
                    position_open = False
        
        # Executa novas ordens
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
        
        highest_balance = max(highest_balance, usd_balance)
        drawdown = (highest_balance - usd_balance) / highest_balance if highest_balance > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)
    
    # Fechar posição no final do histórico
    if position_open:
        usd_balance = btc_balance * df.iloc[-1]["close"] if trade_type == "long" else usd_balance + (entry_price - df.iloc[-1]["close"]) * tamanho_ordem
        btc_balance = 0
        operations.append(("FECHAMENTO FORÇADO", df.iloc[-1]["close"], df.iloc[-1]["timestamp"]))
        position_open = False
    
    return operations, usd_balance, win_trades, win_trades_tp, win_trades_reverse, loss_trades, max_drawdown

# 🚀 Executar Backtest
df = get_historical_data(symbol)
if df is not None:
    df = calcular_estocastico(df)
    operations, final_balance, win_trades, win_trades_tp, win_trades_reverse, loss_trades, max_drawdown = executar_ordem(df, initial_balance, tamanho_ordem, estrategia_estocastica)
    total_trades = win_trades + loss_trades
    accuracy = (win_trades / total_trades) * 100 if total_trades > 0 else 0
    avg_return = (final_balance - initial_balance) / total_trades if total_trades > 0 else 0
    
    print(f"\n📊 **Resultado do Backtesting Estocástico** 📊")
    print(f"🔹 Saldo Final: ${final_balance:.2f}")
    print(f"✅ Acertos (Total): {win_trades}")
    print(f"✅ Acertos (Take Profit): {win_trades_tp}")
    print(f"✅ Acertos (Reverse): {win_trades_reverse}")
    print(f"❌ Erros (Stop Loss): {loss_trades}")
    print(f"📈 Taxa de acerto: {accuracy:.2f}%")
    print(f"📊 Retorno médio por trade: {avg_return:.4f}")
    print(f"📉 Máximo Drawdown: {max_drawdown:.4f}")
    
    for op in operations:
        print(f"{op[0]} | Preço: {op[1]:.2f} | Data: {op[2]}")
