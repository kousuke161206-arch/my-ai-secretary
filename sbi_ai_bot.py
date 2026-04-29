import yfinance as yf
import requests
import os
import pandas as pd
from datetime import datetime

# --- 設定 ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# 監視する精鋭25銘柄
WATCH_LIST = [
    "^GSPC", "^N225", "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", 
    "META", "AVGO", "ASML", "ARM", "PLTR", "NFLX",
    "7203.T", "6758.T", "7974.T", "8306.T", "6861.T", "9983.T", 
    "8035.T", "6723.T", "9984.T", "6098.T", "9697.T"
]

def calculate_rsi(df, period=14):
    """【レベル2】RSI（相対力指数）の計算"""
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_analyst_info(stock_obj):
    """【レベル1】プロのアナリスト評価を取得"""
    try:
        info = stock_obj.info
        rating = info.get('recommendationKey', 'N/A').replace('_', ' ').title()
        target = info.get('targetMeanPrice', None)
        current = info.get('currentPrice', None)
        potential = ""
        if target and current:
            diff = ((target - current) / current) * 100
            potential = f" (目標まで {diff:+.1f}%)"
        return f"{rating}{potential}"
    except:
        return "データ取得制限中"

def main():
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    alert_list = []
    
    print(f"--- 25銘柄 安定パトロール開始 ({now_str}) ---")
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 2: continue
            
            # 最新の有効データを特定（土日などの空データを回避）
            c_row, p_row = df.iloc[-1], df.iloc[-2]
            if c_row['Close'] == p_row['Close'] and len(df) >= 3:
                c_row, p_row = df.iloc[-2], df.iloc[-3]

            change_pct = ((c_row['Close'] - p_row['Close']) / p_row['Close']) * 100
            rsi = calculate_rsi(df).iloc[-1]
            
            # ログに出力
            print(f"[ ] {ticker:8}: 前日比 {change_pct:+.2f}%, RSI: {rsi:.1f}")
            
            # 判定条件：価格 -3.0%以下 または RSI 35以下
            if change_pct <= -3.0 or rsi <= 35:
                eval_info = get_analyst_info(stock)
                
                unit = "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                name = "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                
                msg = (
                    f"⚠️ **{name}** ({ticker})\n"
                    f"💰 価格: {c_row['Close']:.2f}{unit} ({change_pct:+.2f}%)\n"
                    f"📊 RSI: {rsi:.1f} {'(売られすぎ傾向)' if rsi <= 30 else ''}\n"
                    f"👨‍筋評価: {eval_info}\n"
                )
                alert_list.append(msg)
        except:
            continue

    if alert_list:
        header = f"🚀 **【SBI精鋭レポート：チャンス検知】({now_str})**\n━━━━━━━━━━━━━━\n"
        requests.post(WEBHOOK_URL, json={"content": header + "\n".join(alert_list)})
    else:
        requests.post(WEBHOOK_URL, json={"content": f"✅ {now_str}：パトロール完了。現在、明確な買いシグナルの銘柄はありません。"})

if __name__ == "__main__":
    main()
