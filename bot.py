import telebot
import requests
import threading
import time
from datetime import datetime

# ========================= НАЛАШТУВАННЯ =========================
BOT_TOKEN = "8865777967:AAE0j_oJM-Rf3kesv-wtYaKKDx2S43ElK68"

LEVERAGE = 12
TARGET_PROFIT_PCT = 25
STOP_LOSS_PCT = 12
AUTO_TOP_INTERVAL = 30          # хвилин
STRONG_MOVE_THRESHOLD = 10      # % для сильного руху

bot = telebot.TeleBot(BOT_TOKEN)
chat_id_for_auto = None


def get_binance_data(symbol: str):
    try:
        symbol = symbol.upper().replace("USDT", "") + "USDT"
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
        response = requests.get(url, timeout=8)
        if response.status_code != 200:
            return None
        data = response.json()
        return {
            'name': symbol.replace('USDT', ''),
            'price': float(data.get('lastPrice', 0)),
            'change': float(data.get('priceChangePercent', 0)),
            'volume': float(data.get('volume', 0)),
        }
    except:
        return None


def analyze_market(change: float, volume: float):
    if volume < 800000:
        return "⚪ Низька ліквідність", "Об’єм занадто низький"

    if change > 10:
        return "🟢 LONG (Дуже сильний)", "Потужний висхідний тренд"
    elif change > 5:
        return "🟢 LONG (Потужний)", "Сильний висхідний тренд"
    elif change > 2:
        return "🟡 LONG (Помірний)", "Позитивна динаміка"
    elif change > -3:
        return "⚪ Чекати", "Боковий рух"
    elif change > -8:
        return "🔴 SHORT (Корекція)", "Продавці набирають силу"
    else:
        return "🔴 SHORT (Паніка)", "Високий ризик падіння"


def get_top_coins():
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        usdt_pairs = [item for item in data if item['symbol'].endswith('USDT')]
        top = sorted(usdt_pairs, key=lambda x: float(x['priceChangePercent']), reverse=True)[:10]
        
        text = f"🔥 **ТОП-10 за 24 години** • {datetime.now().strftime('%H:%M')}\n\n"
        
        for coin in top:
            symbol = coin['symbol'].replace('USDT', '')
            change = float(coin['priceChangePercent'])
            price = float(coin['lastPrice'])
            
            if change > 5:
                signal = "🟢 LONG"
            elif change > 0:
                signal = "🟡 LONG"
            elif change > -5:
                signal = "⚪"
            else:
                signal = "🔴 SHORT"
            
            text += f"{signal} **{symbol}** `{price:.4f}` | `{change:+.2f}%`\n"
        
        return text
    except:
        return "❌ Не вдалося отримати топ."


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, 
        "🤖 **Cryptolombard Bot**\n\n"
        "Надішли тікер: `BTC`, `ETH`, `SOL`...\n"
        "/top — ТОП монет", 
        parse_mode="Markdown")


@bot.message_handler(commands=['top'])
def top_coins(message):
    global chat_id_for_auto
    chat_id_for_auto = message.chat.id
    bot.reply_to(message, get_top_coins(), parse_mode="Markdown")


@bot.message_handler(func=lambda message: True)
def chat(message):
    text = message.text.strip().upper()
    symbol = text.replace('/', '').replace('USDT', '').strip()
    if len(symbol) < 2:
        return

    info = get_binance_data(symbol)
    if not info or info['price'] == 0:
        bot.reply_to(message, "❌ Монету не знайдено.")
        return

    direction, reason = analyze_market(info['change'], info['volume'])

    price_change_tp = (TARGET_PROFIT_PCT / LEVERAGE) / 100
    price_change_sl = (STOP_LOSS_PCT / LEVERAGE) / 100
    entry = info['price']

    if "LONG" in direction or "Чекати" in direction:
        tp_price = entry * (1 + price_change_tp)
        sl_price = entry * (1 - price_change_sl)
    else:
        tp_price = entry * (1 - price_change_tp)
        sl_price = entry * (1 + price_change_sl)

    text_out = f"""
━━━━━━━━━━━━━━━━━━
⚡ **{info['name']}/USDT**
━━━━━━━━━━━━━━━━━━

💰 **Ціна:** `{entry:.4f}`
📊 **Зміна 24г:** `{info['change']:+.2f}%`
📈 **Сигнал:** {direction}
💡 **Аналіз:** {reason}

⚙️ **Плече:** `{LEVERAGE}x`
🎯 **TP ({TARGET_PROFIT_PCT}%):** `{tp_price:.4f}`
🛑 **SL ({STOP_LOSS_PCT}%):** `{sl_price:.4f}`
━━━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime("%H:%M:%S")}
    """

    bot.reply_to(message, text_out.strip(), parse_mode="Markdown")


# ========================= АВТО СПОВІЩЕННЯ ПРО СИЛЬНІ РУХИ =========================
def strong_moves_monitor():
    known_moves = {}
    while True:
        if not chat_id_for_auto:
            time.sleep(60)
            continue
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            data = requests.get(url, timeout=10).json()
            for item in data:
                if not item['symbol'].endswith('USDT'):
                    continue
                symbol = item['symbol'].replace('USDT', '')
                change = float(item['priceChangePercent'])
                if abs(change) >= STRONG_MOVE_THRESHOLD:
                    key = f"{symbol}_{int(change)}"
                    if key not in known_moves:
                        known_moves[key] = True
                        direction = "🟢 **СИЛЬНЕ ЗРОСТАННЯ**" if change > 0 else "🔴 **СИЛЬНЕ ПАДІННЯ**"
                        msg = f"{direction}\n**{symbol}** `{change:+.2f}%`"
                        bot.send_message(chat_id_for_auto, msg, parse_mode="Markdown")
        except:
            pass
        time.sleep(300)  # перевіряти кожні 5 хвилин


if __name__ == "__main__":
    print("✅ Бот запущений!")
    print("Автооновлення топу та сповіщення про сильні рухи активні")
    
    threading.Thread(target=strong_moves_monitor, daemon=True).start()
    threading.Thread(target=lambda: time.sleep(AUTO_TOP_INTERVAL*60) or bot.send_message(chat_id_for_auto, get_top_coins(), parse_mode="Markdown") if chat_id_for_auto else None, daemon=True).start()
    
    bot.infinity_polling()
