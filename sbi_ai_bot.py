import yfinance as yf
import requests
import os
import pandas as pd
from google import genai
from datetime import datetime
import sys

# --- 設定の読み込み ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# AIクライアントの初期化（失敗してもプログラムを止めない）
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"AI初期化エラー: {e}")

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

def analyze_news_with_ai(ticker, news_list):
    if client is None: return "AI未設定（Keyを確認してください）"
    if not news_list: return "関連ニュースなし"
    
    try:
        headlines = [n.get('title', 'No Title') for n in news_list[:3]]
        prompt = f"銘柄 {ticker} の最新ニュース:\n" + "\n".join(headlines) + "\n\n1行で要約し、投資判断（買い・売り・中立）を理由と共に日本語で答えて。"
        
        # モデル名は2026年現在の最新版を使用
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        return response.text.strip()
    except Exception as e:
        print(f"AI解析中にエラー: {e}")
        return "AI解析一時不可（価格のみ確認してください）"

def send_discord(message):
    """何があってもDiscord送信を試みる関数"""
    if not WEBHOOK_URL:
        print("エラー: WEBHOOK_URLが設定されていません。")
        return
    try:
        response = requests.post(WEBHOOK_URL, json={"content": message})
        print(f"Discord送信結果: {response.status_code}")
    except Exception as e:
        print(f"Discord送信中にクラッシュ: {e}")

def main():
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    alert_list = []
    print(f"--- 25銘柄パトロール開始 ({now_str}) ---", flush=True)
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 2: continue
            
            c_row, p_row = df.iloc[-1], df.iloc[-2]
            # 最新データが止まっている場合の調整
            if c_row['Close'] == p_row['Close'] and len(df) >= 3:
                c_row, p_row = df.iloc[-2], df.iloc[-3]

            change_pct = ((c_row['Close'] - p_row['Close']) / p_row['Close']) * 100
            rsi = calculate_rsi(df).iloc[-1]
            
            print(f"[ ] {ticker:8}: 前日比 {change_pct:+.2f}%, RSI: {rsi:.1f}", flush=True)
            
            # 判定条件
            if change_pct <= -3.0 or rsi <= 35:
                # ニュース取得
                news_data = []
                try: news_data = stock.news
                except: pass
                
                ai_news = analyze_news_with_ai(ticker, news_data)
                
                unit = "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                name = "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                
                alert_list.append(
                    f"⚠️ **{name}** ({ticker})\n"
                    f"💰 価格: {c_row['Close']:.2f}{unit} ({change_pct:+.2f}%)\n"
                    f"📊 RSI: {rsi:.1f}\n"
                    f"🤖 **AI解析:** {ai_news}\n"
                )
        except Exception as e:
            print(f"[!] {ticker}: エラー回避 ({e})", flush=True)

    # 送信処理（ここでWEBHOOK_URLがNoneでもクラッシュしないように関数化済み）
    if alert_list:
        msg = f"🚀 **【AI精鋭レポート】勝機検知 ({now_str})**\n━━━━━━━━━━━━━━\n" + "\n".join(alert_list)
        send_discord(msg)
    else:
        send_discord(f"✅ {now_str}：パトロール完了。現在、条件に合う銘柄はありません。")

if __name__ == "__main__":
    main()
