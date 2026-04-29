import yfinance as yf
import requests
import os
import pandas as pd
from google import genai # 最新のSDK
from datetime import datetime

# --- 設定 ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 2026年最新規格のAIクライアント初期化
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"AI初期化失敗: {e}")

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
    if client is None: return "AIクライアント未設定"
    if not news_list: return "ニュースなし"
    
    try:
        headlines = [n.get('title', 'No Title') for n in news_list[:3]]
        prompt = f"銘柄 {ticker} の最新ニュース:\n" + "\n".join(headlines) + "\n\n1行で要約し、投資判断を理由と共に日本語で回答して。"
        
        # 2026年最新の生成コマンドとモデル名(gemini-2.0-flash)を使用
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"解析エラー({str(e)})"

def main():
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    alert_list = []
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 2: continue
            
            c_row, p_row = df.iloc[-1], df.iloc[-2]
            if c_row['Close'] == p_row['Close'] and len(df) >= 3:
                c_row, p_row = df.iloc[-2], df.iloc[-3]

            change_pct = ((c_row['Close'] - p_row['Close']) / p_row['Close']) * 100
            rsi = calculate_rsi(df).iloc[-1]
            
            # 判定条件
            if change_pct <= -3.0 or rsi <= 35:
                eval_info = get_analyst_info(stock)
                ai_news = analyze_news_with_ai(ticker, stock.news)
                
                unit = "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                name = "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                
                alert_list.append(
                    f"⚠️ **{name}** ({ticker})\n"
                    f"💰 価格: {c_row['Close']:.2f}{unit} ({change_pct:+.2f}%)\n"
                    f"📊 RSI: {rsi:.1f}\n"
                    f"👨‍筋評価: {eval_info}\n"
                    f"🤖 **AI解析:** {ai_news}\n"
                )
        except Exception as e:
            print(f"[!] {ticker}: スキップ ({e})")

    if alert_list:
        msg = f"🚀 **【AI精鋭レポート】勝機検知 ({now_str})**\n━━━━━━━━━━━━━━\n" + "\n".join(alert_list)
        requests.post(WEBHOOK_URL, json={"content": msg})
    else:
        requests.post(WEBHOOK_URL, json={"content": f"✅ {now_str}：パトロール完了。異常なし。"})

if __name__ == "__main__":
    main()
