import yfinance as yf
import requests
import os
import time
from datetime import datetime

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# 精鋭25銘柄リスト
WATCH_LIST = [
    "^GSPC", "^N225", "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN", 
    "META", "AVGO", "ASML", "ARM", "PLTR", "NFLX",
    "7203.T", "6758.T", "7974.T", "8306.T", "6861.T", "9983.T", 
    "8035.T", "6723.T", "9984.T", "6098.T", "9697.T"
]

def get_status_info(change_pct):
    if change_pct <= -20:
        return "🚨 【レベル3：歴史的暴落】", "即ニュースを確認！致命的な問題がなければ千載一遇の好機。"
    elif change_pct <= -7:
        return "⚠️ 【レベル2：大幅下落】", "買い増しの検討ライン。冷静に資金配分を考えましょう。"
    elif change_pct <= -3:
        return "📉 【レベル1：押し目】", "一時的な調整。コツコツ買うなら絶好のタイミング。"
    return None, None

def send_discord(message):
    if not WEBHOOK_URL: return
    requests.post(WEBHOOK_URL, json={"content": message})

def main():
    now_str = datetime.now().strftime('%H:%M')
    alert_list = []
    
    print(f"25銘柄のパトロール開始...")
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="2d")
            if len(df) < 2: continue
                
            prev_close = df['Close'].iloc[0]
            current_price = df['Close'].iloc[1]
            change_pct = ((current_price - prev_close) / prev_close) * 100
            
            level_label, advice = get_status_info(change_pct)
            
            if level_label:
                # 通貨と名前の処理
                unit = "円" if ".T" in ticker or ticker == "^N225" else "ドル"
                name = "S&P500" if ticker == "^GSPC" else "日経平均" if ticker == "^N225" else ticker
                alert_list.append(f"{level_label} **{name}**\n価格: {current_price:.2f}{unit} ({change_pct:+.2f}%)\n💡 {advice}")
        except:
            continue

    if alert_list:
        header = f"🔔 **【AI緊急通知】市場にチャンスあり ({now_str})**\n"
        send_discord(header + "\n\n".join(alert_list))
    else:
        send_discord(f"✅ {now_str}：パトロール完了。25銘柄すべて異常なし。")

if __name__ == "__main__":
    main()
