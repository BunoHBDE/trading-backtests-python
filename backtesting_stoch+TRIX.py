import pandas as pd

# 🔹 Função para calcular TRIX
def calcular_trix(df, periodo=14):
    df["ema1"] = df["close"].ewm(span=periodo, adjust=False).mean()
    df["ema2"] = df["ema1"].ewm(span=periodo, adjust=False).mean()
    df["ema3"] = df["ema2"].ewm(span=periodo, adjust=False).mean()
    df["trix"] = df["ema3"].pct_change() * 100  # Taxa de variação percentual
    return df

# 🔹 Função para calcular Estocástico
def calcular_estocastico(df, periodo=14):
    df["low_min"] = df["low"].rolling(window=periodo).min()
    df["high_max"] = df["high"].rolling(window=periodo).max()
    df["%K"] = ((df["close"] - df["low_min"]) / (df["high_max"] - df["low_min"])) * 100
    df["%D"] = df["%K"].rolling(window=3).mean()
    return df
    

# 🔹 Estratégia combinando TRIX e Estocástico
def estrategia_trix_estocastico(df, i):
    if i < 14:
        return None
    
    trix = df.iloc[i]["trix"]
    k = df.iloc[i]["%K"]

    if trix > 0 and k < 30:
        return "BUY"
    elif trix < 0 and k > 70:
        return "SELL"
    return None

# 🔹 Função para executar o backtesting
def executar_backtesting(df, initial_balance=10000, tamanho_ordem=0.001):
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
        ordem = estrategia_trix_estocastico(df, i)
        
        # Verifica se há posição aberta e aplica Stop Loss ou Take Profit
        if position_open:
            if trade_type == "long":
                if last_row["high"] >= take_profit:
                    usd_balance = btc_balance * take_profit
                    btc_balance = 0
                    win_trades += 1
                    operations.append(("WIN (TP)", take_profit, last_row["time"]))
                    position_open = False
                elif last_row["low"] <= stop_loss:
                    usd_balance = btc_balance * stop_loss
                    btc_balance = 0
                    loss_trades += 1
                    operations.append(("LOSS (SL)", stop_loss, last_row["time"]))
                    position_open = False
            elif trade_type == "short":
                if last_row["low"] <= take_profit:
                    usd_balance += (entry_price - take_profit) * tamanho_ordem
                    btc_balance = 0
                    win_trades += 1
                    operations.append(("WIN (TP)", take_profit, last_row["time"]))
                    position_open = False
                elif last_row["high"] >= stop_loss:
                    usd_balance += (entry_price - stop_loss) * tamanho_ordem
                    btc_balance = 0
                    loss_trades += 1
                    operations.append(("LOSS (SL)", stop_loss, last_row["time"]))
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
                operations.append(("BUY", price, last_row["time"]))
            elif ordem == "SELL":
                entry_price = price
                stop_loss = price * 1.005
                take_profit = price * 0.99
                position_open = True
                trade_type = "short"
                operations.append(("SELL", price, last_row["time"]))

    # Fechar posição se ainda estiver aberta no final do histórico
    if position_open:
        if trade_type == "long":
            usd_balance = btc_balance * df.iloc[-1]["close"]
        elif trade_type == "short":
            usd_balance += (entry_price - df.iloc[-1]["close"]) * tamanho_ordem
        btc_balance = 0
        operations.append(("FECHAMENTO FORÇADO", df.iloc[-1]["close"], df.iloc[-1]["time"]))
        position_open = False

    return operations, usd_balance, win_trades, loss_trades

# 🔹 Carregar os dados históricos (substitua pelo caminho correto do seu arquivo)
file_path = "Diretório"
df = pd.read_excel(file_path)

# 🔹 Aplicar os cálculos dos indicadores
df = calcular_trix(df)
df = calcular_estocastico(df)

# 🔹 Rodar o backtesting
operations, final_balance, win_trades, loss_trades = executar_backtesting(df)

# 🔹 Exibir os resultados do backtesting
print(f"\n📊 **Resultado do Backtesting** 📊")
print(f"🔹 Saldo Final: ${final_balance:.2f}")
print(f"✅ Acertos (Take Profit): {win_trades}")
print(f"❌ Erros (Stop Loss): {loss_trades}")

