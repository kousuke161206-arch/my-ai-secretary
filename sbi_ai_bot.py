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
    # エラーが起きても「データなし」で返し、プログラムを止めない
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
        return "データ取得制限中（または無し）"

def analyze_news_with_ai(ticker, news_list):
    if not GEMINI_API_KEY or not news_list:
        return "直近のニュースはありません。"
    headlines = "\n".join([n['title'] for n in news_list[:3]])
    prompt = f"銘柄 {ticker} の最新ニュース:\n{headlines}\n\n1行で要約し、投資判断（ポジティブ/ネガティブ/ニュートラル）を理由と共に日本語で回答して。"
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI解析をスキップしました（サーバー混雑）。"

def main():
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    alert_list = []
    
    print(f"--- 25銘柄パトロールログ ({now_str}) ---")
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 15: continue
            
            current_price = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            change_pct = ((current_price - prev_close) / prev_close) * 100
            rsi = calculate_rsi(df).iloc[-1]
            
            print(f"[ ] {ticker:8}: 前日比 {change_pct:+.2f}%, RSI: {rsi:.1f}")
            
            # 条件判定
            if change_pct <= -3.0 or rsi <= 35:
                print(f"  => 🚩 チャンス検知！詳細情報を集めます。")
                
                # --- ここが修正ポイント：個別にtry-exceptをかけ、一つ失敗しても全体を止めない ---
                eval_info = get_analyst_info(stock)
                
                # ニュース取得も慎重に行う
                news_data = []
                try:
                    news_data = stock.news
                except:
                    pass
                
                ai_news = analyze_news_with_ai(ticker, news_data)
                
                unit = "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                name = "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                
                msg = (
                    f"⚠️ **{name}** ({ticker})\n"
                    f"💰 価格: {current_price:.2f}{unit} ({change_pct:+.2f}%)\n"
                    f"📊 RSI: {rsi:.1f}\n"
                    f"👨‍筋評価: {eval_info}\n"
                    f"🤖 **AIニュース解析:** {ai_news}\n"
                )
                alert_list.append(msg)
        except Exception as e:
            print(f"[!] {ticker:8}: エラー発生 ({e})。この銘柄をスキップします。")
            continue

    if alert_list:
        header = f"🚀 **【AI精鋭レポート】勝機検知 ({now_str})**\n━━━━━━━━━━━━━━\n"
        requests.post(WEBHOOK_URL, json={"content": header + "\n".join(alert_list)})
    else:
        requests.post(WEBHOOK_URL, json={"content": f"✅ {now_str}：パトロール完了。異常なし。"})

if __name__ == "__main__":
    main()
