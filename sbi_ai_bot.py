import yfinance as yf
import requests
import os
import pandas as pd
from google import genai
from datetime import datetime

# --- 設定 ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except:
        print("AI初期化エラー")

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

def main():
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    matched_stocks = []
    
    print(f"--- パトロール開始 ({now_str}) ---")
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 2: continue
            
            curr, prev = df.iloc[-1], df.iloc[-2]
            if curr['Close'] == prev['Close'] and len(df) >= 3:
                curr, prev = df.iloc[-2], df.iloc[-3]

            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            rsi = calculate_rsi(df).iloc[-1]
            
            # 条件判定 (-3.0%以下 または RSI 35以下)
            if change_pct <= -3.0 or rsi <= 35:
                # ニュースを取得（解析はまだしない）
                news_titles = [n.get('title', 'No Title') for n in (stock.news or [])[:2]]
                matched_stocks.append({
                    "ticker": ticker,
                    "price": curr['Close'],
                    "change": change_pct,
                    "rsi": rsi,
                    "news": news_titles,
                    "unit": "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                })
        except: continue

    # 1. 銘柄がなければ終了
    if not matched_stocks:
        requests.post(WEBHOOK_URL, json={"content": f"✅ {now_str}：パトロール完了。異常なし。"})
        return

    # 2. AIへの依頼を「一通」にまとめる
    ai_report = "AI解析制限中"
    if client:
        # 全銘柄のニュースを連結
        all_news_text = ""
        for s in matched_stocks:
            all_news_text += f"【{s['ticker']}】\n" + "\n".join(s['news']) + "\n\n"
        
        prompt = f"以下の銘柄群のニュースを読み、それぞれ短く日本語で『買い・売り・中立の判断とその理由』を1行ずつ教えてください。\n\n{all_news_text}"
        
        try:
            # ここでAIを1回だけ呼び出す
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            ai_report = response.text
        except Exception as e:
            ai_report = f"AI解析エラー (詳細: {e})"

    # 3. Discordへ一括送信
    report_msg = f"🚀 **【AI精鋭レポート】({now_str})**\n\n🤖 **AI総合判定:**\n{ai_report}\n\n"
    report_msg += "━━━━━━━━━━━━━━\n"
    for s in matched_stocks:
        report_msg += f"⚠️ **{s['ticker']}**: {s['price']:.2f}{s['unit']} ({s['change']:+.2f}%) / RSI: {s['rsi']:.1f}\n"
    
    requests.post(WEBHOOK_URL, json={"content": report_msg})

if __name__ == "__main__":
    main()
