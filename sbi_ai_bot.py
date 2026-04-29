import yfinance as yf
import requests
import os
import google.generativeai as genai
from datetime import datetime

# --- 設定エリア ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini AIの初期化
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

WATCH_LIST = [
    "^GSPC", "^N225", "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", 
    "META", "AVGO", "ASML", "ARM", "PLTR", "NFLX",
    "7203.T", "6758.T", "7974.T", "8306.T", "6861.T", "9983.T", 
    "8035.T", "6723.T", "9984.T", "6098.T", "9697.T"
]

def analyze_news_with_ai(ticker, news_list):
    """【レベル2.5：AIニュース解析】ニュースを読み込んで、ポジティブかネガティブか判定する"""
    if not news_list:
        return "直近の関連ニュースはありません。"
    
    # ニュースの見出しを繋げる
    headlines = "\n".join([n['title'] for n in news_list[:3]])
    prompt = f"銘柄 {ticker} の最新ニュースです:\n{headlines}\n\nこのニュースを1行で要約し、投資判断として『ポジティブ（買い）』『ネガティブ（売り）』『ニュートラル（中立）』のどれか1つを理由と共に回答してください。日本語で短くお願いします。"
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI解析に失敗しました。"

# (中略: calculate_rsi, get_analyst_info は前回と同じ)
# ... [前回提供した関数をここに維持します] ...

def main():
    now_str = datetime.now().strftime('%H:%M')
    alert_list = []
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 15: continue
            
            # (中略: 価格とRSIの判定ロジック)
            # ...
            
            # もし「チャンス（下落やRSI低迷）」を検知したら
            if change_pct <= -3.0 or current_rsi <= 35:
                # レベル2.5: 最新ニュースを取得してAIに分析させる
                ai_analysis = analyze_news_with_ai(ticker, stock.news)
                
                # レポートに追加
                alert_msg = (
                    f"⚠️ **{ticker}**\n"
                    f"💰 価格: {current_price:.2f} ({change_pct:+.2f}%)\n"
                    f"📊 RSI: {current_rsi:.1f}\n"
                    f"🤖 **AIニュース解析:** {ai_analysis}\n"
                )
                alert_list.append(alert_msg)
        except:
            continue

    # 送信処理
    # (前回と同じ)
