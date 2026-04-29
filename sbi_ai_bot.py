import yfinance as yf
import requests
import os
import time
from datetime import datetime

# --- 【重要】GitHubの秘密の合言葉からURLを読み込む設定 ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# 監視する精鋭12銘柄
WATCH_LIST = [
    "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN",
    "7203.T", "6758.T", "7974.T", "8306.T", "6861.T", "9983.T"
]

def get_status_label(change_pct):
    """下落率から現在の状態ラベルを判定する"""
    if change_pct <= -20:
        return "🚨 【歴史的暴落】"
    elif change_pct <= -7:
        return "⚠️ 【大幅下落】"
    elif change_pct <= -3:
        return "📉 【押し目（買い時）】"
    elif change_pct < 0:
        return "💤 【微減（安定中）】"
    elif change_pct == 0:
        return "➡ 【変わらず】"
    else:
        return "📈 【上昇中】"

def send_discord(message):
    """Discordにメッセージを送信する"""
    if not WEBHOOK_URL:
        print("❌ エラー: WEBHOOK_URL が設定されていません。")
        return
    data = {"content": message}
    requests.post(WEBHOOK_URL, json=data)

def main():
    now = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    report_msg = f"━━━━━ 📊 **AI市場健康診断 ({now})** ━━━━━\n"
    
    print(f"データ取得を開始します...")
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            # 前日比計算のために2日分取得
            df = stock.history(period="2d")
            
            if len(df) < 2:
                continue
                
            prev_close = df['Close'].iloc[0]
            current_price = df['Close'].iloc[1]
            change_pct = ((current_price - prev_close) / prev_close) * 100
            
            label = get_status_label(change_pct)
            unit = "円" if ".T" in ticker else "ドル"
            
            report_msg += f"{label} **{ticker}**: {current_price:.2f}{unit} ({change_pct:+.2f}%)\n"
            
        except Exception as e:
            report_msg += f"❌ {ticker}: データ取得エラー\n"

    report_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    send_discord(report_msg)
    print("✅ レポートを送信しました。")

if __name__ == "__main__":
    main()
