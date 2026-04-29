import yfinance as yf
import requests
import os
import pandas as pd
import google.generativeai as genai
from datetime import datetime

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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
    if not GEMINI_API_KEY or not news_list: return "ニュースなし"
    headlines = "\n".join([n['title'] for n in news_list[:3]])
    prompt = f"銘柄 {ticker} の最新ニュース:\n{headlines}\n\n1行で要約し、投資判断（ポジティブ/ネガティブ/中立）を理由と共に日本語で回答して。"
    try:
        response = model.generate_content(prompt)
        return response.text
    except: return "AI解析失敗"

def main():
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    alert_list = []
    
    print(f"--- 25銘柄パトロールログ ({now_str}) ---")
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 2: continue
            
            # 【重要】最新の2日分を確実に特定する（休場の空データを無視）
            # 最新の終値と、その1つ前の終値
            current_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            
            current_price = current_row['Close']
            prev_close = prev_row['Close']
            
            # もし「今日」のデータがまだ動いていない（前日と全く同じ）なら、もう1つ前を見る
            if current_price == prev_close and len(df) >= 3:
                current_row = df.iloc[-2]
                prev_row = df.iloc[-3]
                current_price = current_row['Close']
                prev_close = prev_row['Close']

            change_pct = ((current_price - prev_close) / prev_close) * 100
            rsi = calculate_rsi(df).iloc[-1]
            
            # 日付もログに出して「いつのデータか」を明確にする
            date_label = current_row.name.strftime('%m/%d')
            print(f"[ ] {ticker:8}: {date_label} 前日比 {change_pct:+.2f}%, RSI: {rsi:.1f}")
            
            if change_pct <= -3.0 or rsi <= 35:
                eval_info = get_analyst_info(stock)
                ai_news = analyze_news_with_ai(ticker, stock.news)
                
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
            print(f"[!] {ticker:8}: エラー ({e})")

    if alert_list:
        header = f"🚀 **【AI精鋭レポート】勝機検知 ({now_str})**\n━━━━━━━━━━━━━━\n"
        requests.post(WEBHOOK_URL, json={"content": header + "\n".join(alert_list)})
    else:
        # なぜ「異常なし」になったかのヒントを添える
        send_msg = f"✅ {now_str}：パトロール完了。現在、-3%を超える下落銘柄は見当たりません。"
        requests.post(WEBHOOK_URL, json={"content": send_msg})

if __name__ == "__main__":
    main()
