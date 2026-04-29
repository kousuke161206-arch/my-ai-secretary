import yfinance as yf
import requests
import os
import pandas as pd
from datetime import datetime

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# 監視リスト（25銘柄）
WATCH_LIST = [
    "^GSPC", "^N225", "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", 
    "META", "AVGO", "ASML", "ARM", "PLTR", "NFLX",
    "7203.T", "6758.T", "7974.T", "8306.T", "6861.T", "9983.T", 
    "8035.T", "6723.T", "9984.T", "6098.T", "9697.T"
]

def calculate_rsi(df, period=14):
    """【レベル2：テクニカル】RSI（相対力指数）を計算する"""
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_analyst_info(stock_obj):
    """【レベル1：ファンダメンタル】プロの評価を取得する"""
    try:
        info = stock_obj.info
        rating = info.get('recommendationKey', 'N/A').replace('_', ' ').title()
        target = info.get('targetMeanPrice', None)
        current = info.get('currentPrice', None)
        
        potential = ""
        if target and current:
            diff = ((target - current) / current) * 100
            potential = f" (目標まであと {diff:+.1f}%)"
        
        return f"{rating}{potential}"
    except:
        return "データ取得不可"

def send_discord(message):
    if not WEBHOOK_URL: return
    requests.post(WEBHOOK_URL, json={"content": message})

def main():
    now_str = datetime.now().strftime('%H:%M')
    alert_list = []
    
    print(f"高機能パトロール開始...")
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            # RSI計算のために1ヶ月分のデータを取得
            df = stock.history(period="1mo")
            if len(df) < 15: continue
            
            # 現在値と前日比
            current_price = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            change_pct = ((current_price - prev_close) / prev_close) * 100
            
            # レベル2: RSI計算
            rsi_series = calculate_rsi(df)
            current_rsi = rsi_series.iloc[-1]
            
            # 判定ロジック
            is_price_drop = change_pct <= -3.0
            is_rsi_low = current_rsi <= 35  # 一般的に30以下が売られすぎだが、早めに検知するため35に設定
            
            if is_price_drop or is_rsi_low:
                # 異常検知時のみレベル1（プロの評価）を取得（負荷軽減のため）
                analyst_eval = get_analyst_info(stock)
                
                unit = "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                name = "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                
                # レポート作成
                status = "📉 価格下落" if is_price_drop else "波形異常（売られすぎ）"
                alert_msg = (
                    f"⚠️ **{name}** ({ticker})\n"
                    f"🚨 状態: {status}\n"
                    f"💰 価格: {current_price:.2f}{unit} ({change_pct:+.2f}%)\n"
                    f"📊 RSI(波形): {current_rsi:.1f} {'(底に近い)' if current_rsi <= 30 else ''}\n"
                    f"👨‍筋評価: {analyst_eval}\n"
                )
                alert_list.append(alert_msg)
        except Exception as e:
            print(f"Error {ticker}: {e}")
            continue

    if alert_list:
        header = f"🚀 **【AI精鋭レポート】勝機を検知しました ({now_str})**\n━━━━━━━━━━━━━━\n"
        send_discord(header + "\n".join(alert_list) + "━━━━━━━━━━━━━━")
    else:
        send_discord(f"✅ {now_str}：パトロール完了。数学的にもプロの目からも、今は「待ち」の時間です。")

if __name__ == "__main__":
    main()
