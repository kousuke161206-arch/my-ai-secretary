import yfinance as yf
import requests
import os
import pandas as pd
import google.generativeai as genai
from datetime import datetime

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Geminiの初期化を慎重に行う
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
    except: return "取得不可"

def analyze_news_with_ai(ticker, news_list):
    if not GEMINI_API_KEY: return "APIキー未設定"
    if not news_list: return "関連ニュースなし"
    
    try:
        # タイトルがない場合も考慮して安全に取得
        headlines = []
        for n in news_list[:3]:
            title = n.get('title') or n.get('summary') or "タイトルなし"
            headlines.append(title)
        
        prompt = f"銘柄 {ticker} の最新ニュースです:\n" + "\n".join(headlines) + "\n\n1行で要約し、投資判断（買い・売り・中立）を理由と共に日本語で答えて。AIとしての意見でOKです。"
        
        response = model.generate_content(prompt)
        # AIが回答を拒否（安全フィルターなど）した場合の処理
        if not response.parts:
            return "AIが回答を控えました（安全フィルター等）。"
        return response.text.strip()
    except Exception as e:
        return f"AI解析エラー: {str(e)}"

def main():
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    alert_list = []
    print(f"--- 25銘柄パトロール開始 ({now_str}) ---")
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 2: continue
            
            current_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            current_price = current_row['Close']
            prev_close = prev_row['Close']
            
            # データ変動チェック
            if current_price == prev_close and len(df) >= 3:
                current_row = df.iloc[-2]
                prev_row = df.iloc[-3]
                current_price = current_row['Close']
                prev_close = prev_row['Close']

            change_pct = ((current_price - prev_close) / prev_close) * 100
            rsi = calculate_rsi(df).iloc[-1]
            
            print(f"[ ] {ticker:8}: 前日比 {change_pct:+.2f}%, RSI: {rsi:.1f}")
            
            # 判定（-3%以下 または RSI 35以下 または日本株の急落）
            if change_pct <= -3.0 or rsi <= 35:
                eval_info = get_analyst_info(stock)
                
                # ニュース取得を確実にする
                news_data = []
                try: news_data = stock.news
                except: pass
                
                ai_news = analyze_news_with_ai(ticker, news_data)
                
                unit = "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                name = "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                
                alert_list.append(
                    f"⚠️ **{name}** ({ticker})\n"
                    f"💰 価格: {current_price:.2f}{unit} ({change_pct:+.2f}%)\n"
                    f"📊 RSI: {rsi:.1f}\n"
                    f"👨‍筋評価: {eval_info}\n"
                    f"🤖 **AI解析:** {ai_news}\n"
                )
        except Exception as e:
            print(f"[!] {ticker:8}: 実行エラー ({e})")

    if alert_list:
        header = f"🚀 **【AI精鋭レポート】勝機検知 ({now_str})**\n━━━━━━━━━━━━━━\n"
        requests.post(WEBHOOK_URL, json={"content": header + "\n".join(alert_list)})
    else:
        requests.post(WEBHOOK_URL, json={"content": f"✅ {now_str}：パトロール完了。異常なし。"})

if __name__ == "__main__":
    main()
