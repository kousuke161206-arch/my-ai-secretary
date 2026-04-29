import yfinance as yf
import requests
import os
import pandas as pd
from google import genai
from datetime import datetime
import time

# --- 設定 ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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

def batch_analyze_with_ai(request_data):
    """【新機能】複数銘柄を1回のAIリクエストでまとめて解析する"""
    if client is None or not request_data:
        return {}
    
    # AIへの巨大な質問状（プロンプト）を作成
    prompt = "以下の各銘柄の最新ニュースを個別に分析し、それぞれ1行で『判断(買い/売り/中立)と理由』を日本語で答えてください。\n\n"
    for ticker, news in request_data:
        headlines = "\n".join([n.get('title', 'No Title') for n in news[:2]])
        prompt += f"■{ticker}のニュース:\n{headlines}\n\n"

    try:
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        # AIの回答を銘柄ごとに辞書形式で管理する（簡易的な抽出）
        return response.text
    except Exception as e:
        print(f"AIバッチ解析エラー: {e}")
        return f"AI解析エラー: {e}"

def main():
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    matched_stocks = [] # チャンス銘柄の情報を溜めるリスト
    
    print(f"--- 25銘柄パトロール開始 ({now_str}) ---")
    
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
            
            if change_pct <= -3.0 or rsi <= 35:
                # ニュースを即解析せず、まずはデータを溜める
                news_data = []
                try: news_data = stock.news
                except: pass
                matched_stocks.append({
                    "ticker": ticker,
                    "price": f"{curr['Close']:.2f}",
                    "change": f"{change_pct:+.2f}%",
                    "rsi": f"{rsi:.1f}",
                    "news": news_data,
                    "unit": "円" if ".T" in ticker or ticker == "^N225" else "ドル",
                    "name": "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                })
        except: continue

    # まとめてAIに投げる
    if matched_stocks:
        request_items = [(s["ticker"], s["news"]) for s in matched_stocks]
        ai_summary = batch_analyze_with_ai(request_items)
        
        # Discord用のメッセージ作成
        report = f"🚀 **【AI精鋭レポート】勝機検知 ({now_str})**\n"
        report += "🤖 **AI総合解析結果:**\n" + ai_summary + "\n\n━━━━━━━━━━━━━━\n"
        
        for s in matched_stocks:
            report += f"⚠️ **{s['name']}** ({s['ticker']}): {s['price']}{s['unit']} ({s['change']}) / RSI: {s['rsi']}\n"
        
        requests.post(WEBHOOK_URL, json={"content": report})
    else:
        requests.post(WEBHOOK_URL, json={"content": f"✅ {now_str}：パトロール完了。異常なし。"})

if __name__ == "__main__":
    main()
