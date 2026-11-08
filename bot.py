import telebot
import requests
import json
import re
import os
from datetime import datetime
from flask import Flask, request

# === НАСТРОЙКИ ===
TG_TOKEN = os.environ.get('TG_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

if not TG_TOKEN or not GROQ_API_KEY:
    raise Exception("Токены не найдены! Проверь Environment Variables на Render.")

DATA_FILE = 'data.json'
WEBHOOK_URL = f'https://heops-bot.onrender.com/{TG_TOKEN}'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"my_debt": 90000, "mom_debt": 250000, "balance": 0, 
            "income_history": [], "expense_history": [], "debt_history": [], 
            "notes": "Ксюша любит уют, не любит шумные места."}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()
bot = telebot.TeleBot(TG_TOKEN)
app = Flask(__name__)

# === ИИ: ОПРЕДЕЛЕНИЕ КАТЕГОРИИ ЧЕРЕЗ GROQ ===
def get_category_from_ai(expense_text):
    """ИИ определяет категорию расхода"""
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama3-70b-8192",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты — классификатор расходов. Определи категорию для расхода. Ответь ТОЛЬКО одной категорией из списка: Еда, Напитки, Транспорт, Развлечения, Здоровье, Одежда, Бытовое, Связь, Другое. Не добавляй ничего больше."
                },
                {
                    "role": "user",
                    "content": f"Расход: {expense_text}. Категория:"
                }
            ],
            "temperature": 0.1,
            "max_tokens": 10
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            category = result['choices'][0]['message']['content'].strip()
            valid_categories = ['Еда', 'Напитки', 'Транспорт', 'Развлечения', 'Здоровье', 'Одежда', 'Бытовое', 'Связь', 'Другое']
            if category in valid_categories:
                return category
        
        return None
        
    except Exception as e:
        return None

# === ЛОКАЛЬНЫЕ ПРАВИЛА (FALLBACK) ===
def get_category_local(expense_text):
    """Локальное определение категории, если ИИ не ответил"""
    text = expense_text.lower()
    
    categories = {
        'Еда': ['шаурм', 'пицц', 'бургер', 'суш', 'ролл', 'рамен', 'борщ', 'суп', 'каш', 'мяс', 'колбас', 'сыр', 'хлеб', 'молок', 'яйц', 'фрукт', 'овощ', 'снек', 'печень', 'шоколад', 'конфет'],
        'Напитки': ['вод', 'чай', 'кофе', 'сок', 'газировк', 'энергетик', 'ред булл', 'monster', 'burn', 'алкоголь', 'пиво', 'вин', 'водк'],
        'Транспорт': ['такси', 'автобус', 'метро', 'трамвай', 'бензин', 'топлив', 'парковк', 'самокат', 'каршеринг'],
        'Развлечения': ['кино', 'игр', 'cs', 'steam', 'playstation', 'xbox', 'подписк', 'нетфликс', 'spotify'],
        'Здоровье': ['аптек', 'лекарств', 'врач', 'больниц', 'спортзал', 'тренировк'],
        'Одежда': ['одежд', 'обувь', 'куртк', 'джинс', 'футболк'],
        'Бытовое': ['бытов', 'уборк', 'стирк', 'шампун', 'мыл', 'туалет', 'зубн'],
        'Связь': ['интернет', 'телефон', 'мобильн', 'сим', 'роуминг'],
    }
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text:
                return category
    
    return 'Другое'

def get_category(expense_text):
    """Сначала пробуем ИИ, если не получилось — локальные правила"""
    ai_category = get_category_from_ai(expense_text)
    if ai_category:
        return ai_category
    return get_category_local(expense_text)

# === ОБРАБОТКА СООБЩЕНИЙ ===
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.lower().strip() if message.text else ''
    original_text = message.text.strip() if message.text else ''
    
    # Поддержка и обычных команд, и слэш-команд
    is_command = text.startswith('/')
    command = text[1:] if is_command else text
    
    # Если просто слэш без команды — показать помощь
    if is_command and not command:
        command = 'помощь'
    
    # 1. Помощь
    if command in ['помощь', 'help', 'команды', '']:
        help_text = """📋 **Хеопс — твой финансовый помощник:**

💰 **Финансы:**
• `300 шаурма` — записать трату (ИИ определит категорию)
• `зп самокат 3000` — записать доход
• `погасил свой 1000` — погасить свой долг
• `погасил мамин 2000` — погасить мамин долг
• `/баланс` или `/balance` — общая статистика
• `/категории` или `/categories` — анализ расходов с %

📌 **Ксюша:**
• `/заметка Ксюша любит рамен` — добавить заметку
• `/ксюша` или `/ksyusha` — показать все заметки о Ксюше

💡 **Совет:** Напиши `/` чтобы увидеть меню команд!"""
        bot.reply_to(message, help_text)
        return

    # 2. Расход с ИИ-категоризацией
    expense_match = re.match(r'^(\d+)\s+(.+)$', text)
    if expense_match and 'зп' not in text and 'погас' not in text:
        amount = int(expense_match.group(1))
        category_text = expense_match.group(2)
        
        category = get_category(category_text)
        
        data['balance'] -= amount
        data['expense_history'].append(f"{datetime.now().strftime('%d.%m')}: {amount}р - {category_text} [{category}]")
        save_data(data)
        bot.reply_to(message, f"📉 Записал: {amount}р на {category_text}\n📂 Категория: {category}\n💰 Остаток: {data['balance']}р")
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

    # 5. Анализ по категориям с процентами
    if command in ['категории', 'анализ', 'статистика расходов', 'categories']:
        if not data['expense_history']:
            bot.reply_to(message, "Пока нет расходов для анализа. Запиши первую трату! 📝")
            return
        
        category_totals = {}
        total_expenses = 0
        
        for expense in data['expense_history']:
            match = re.search(r': (\d+)р - .+ \[(.+)\]', expense)
            if match:
                amount = int(match.group(1))
                category = match.group(2)
                category_totals[category] = category_totals.get(category, 0) + amount
                total_expenses += amount
        
        if total_expenses == 0:
            bot.reply_to(message, "Не удалось проанализировать расходы.")
            return
        
        report = "📊 **Анализ расходов по категориям:**\n\n"
        report += f"💸 **Всего потрачено:** {total_expenses}р\n\n"
        
        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        
        for category, amount in sorted_categories:
            percentage = (amount / total_expenses) * 100
            bar_length = int(percentage / 5)
            bar = '█' * bar_length + '░' * (20 - bar_length)
            report += f"**{category}:** {amount}р ({percentage:.1f}%)\n{bar}\n\n"
        
        bot.reply_to(message, report)
        return

    # 6. Заметки о Ксюше
    if command.startswith('заметк') or command.startswith('note'):
        note = re.sub(r'^(заметк[ау]?|note)\s*[:\-]?\s*', '', original_text, flags=re.IGNORECASE)
        if not note or note == original_text:
            note = original_text
        data['notes'] += f"{datetime.now().strftime('%d.%m')}: {note}\n"
        save_data(data)
        bot.reply_to(message, f"📌 Запомнил: {note}. Ксюша оценит твою внимательность! 💙")
        return

    # 7. Показать все заметки о Ксюше
    if command in ['ксюша', 'ksyusha']:
        notes = data.get('notes', '')
        if not notes or notes.strip() == '':
            bot.reply_to(message, "📝 Пока нет заметок о Ксюше.\n\nДобавь первую: `/заметка Ксюша любит рамен`")
            return
        
        report = "💙 **Всё о Ксюше:**\n\n"
        report += notes
        report += "\n⚠️ Не забывай: ДР Ксюши — 1 февраля!"
        
        bot.reply_to(message, report)
        return

    # 8. Баланс и статистика
    if command in ['баланс', 'статистика', 'итог', 'день', 'долги', 'balance']:
        stats = f"📊 **Твой баланс:** {data['balance']}р\n\n"
        stats += f"📉 **Долги:**\n"
        stats += f"  • Твой: {data['my_debt']}р\n"
        stats += f"  • Мамин: {data['mom_debt']}р\n"
        stats += f"  • **Итого:** {data['my_debt'] + data['mom_debt']}р\n\n"
        if data['expense_history'][-5:]:
            stats += "🛒 **Последние траты:**\n" + "\n".join(data['expense_history'][-5:]) + "\n\n"
        if data['income_history'][-5:]:
            stats += "💰 **Последние доходы:**\n" + "\n".join(data['income_history'][-5:]) + "\n\n"
        bot.reply_to(message, stats)
        return

    # 9. Всё остальное
    bot.reply_to(message, "Я помогаю только с учётом финансов и напоминаниями о Ксюше. 😊\n\nНапиши `/` чтобы увидеть меню команд!")

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
