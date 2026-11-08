import telebot
import requests
import json
import re
import os
import random
from datetime import datetime
from flask import Flask, request

# === НАСТРОЙКИ ===
TG_TOKEN = 'ТВОЙ_ТОКЕН_ОТ_BOTFATHER'
HF_TOKEN = 'ТВОЙ_ТОКЕН_HUGGING_FACE'

DATA_FILE = 'data.json'
WEBHOOK_URL = 'https://твой-адрес.onrender.com/' + TG_TOKEN

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"my_debt": 90000, "mom_debt": 250000, "balance": 0, 
            "income_history": [], "expense_history": [], "debt_history": [], 
            "diary": [], "notes": "Ксюша любит уют, не любит шумные места."}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()
bot = telebot.TeleBot(TG_TOKEN)
app = Flask(__name__)

# === ФУНКЦИЯ ИИ ===
def ask_ai(text):
    try:
        API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        prompt = f"""Ты — добрый, спокойный помощник по имени Хеопс. 
Ты помогаешь студенту, который работает и гасит долги (свой 90к и мамин 250к). 
Ты общаешься просто, по-дружески, без пафоса и клоунады. 
Поддержи его, будь на его стороне. Отвечай кратко (2-3 предложения).

Сообщение пользователя: {text}
Твой ответ:"""
        
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=30)
        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            generated = result[0].get('generated_text', '')
            if 'Твой ответ:' in generated:
                return generated.split('Твой ответ:')[-1].strip()
            return generated.strip()
        return "Я тут, я с тобой. Расскажи подробнее? 🫂"
    except Exception as e:
        return f"ИИ сейчас отдыхает 😴 Но я запомнил: {text}. Напиши 'баланс' чтобы увидеть статистику!"

# === ОБРАБОТКА СООБЩЕНИЙ ===
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.lower().strip()
    original_text = message.text.strip()
    
    # 1. Помощь
    if text in ['помощь', 'help', 'команды']:
        help_text = """📋 **Команды Хеопса:**

💰 **Финансы:**
• `300 шаурма` — записать трату
• `зп самокат 3000` — записать доход
• `погасил свой 1000` — погасить свой долг
• `погасил мамин 2000` — погасить мамин долг
• `баланс` или `статистика` — посмотреть всё

📝 **Дневник:**
• `позанимался`, `съел шаурму`, `погулял` — запись в дневник

📌 **Заметки:**
• `заметка У Ксюши ДР 1 февраля` — сохранить заметку

💬 **Общение:**
Просто пиши что думаешь — я выслушаю! 🫂"""
        bot.reply_to(message, help_text)
        return

    # 2. Расход
    expense_match = re.match(r'^(\d+)\s+(.+)$', text)
    if expense_match and 'зп' not in text and 'погас' not in text:
        amount = int(expense_match.group(1))
        category = expense_match.group(2)
        data['balance'] -= amount
        data['expense_history'].append(f"{datetime.now().strftime('%d.%m')}: {amount}р - {category}")
        save_data(data)
        bot.reply_to(message, f"📉 Записал: {amount}р на {category}. Остаток: {data['balance']}р. Держись, всё идёт по плану! 💪")
        return

    # 3. Доход
    income_match = re.search(r'(зп|яндекс|самокат|подработка)\s*.*?(\d+)', text)
    if income_match:
        source = income_match.group(1).capitalize()
        amount = int(income_match.group(2))
        data['balance'] += amount
        data['income_history'].append(f"{datetime.now().strftime('%d.%m')}: {amount}р - {source}")
        save_data(data)
        bot.reply_to(message, f"💰 Отлично! Получил {amount}р от {source}. Баланс: {data['balance']}р. Каждый рубль приближает к цели! 🎯")
        return

    # 4. Погашение долга
    if 'погас' in text:
        debt_match = re.search(r'(\d+)', text)
        if debt_match:
            amount = int(debt_match.group(1))
            if 'мамин' in text or 'мам' in text:
                data['mom_debt'] -= amount
                save_data(data)
                bot.reply_to(message, f"🙌 Записал! Долг мамы теперь {data['mom_debt']}р. Вы большие молодцы! 💙")
            else:
                data['my_debt'] -= amount
                save_data(data)
                bot.reply_to(message, f"🔥 Супер! Твой долг теперь {data['my_debt']}р. Так держать! 🚀")
            return

    # 5. Дневник
    diary_keywords = ['позанимался', 'тренировк', 'съел', 'скушал', 'поел', 'выпил', 'поеш', 'поспал', 'погулял', 'поработал']
    if any(word in text for word in diary_keywords):
        data['diary'].append(f"{datetime.now().strftime('%d.%m %H:%M')}: {original_text}")
        save_data(data)
        responses = [
            f"✅ Записал: {original_text}. Ты молодец, что отслеживаешь! 🫂",
            f"📝 Принято: {original_text}. Главное — движение вперёд, ты справишься! 💪",
            f"🌟 Записал. Ты большой молодец, что заботишься о себе! 🙌"
        ]
        bot.reply_to(message, random.choice(responses))
        return

    # 6. Заметки
    if 'заметк' in text:
        note = re.sub(r'^заметк[ау]?\s*[:\-]?\s*', '', original_text, flags=re.IGNORECASE)
        if not note or note == original_text:
            note = original_text
        data['notes'] += f" {note}"
        save_data(data)
        bot.reply_to(message, f"📌 Запомнил: {note}")
        return

    # 7. Баланс
    if text in ['баланс', 'статистика', 'итог', 'день', 'долги']:
        stats = f"📊 **Твой баланс:** {data['balance']}р\n\n"
        stats += f"📉 **Долги:**\n"
        stats += f"  • Твой: {data['my_debt']}р\n"
        stats += f"  • Мамин: {data['mom_debt']}р\n"
        stats += f"  • **Итого:** {data['my_debt'] + data['mom_debt']}р\n\n"
        if data['expense_history'][-5:]:
            stats += "🛒 **Последние траты:**\n" + "\n".join(data['expense_history'][-5:]) + "\n\n"
        if data['income_history'][-5:]:
            stats += "💰 **Последние доходы:**\n" + "\n".join(data['income_history'][-5:]) + "\n\n"
        if data['diary'][-5:]:
            stats += "📝 **Дневник:**\n" + "\n".join(data['diary'][-5:])
        bot.reply_to(message, stats)
        return

    # 8. ИИ
    ai_response = ask_ai(original_text)
    bot.reply_to(message, ai_response)

# === WEBHOOK ===
@app.route('/' + TG_TOKEN, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return '', 200

@app.route('/')
def index():
    return 'Хеопс работает! 🤖'

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))