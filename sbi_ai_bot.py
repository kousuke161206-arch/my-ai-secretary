import yfinance as yf
import requests
import os
import time
from datetime import datetime

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

WATCH_LIST = [
    "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN",
    "7203.T", "6758.T", "7974.T", "8306.T", "6861.T", "9983.T"
]

def get_status_info(change_pct):
    """下落率からレベルと助言を判定する"""
    if change_pct <= -20:
        return "🚨 【レベル3：歴史的暴落】", "即ニュースを確認！致命的な問題がなければ千載一遇の好機。"
    elif change_pct <= -7:
        return "⚠️ 【レベル2：大幅下落】", "買い増しの検討ライン。資金配分を考えましょう。"
    elif change_pct <= -3:
        return "📉 【レベル1：押し目】", "一時的な調整。コツコツ買うなら絶好のタイミング。"
    return None, None # -3%より上の場合は通知対象外

def send_discord(message):
    if not WEBHOOK_URL:
        return
    data = {"content": message}
    requests.post(WEBHOOK_URL, json=data)

def main():
    # 日本時間に近い表記にするため（GitHubのサーバー時間に依存しますが目安として）
    now_str = datetime.now().strftime('%H:%M')
    
    alert_list = []
    print(f"パトロール開始...")
    
    for ticker in WATCH_LIST:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="2d")
            if len(df) < 2: continue
                
            prev_close = df['Close'].iloc[0]
            current_price = df['Close'].iloc[1]
            change_pct = ((current_price - prev_close) / prev_close) * 100
            
            # 異常（レベル1〜3）があるかチェック
            level_label, advice = get_status_info(change_pct)
            
            if level_label:
                unit = "円" if ".T" in ticker else "ドル"
                alert_list.append(f"{level_label} **{ticker}**\n価格: {current_price:.2f}{unit} ({change_pct:+.2f}%)\n💡 {advice}")
        except:
            continue

    # --- 送信ロジック ---
    if alert_list:
        # 異常があった場合：詳細なレポートを送信
        header = f"🔔 **【AI緊急通知】市場に変化あり ({now_str})**\n"
        footer = "\n━━━━━━━━━━━━━━━━"
        send_discord(header + "\n\n".join(alert_list) + footer)
        print("✅ 異常を検知し、詳細レポートを送信しました。")
    else:
        # 異常がない場合：「異常なし」という一言だけ送信
        send_discord(f"✅ {now_str}：パトロール完了。異常なし（全銘柄安定しています）")
        print("✅ 異常なし。一言通知のみ送信しました。")

if __name__ == "__main__":
    main()
