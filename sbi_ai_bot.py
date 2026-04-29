import yfinance as yf
import requests
import os
import pandas as pd
import google.generativeai as genai
from datetime import datetime
import sys

# --- 設定読み込み ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# AIモデルの初期化
model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Gemini初期化失敗: {e}")

WATCH_LIST = [
    "^GSPC", "^N225", "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", 
    "META", "AVGO", "ASML", "ARM", "PLTR", "NFLX",
    "7203.T", "6758.T", "7974.T", "8306.T", "6861.T", "9983.T", 
    "8035.T", "6723.T", "9984.T", "6098.T", "9697.T"
]

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_analyst_info(stock_obj):
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
    except: return "取得不可"

def analyze_news_with_ai(ticker, news_list):
    if model is None or not news_list: return "AI解析スキップ"
    try:
        headlines = [n.get('title', 'No Title') for n in news_list[:3]]
        prompt = f"銘柄 {ticker} の最新ニュース:\n" + "\n".join(headlines) + "\n\n1行で要約し、投資判断を理由と共に日本語で回答して。"
        response = model.generate_content(prompt)
        return response.text.strip()
    except: return "解析エラー"

def send_discord(message):
    if not WEBHOOK_URL:
        print("WEBHOOK_URLが未設定です。")
        return
    try:
        r = requests.post(WEBHOOK_URL, json={"content": message})
        print(f"Discord送信ステータス: {r.status_code}")
    except Exception as e:
        print(f"Discord送信失敗: {e}")

def main():
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    alert_list = []
    print(f"--- パトロール開始 ({now_str}) ---", flush=True)
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 2: continue
            
            # 最新2日分のデータを特定
            c_row = df.iloc[-1]
            p_row = df.iloc[-2]
            
            # 土日などで最新データが動いていない場合の処理
            if c_row['Close'] == p_row['Close'] and len(df) >= 3:
                c_row, p_row = df.iloc[-2], df.iloc[-3]

            # 修正ポイント：確実に抽出した行から計算する
            c_price = c_row['Close']
            p_price = p_row['Close']
            change_pct = ((c_price - p_price) / p_price) * 100
            rsi = calculate_rsi(df).iloc[-1]
            
            print(f"[ ] {ticker:8}: 前日比 {change_pct:+.2f}%, RSI: {rsi:.1f}", flush=True)
            
            if change_pct <= -3.0 or rsi <= 35:
                print(f"  => 🚩 チャンス検知: {ticker}", flush=True)
                eval_info = get_analyst_info(stock)
                ai_news = analyze_news_with_ai(ticker, stock.news)
                
                unit = "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                name = "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                
                alert_list.append(
                    f"⚠️ **{name}** ({ticker})\n"
                    f"💰 価格: {c_price:.2f}{unit} ({change_pct:+.2f}%)\n"
                    f"📊 RSI: {rsi:.1f}\n"
                    f"👨‍筋評価: {eval_info}\n"
                    f"🤖 **AI解析:** {ai_news}\n"
                )
        except Exception as e:
            print(f"[!] {ticker}: エラー {e}", flush=True)

    # 最終報告
    if alert_list:
        send_discord(f"🚀 **【AI精鋭レポート】勝機検知 ({now_str})**\n━━━━━━━━━━━━━━\n" + "\n".join(alert_list))
    else:
        send_discord(f"✅ {now_str}：パトロール完了。異常なし。")
    
    print("--- パトロール終了 ---", flush=True)

if __name__ == "__main__":
    main()
