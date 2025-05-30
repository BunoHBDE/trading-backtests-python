import pandas as pd

# 🔹 Função para calcular TRIX
def calcular_trix(df, periodo=18):
    df["ema1"] = df["close"].ewm(span=periodo, adjust=False).mean()
    df["ema2"] = df["ema1"].ewm(span=periodo, adjust=False).mean()
    df["ema3"] = df["ema2"].ewm(span=periodo, adjust=False).mean()
    df["trix"] = df["ema3"].pct_change() * 100  # Taxa de variação percentual
    df["trix_delta"] = df["trix"].diff()  # Variação do TRIX para detectar tendências
    return df

# 🔹 Função para calcular ADX (Average Directional Index)
def calcular_adx(df, periodo=14):
    df["high_diff"] = df["high"].diff()
    df["low_diff"] = df["low"].diff()

    df["+DM"] = ((df["high_diff"] > df["low_diff"]) & (df["high_diff"] > 0)) * df["high_diff"]
    df["-DM"] = ((df["low_diff"] > df["high_diff"]) & (df["low_diff"] > 0)) * df["low_diff"]

    df["+DI"] = 100 * (df["+DM"].ewm(span=periodo, adjust=False).mean() / df["close"])
    df["-DI"] = 100 * (df["-DM"].ewm(span=periodo, adjust=False).mean() / df["close"])
    
    df["DX"] = 100 * abs(df["+DI"] - df["-DI"]) / (df["+DI"] + df["-DI"])
    df["ADX"] = df["DX"].ewm(span=periodo, adjust=False).mean()
    df["adx_delta"] = df["ADX"].diff()  # Variação do ADX para detectar crescimento/queda

    return df

# 🔹 Estratégia baseada em TRIX e ADX
def estrategia_trix_adx(df, i):
    if i < 14:
        return None
    
    trix = df.iloc[i]["trix"]
    trix_delta = df.iloc[i]["trix_delta"]
    adx = df.iloc[i]["ADX"]
    adx_delta = df.iloc[i]["adx_delta"]


    # 📉 **Condição para Short**
    if (trix < 0 and adx > 20 and adx_delta > 0 and trix_delta > 0):
        print (f"Trix: {trix}")
        print (f"Trix delta: {trix_delta}")
        print (f"Adx: {adx}")
        print (f"Adx delta: {adx_delta}")
        return "SELL"
    
    return None

# 🔹 Função para executar o backtesting
def executar_backtesting(df, initial_balance=10000, tamanho_ordem=0.005):
    btc_balance = 0
    usd_balance = initial_balance
    operations = []
    position_open = False
    entry_price = 0
    stop_loss = 0
    take_profit = 0
    trade_type = None
    win_trades_long = 0
    win_trades_short = 0
    loss_trades_long = 0
    loss_trades_short = 0

    for i in range(1, len(df)):
        last_row = df.iloc[i]
        price = last_row["close"]
        ordem = estrategia_trix_adx(df, i)

        # Verifica se há posição aberta e aplica Stop Loss ou Take Profit
        if position_open:
            if trade_type == "long":
                if last_row["high"] >= take_profit:
                    usd_balance = btc_balance * take_profit
                    btc_balance = 0
                    win_trades_long += 1
                    operations.append(("WIN (TP)", take_profit, last_row["time"]))
                    position_open = False
                elif last_row["low"] <= stop_loss:
                    usd_balance = btc_balance * stop_loss
                    btc_balance = 0
                    loss_trades_long += 1
                    operations.append(("LOSS (SL)", stop_loss, last_row["time"]))
                    position_open = False
                
            elif trade_type == "short":
                if last_row["low"] <= take_profit:
                    usd_balance += (entry_price - take_profit) * tamanho_ordem
                    btc_balance = 0
                    win_trades_short += 1
                    operations.append(("WIN (TP)", take_profit, last_row["time"]))
                    position_open = False
                elif last_row["high"] >= stop_loss:
                    usd_balance += (entry_price - stop_loss) * tamanho_ordem
                    btc_balance = 0
                    loss_trades_short += 1
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

    return operations, usd_balance, win_trades_long, win_trades_short, loss_trades_long, loss_trades_short

# 🔹 Carregar os dados históricos (substitua pelo caminho correto do seu arquivo)
file_path = "Diretório"
df = pd.read_excel(file_path)

# 🔹 Aplicar os cálculos dos indicadores
df = calcular_trix(df)
df = calcular_adx(df)

# 🔹 Rodar o backtesting
operations, final_balance, win_trades_long, win_trades_short, loss_trades_long, loss_trades_short = executar_backtesting(df)

# 🔹 Exibir os resultados do backtesting
print(f"\n📊 **Resultado do Backtesting** 📊")
print(f"🔹 Saldo Final: ${final_balance:.2f}")
print(f"✅ Acertos (Long): {win_trades_long}")
print(f"✅ Acertos (Short): {win_trades_short}")
print(f"❌ Erros (Long): {loss_trades_long}")
print(f"❌ Erros (Short): {loss_trades_short}")

