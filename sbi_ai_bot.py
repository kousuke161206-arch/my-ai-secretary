import yfinance as yf
import requests
import os
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- 設定の読み込み ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# AIモデルをあらかじめ空で定義（エラー防止）
model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Gemini初期化エラー: {e}")

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
    # modelが正しく作られていない場合は解析しない
    if model is None: return "AI解析不可 (APIキー設定を確認してください)"
    if not news_list: return "関連ニュースなし"
    
    try:
        headlines = []
        for n in news_list[:3]:
            # タイトルか概要を安全に取得
            t = n.get('title') or n.get('summary') or "ニュース項目あり"
            headlines.append(t)
        
        prompt = f"銘柄 {ticker} の最新ニュース:\n" + "\n".join(headlines) + "\n\n1行で要約し、投資判断を理由と共に日本語で回答して。"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"解析エラー: {str(e)}"

def send_discord(message):
    """Discordへの送信を安全に行う"""
    if not WEBHOOK_URL:
        print("WEBHOOK_URLが設定されていません。")
        return
    try:
        requests.post(WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"Discord送信エラー: {e}")

def main():
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    alert_list = []
    print(f"--- パトロール開始 ({now_str}) ---")
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 2: continue
            
            # 最新の有効なデータを特定
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            if curr['Close'] == prev['Close'] and len(df) >= 3:
                curr, prev = df.iloc[-2], df.iloc[-3]

            change_pct = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            rsi = calculate_rsi(df).iloc[-1]
            
            print(f"[ ] {ticker:8}: 前日比 {change_pct:+.2f}%, RSI: {rsi:.1f}")
            
            # 条件判定
            if change_pct <= -3.0 or rsi <= 35:
                # 異常あり：詳細情報を集める（失敗しても他を止めない）
                eval_info = get_analyst_info(stock)
                
                news_data = []
                try: news_data = stock.news
                except: pass
                
                ai_news = analyze_news_with_ai(ticker, news_data)
                
                unit = "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                name = "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                
                alert_list.append(
                    f"⚠️ **{name}** ({ticker})\n"
                    f"💰 価格: {curr['Close']:.2f}{unit} ({change_pct:+.2f}%)\n"
                    f"📊 RSI: {rsi:.1f}\n"
                    f"👨‍筋評価: {eval_info}\n"
                    f"🤖 **AI解析:** {ai_news}\n"
                )
        except Exception as e:
            print(f"[!] {ticker}: 処理スキップ ({e})")

    # メッセージの送信
    if alert_list:
        header = f"🚀 **【AI精鋭レポート】勝機検知 ({now_str})**\n━━━━━━━━━━━━━━\n"
        send_discord(header + "\n".join(alert_list))
    else:
        send_discord(f"✅ {now_str}：パトロール完了。異常なし。")

if __name__ == "__main__":
    main()
