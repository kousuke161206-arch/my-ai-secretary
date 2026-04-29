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

# 監視する精鋭25銘柄
WATCH_LIST = [
    "^GSPC", "^N225", "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", 
    "META", "AVGO", "ASML", "ARM", "PLTR", "NFLX",
    "7203.T", "6758.T", "7974.T", "8306.T", "6861.T", "9983.T", 
    "8035.T", "6723.T", "9984.T", "6098.T", "9697.T"
]

def calculate_rsi(df, period=14):
    """【レベル2】RSI（相対力指数）の計算"""
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_analyst_info(stock_obj):
    """【レベル1】プロのアナリスト評価を取得"""
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
        return "評価データなし"

def analyze_news_with_ai(ticker, news_list):
    """【レベル2.5】Geminiによる最新ニュースのAI要約・判定"""
    if not GEMINI_API_KEY or not news_list:
        return "関連ニュースなし"
    headlines = "\n".join([n['title'] for n in news_list[:3]])
    prompt = f"銘柄 {ticker} の最新ニュース:\n{headlines}\n\n1行で要約し、投資判断（ポジティブ/ネガティブ/ニュートラル）を理由と共に日本語で回答して。"
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI解析に失敗しました。"

def send_discord(message):
    """Discordへの送信"""
    if not WEBHOOK_URL: return
    requests.post(WEBHOOK_URL, json={"content": message})

def main():
    now_str = datetime.now().strftime('%Y/%m/%d %H:%M')
    alert_list = []
    
    print(f"--- 25銘柄パトロールログ ({now_str}) ---")
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1mo")
            if len(df) < 15:
                print(f"[-] {ticker:8}: データ不足のためスキップ")
                continue
            
            # 現在の数値計算
            current_price = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            change_pct = ((current_price - prev_close) / prev_close) * 100
            rsi_series = calculate_rsi(df)
            current_rsi = rsi_series.iloc[-1]
            
            # ★ログ出力：判定に関わらず全銘柄の状態をGitHubの画面に出す
            print(f"[ ] {ticker:8}: 前日比 {change_pct:+.2f}%, RSI: {current_rsi:.1f}")
            
            # 判定条件：価格 -3.0%以下 OR RSI 35以下
            if change_pct <= -3.0 or current_rsi <= 35:
                print(f"  => 🚩 条件一致！レポートを作成します。")
                eval_info = get_analyst_info(stock)
                ai_news = analyze_news_with_ai(ticker, stock.news)
                
                unit = "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                name = "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                
                msg = (
                    f"⚠️ **{name}** ({ticker})\n"
                    f"💰 価格: {current_price:.2f}{unit} ({change_pct:+.2f}%)\n"
                    f"📊 RSI: {current_rsi:.1f}\n"
                    f"👨‍筋評価: {eval_info}\n"
                    f"🤖 **AIニュース解析:** {ai_news}\n"
                )
                alert_list.append(msg)
        except Exception as e:
            print(f"[!] {ticker:8}: エラー発生 ({e})")
            continue

    # 送信判定
    if alert_list:
        header = f"🚀 **【AI精鋭レポート】勝機検知 ({now_str})**\n━━━━━━━━━━━━━━\n"
        send_discord(header + "\n".join(alert_list))
    else:
        send_discord(f"✅ {now_str}：パトロール完了。現在、条件に合致する「明確な買い時」の銘柄はありません。")

if __name__ == "__main__":
    main()
