import yfinance as yf
import requests
import os
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- 設定エリア ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini AIの初期化
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

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
    except:
        return "データ取得不可"

def analyze_news_with_ai(ticker, news_list):
    if not GEMINI_API_KEY or not news_list:
        return "ニュースデータなし（またはAPIキー未設定）"
    headlines = "\n".join([n['title'] for n in news_list[:3]])
    prompt = f"銘柄 {ticker} の最新ニュース:\n{headlines}\n\n1行で要約し、投資判断（ポジティブ/ネガティブ/ニュートラル）を理由と共に回答して。"
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI解析に失敗しました。"

def send_discord(message):
    if not WEBHOOK_URL: return
    requests.post(WEBHOOK_URL, json={"content": message})

def main():
    now_str = datetime.now().strftime('%H:%M')
    alert_list = []
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 15: continue
            
            current_price = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            change_pct = ((current_price - prev_close) / prev_close) * 100
            
            rsi_series = calculate_rsi(df)
            current_rsi = rsi_series.iloc[-1]
            
            # 条件：価格-3%以下 または RSI 35以下
            if change_pct <= -3.0 or current_rsi <= 35:
                analyst_eval = get_analyst_info(stock)
                ai_analysis = analyze_news_with_ai(ticker, stock.news)
                
                unit = "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                name = "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                
                alert_msg = (
                    f"⚠️ **{name}** ({ticker})\n"
                    f"💰 価格: {current_price:.2f}{unit} ({change_pct:+.2f}%)\n"
                    f"📊 RSI: {current_rsi:.1f}\n"
                    f"👨‍筋評価: {analyst_eval}\n"
                    f"🤖 **AIニュース解析:** {ai_analysis}\n"
                )
                alert_list.append(alert_msg)
        except:
            continue

    if alert_list:
        header = f"🚀 **【AI精鋭レポート】勝機検知 ({now_str})**\n━━━━━━━━━━━━━━\n"
        send_discord(header + "\n".join(alert_list))
    else:
        send_discord(f"✅ {now_str}：パトロール完了。異常なし（平和な相場です）")

if __name__ == "__main__":
    main()
