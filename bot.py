import telebot
import requests
import json
import re
import os
from datetime import datetime, timedelta
from flask import Flask, request
import time
import threading
from telebot import types

# === НАСТРОЙКИ ===
TG_TOKEN = os.environ.get('TG_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

if not TG_TOKEN or not GROQ_API_KEY:
    raise Exception("Токены не найдены!")

DATA_FILE = 'data.json'
WEBHOOK_URL = f'https://heops-bot.onrender.com/{TG_TOKEN}'

ZHENYA_ID = 368734185
KSYUSHA_ID = 1981878862

USERS = {ZHENYA_ID: "Женя", KSYUSHA_ID: "Ксюша"}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if str(KSYUSHA_ID) in data.get('users', {}):
            if 'my_debt' not in data['users'][str(KSYUSHA_ID)]:
                data['users'][str(KSYUSHA_ID)]['my_debt'] = 150000
        if str(ZHENYA_ID) in data.get('users', {}):
            if 'my_debt' not in data['users'][str(ZHENYA_ID)]:
                data['users'][str(ZHENYA_ID)]['my_debt'] = 90000
        if str(ZHENYA_ID) in data.get('users', {}):
            if 'mom_debt' in data['users'][str(ZHENYA_ID)]:
                del data['users'][str(ZHENYA_ID)]['mom_debt']
        if 'write_queue' not in data:
            data['write_queue'] = {str(ZHENYA_ID): None, str(KSYUSHA_ID): None}
        save_data(data)
        return data
    return {
        "users": {
            str(ZHENYA_ID): {"name": "Женя", "balance": 0, "my_debt": 90000, "income_history": [], "expense_history": [], "notes": ""},
            str(KSYUSHA_ID): {"name": "Ксюша", "balance": 0, "my_debt": 150000, "income_history": [], "expense_history": [], "notes": ""}
        },
        "emotions": {str(ZHENYA_ID): {"date": "", "text": "", "sent": False, "waiting": False}, str(KSYUSHA_ID): {"date": "", "text": "", "sent": False, "waiting": False}},
        "write_queue": {str(ZHENYA_ID): None, str(KSYUSHA_ID): None}
    }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()
bot = telebot.TeleBot(TG_TOKEN)
app = Flask(__name__)

def get_partner_id(user_id):
    return KSYUSHA_ID if user_id == ZHENYA_ID else ZHENYA_ID

def get_partner_command(user_id):
    return "/она" if user_id == ZHENYA_ID else "/он"

def send(chat_id, text):
    try:
        bot.send_message(chat_id, text, parse_mode=None)
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        try:
            bot.send_message(chat_id, str(text))
        except:
            pass

# === КАТЕГОРИЗАЦИЯ ===
def get_category_from_ai(expense_text):
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "Определи категорию расхода. Ответь ТОЛЬКО одной: Еда, Напитки, Транспорт, Развлечения, Здоровье, Одежда, Бытовое, Связь, Другое."},
                {"role": "user", "content": f"Расход: {expense_text}. Категория:"}
            ],
            "temperature": 0.1,
            "max_tokens": 10
        }
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            category = result['choices'][0]['message']['content'].strip()
            valid_categories = ['Еда', 'Напитки', 'Транспорт', 'Развлечения', 'Здоровье', 'Одежда', 'Бытовое', 'Связь', 'Другое']
            if category in valid_categories:
                return category
        return None
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return None

def get_category_local(expense_text):
    text = expense_text.lower()
    categories = {
        'Еда': ['шаурм', 'пицц', 'бургер', 'суш', 'ролл', 'рамен', 'борщ', 'суп', 'каш', 'мяс', 'колбас', 'сыр', 'хлеб', 'молок', 'яйц', 'фрукт', 'овощ', 'снек', 'печень', 'шоколад', 'конфет', 'пельмен', 'вареник', 'блин', 'ростикс', 'kfc', 'кфс', 'мак', 'макдональдс', 'вкусно', 'точка', 'вквс', 'бургер кинг', 'subway', 'сабвей', 'domino', 'домино', 'папа джонс', 'теремок', 'крошка', 'картошк', 'шашлык', 'ресторан', 'кафе', 'столов', 'бистро', 'фудкорт', 'обед', 'ужин', 'завтрак', 'ланч', 'перекус', 'поел', 'вок', 'итальян', 'грузин', 'хачапур', 'хинкал', 'плов', 'лаваш', 'фалафель', 'кебаб', 'чебурек', 'пышк', 'торт', 'пирожн', 'морожен', 'десерт'],
        'Напитки': ['вод', 'чай', 'кофе', 'сок', 'газировк', 'энергетик', 'ред булл', 'monster', 'burn', 'алкоголь', 'пиво', 'вин', 'водк', 'starbucks', 'кофе хаус', 'шоколадниц', 'кофейня', 'лимонад', 'квас', 'морс', 'смузи', 'латте', 'капучин', 'американо', 'эспрессо', 'матча'],
        'Транспорт': ['такси', 'автобус', 'метро', 'трамвай', 'бензин', 'топлив', 'парковк', 'самокат', 'каршеринг', 'uber', 'убер', 'поезд', 'электричк', 'авиабилет', 'самолет', 'билет', 'проезд', 'троллейбус', 'маршрутк'],
        'Развлечения': ['кино', 'игр', 'cs', 'steam', 'playstation', 'xbox', 'подписк', 'нетфликс', 'spotify', 'концерт', 'театр', 'выставк', 'музей', 'бар', 'клуб', 'караок', 'боулинг', 'бильярд', 'квест', 'парк', 'аттракцион'],
        'Здоровье': ['аптек', 'лекарств', 'врач', 'больниц', 'спортзал', 'тренировк', 'фитнес', 'йога', 'бассейн', 'массаж', 'стоматолог', 'зуб', 'анализ', 'витамины'],
        'Одежда': ['одежд', 'обувь', 'куртк', 'джинс', 'футболк', 'кроссовк', 'ботинк', 'сумк', 'рюкзак', 'часы', 'украшен'],
        'Бытовое': ['бытов', 'уборк', 'стирк', 'шампун', 'мыл', 'туалет', 'зубн', 'порошок', 'ремонт', 'инструмент', 'лампочк'],
        'Связь': ['интернет', 'телефон', 'мобильн', 'сим', 'роуминг', 'мтс', 'билайн', 'мегафон', 'теле2', 'йота'],
    }
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text:
                return category
    return 'Другое'

def get_category(expense_text):
    ai_category = get_category_from_ai(expense_text)
    if ai_category:
        return ai_category
    return get_category_local(expense_text)

# === СТАТИСТИКА ===
def get_week_stats(user_data, user_name):
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    lines = []
    lines.append(f"👤 {user_name} — последние 7 дней:")
    lines.append("")
    lines.append(f"💰 Баланс: {user_data['balance']}р")
    if user_data.get('my_debt'):
        lines.append(f"📉 Долг: {user_data['my_debt']}р")
    lines.append("")
    daily_expenses = {}
    total_week_expenses = 0
    for expense in user_data.get('expense_history', []):
        date_str = expense.split(':')[0]
        try:
            exp_date = datetime.strptime(date_str, '%d.%m')
            if exp_date >= week_ago:
                if date_str not in daily_expenses:
                    daily_expenses[date_str] = []
                daily_expenses[date_str].append(expense.split(': ', 1)[1])
                amount = int(re.search(r'(\d+)р', expense).group(1))
                total_week_expenses += amount
        except:
            pass
    if daily_expenses:
        lines.append(f"📉 Расходы за неделю: {total_week_expenses}р")
        for date in sorted(daily_expenses.keys(), reverse=True):
            lines.append("")
            lines.append(f"📅 {date}:")
            for exp in daily_expenses[date]:
                lines.append(f"  • {exp}")
    else:
        lines.append("📉 Расходов за неделю нет.")
    daily_incomes = {}
    total_week_income = 0
    for income in user_data.get('income_history', []):
        date_str = income.split(':')[0]
        try:
            inc_date = datetime.strptime(date_str, '%d.%m')
            if inc_date >= week_ago:
                if date_str not in daily_incomes:
                    daily_incomes[date_str] = []
                daily_incomes[date_str].append(income.split(': ', 1)[1])
                amount = int(re.search(r'(\d+)р', income).group(1))
                total_week_income += amount
        except:
            pass
    if daily_incomes:
        lines.append("")
        lines.append(f"💰 Доходы за неделю: {total_week_income}р")
        for date in sorted(daily_incomes.keys(), reverse=True):
            lines.append("")
            lines.append(f"📅 {date}:")
            for inc in daily_incomes[date]:
                lines.append(f"  • {inc}")
    else:
        lines.append("")
        lines.append("💰 Доходов за неделю нет.")
    return '\n'.join(lines)

def get_month_stats(user_data, user_name):
    today = datetime.now()
    current_month = today.month
    current_year = today.year
    month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    lines = []
    lines.append(f"👤 {user_name} — {month_names[current_month-1]} {current_year}")
    lines.append("")
    lines.append(f"💰 Баланс: {user_data['balance']}р")
    if user_data.get('my_debt'):
        lines.append(f"📉 Долг: {user_data['my_debt']}р")
    lines.append("")
    daily_expenses = {}
    total_month_expenses = 0
    for expense in user_data.get('expense_history', []):
        date_str = expense.split(':')[0]
        try:
            exp_date = datetime.strptime(date_str, '%d.%m')
            if exp_date.month == current_month and exp_date.year == current_year:
                if date_str not in daily_expenses:
                    daily_expenses[date_str] = []
                daily_expenses[date_str].append(expense.split(': ', 1)[1])
                amount = int(re.search(r'(\d+)р', expense).group(1))
                total_month_expenses += amount
        except:
            pass
    category_totals = {}
    for expense in user_data.get('expense_history', []):
        date_str = expense.split(':')[0]
        try:
            exp_date = datetime.strptime(date_str, '%d.%m')
            if exp_date.month == current_month and exp_date.year == current_year:
                match = re.search(r'\[(.+)\]', expense)
                if match:
                    cat = match.group(1)
                    amount = int(re.search(r'(\d+)р', expense).group(1))
                    category_totals[cat] = category_totals.get(cat, 0) + amount
        except:
            pass
    if daily_expenses:
        lines.append(f"📉 Расходы за месяц: {total_month_expenses}р")
        for date in sorted(daily_expenses.keys(), reverse=True):
            lines.append("")
            lines.append(f"📅 {date}:")
            for exp in daily_expenses[date]:
                lines.append(f"  • {exp}")
    else:
        lines.append("📉 Расходов за месяц нет.")
    daily_incomes = {}
    total_month_income = 0
    for income in user_data.get('income_history', []):
        date_str = income.split(':')[0]
        try:
            inc_date = datetime.strptime(date_str, '%d.%m')
            if inc_date.month == current_month and inc_date.year == current_year:
                if date_str not in daily_incomes:
                    daily_incomes[date_str] = []
                daily_incomes[date_str].append(income.split(': ', 1)[1])
                amount = int(re.search(r'(\d+)р', income).group(1))
                total_month_income += amount
        except:
            pass
    if daily_incomes:
        lines.append("")
        lines.append(f"💰 Доходы за месяц: {total_month_income}р")
        for date in sorted(daily_incomes.keys(), reverse=True):
            lines.append("")
            lines.append(f"📅 {date}:")
            for inc in daily_incomes[date]:
                lines.append(f"  • {inc}")
    else:
        lines.append("")
        lines.append("💰 Доходов за месяц нет.")
    if category_totals:
        lines.append("")
        lines.append("📊 По категориям:")
        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        for cat, amount in sorted_cats:
            percentage = (amount / total_month_expenses) * 100 if total_month_expenses > 0 else 0
            lines.append(f"  {cat}: {amount}р ({percentage:.1f}%)")
    return '\n'.join(lines)

def get_year_stats(user_data, user_name):
    today = datetime.now()
    current_year = today.year
    lines = []
    lines.append(f"👤 {user_name} — {current_year} год")
    lines.append("")
    lines.append(f"💰 Баланс: {user_data['balance']}р")
    if user_data.get('my_debt'):
        lines.append(f"📉 Долг: {user_data['my_debt']}р")
    lines.append("")
    month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    monthly_expenses = {}
    monthly_incomes = {}
    total_year_expenses = 0
    total_year_income = 0
    for expense in user_data.get('expense_history', []):
        date_str = expense.split(':')[0]
        try:
            exp_date = datetime.strptime(date_str, '%d.%m')
            if exp_date.year == current_year:
                month_key = exp_date.month
                if month_key not in monthly_expenses:
                    monthly_expenses[month_key] = 0
                amount = int(re.search(r'(\d+)р', expense).group(1))
                monthly_expenses[month_key] += amount
                total_year_expenses += amount
        except:
            pass
    for income in user_data.get('income_history', []):
        date_str = income.split(':')[0]
        try:
            inc_date = datetime.strptime(date_str, '%d.%m')
            if inc_date.year == current_year:
                month_key = inc_date.month
                if month_key not in monthly_incomes:
                    monthly_incomes[month_key] = 0
                amount = int(re.search(r'(\d+)р', income).group(1))
                monthly_incomes[month_key] += amount
                total_year_income += amount
        except:
            pass
    lines.append(f"📉 Расходы за год: {total_year_expenses}р")
    lines.append(f"💰 Доходы за год: {total_year_income}р")
    lines.append(f"💵 Разница: {total_year_income - total_year_expenses}р")
    lines.append("")
    lines.append("По месяцам:")
    for month_num in range(1, 13):
        exp = monthly_expenses.get(month_num, 0)
        inc = monthly_incomes.get(month_num, 0)
        if exp > 0 or inc > 0:
            lines.append("")
            lines.append(f"📅 {month_names[month_num-1]}:")
            if exp > 0:
                lines.append(f"  📉 Расходы: {exp}р")
            if inc > 0:
                lines.append(f"  💰 Доходы: {inc}р")
    return '\n'.join(lines)

def get_now_stats(user_data, user_name):
    lines = []
    lines.append(f"⚡ {user_name} — прямо сейчас:")
    lines.append("")
    lines.append(f"💰 Баланс: {user_data['balance']}р")
    if user_data.get('my_debt'):
        lines.append(f"📉 Долг: {user_data['my_debt']}р")
    lines.append("")
    all_transactions = []
    for expense in user_data.get('expense_history', []):
        date_str = expense.split(':')[0]
        all_transactions.append({'date': date_str, 'text': expense.split(': ', 1)[1], 'type': 'expense'})
    for income in user_data.get('income_history', []):
        date_str = income.split(':')[0]
        all_transactions.append({'date': date_str, 'text': income.split(': ', 1)[1], 'type': 'income'})
    all_transactions.sort(key=lambda x: x['date'], reverse=True)
    if all_transactions:
        lines.append("📋 Последние 10 операций:")
        for trans in all_transactions[:10]:
            icon = '📉' if trans['type'] == 'expense' else '💰'
            lines.append(f"{icon} {trans['date']}: {trans['text']}")
    else:
        lines.append("📋 Операций пока нет.")
    return '\n'.join(lines)

def get_categories_stats(user_data, user_name):
    if not user_data.get('expense_history'):
        return "Пока нет расходов."
    category_totals = {}
    total_expenses = 0
    for expense in user_data['expense_history']:
        match = re.search(r': (\d+)р - .+ \[(.+)\]', expense)
        if match:
            amount = int(match.group(1))
            category = match.group(2)
            category_totals[category] = category_totals.get(category, 0) + amount
            total_expenses += amount
    lines = []
    lines.append(f"📊 Анализ расходов {user_name}:")
    lines.append("")
    lines.append(f"💸 Всего: {total_expenses}р")
    lines.append("")
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    for category, amount in sorted_categories:
        percentage = (amount / total_expenses) * 100
        lines.append(f"{category}: {amount}р ({percentage:.1f}%)")
    return '\n'.join(lines)

# === ОБРАБОТКА СООБЩЕНИЙ ===
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_id = message.from_user.id
        user_name = USERS.get(user_id)
        if not user_name:
            send(message.chat.id, "Привет! Этот бот только для Жени и Ксюши.")
            return
        partner_id = get_partner_id(user_id)
        partner_name = USERS.get(partner_id, "Партнёр")
        partner_command = get_partner_command(user_id)
        text = message.text.lower().strip() if message.text else ''
        original_text = message.text.strip() if message.text else ''
        is_command = text.startswith('/')
        command = text[1:] if is_command else text
        if is_command and not command:
            command = 'help'
        if data['write_queue'].get(str(user_id)) == 'waiting':
            data['write_queue'][str(user_id)] = {"text": original_text, "date": datetime.now().strftime('%d.%m %H:%M'), "sent": False}
            save_data(data)
            send(message.chat.id, f"✅ Записал! Сообщение отправится {partner_name} завтра утром в 9:00.\n\nТвой текст: \"{original_text}\"")
            return
        if command in ['помощь', 'help', 'команды', '']:
            help_text = f"""Хеопс — для {user_name}:

💰 Твой бюджет:
• 300 шаурма или шаурма 300 — расход
• зп самокат 3000 — доход
• погасил долг 1000 — погашение

📊 Статистика:
• /now или /сейчас — баланс и операции прямо сейчас
• /ya, /я или баланс — за 7 дней
• /month или /месяц — календарный месяц
• /year или /год — календарный год
• {partner_command} или /ona — бюджет {partner_name}
• /categories — по категориям

💙 Эмоции и связь:
• /day или /день — сообщение {partner_name} за вчера
• /write — написать {partner_name} (придёт утром в 9:00)
• /status или /статус — статус

📌 Заметки:
• /note текст — заметка о {partner_name} (автоматически)

⚙️ Для разработчика:
• /reset — полный сброс истории"""
            send(message.chat.id, help_text)
            return
        expense_match_1 = re.match(r'^(\d+)\s+(.+)$', text)
        expense_match_2 = re.match(r'^(.+?)\s+(\d+)$', text)
        if (expense_match_1 or expense_match_2) and 'зп' not in text and 'погас' not in text:
            if expense_match_1:
                amount = int(expense_match_1.group(1))
                category_text = expense_match_1.group(2)
            else:
                amount = int(expense_match_2.group(2))
                category_text = expense_match_2.group(1)
            category = get_category(category_text)
            user_data = data['users'][str(user_id)]
            user_data['balance'] -= amount
            user_data['expense_history'].append(f"{datetime.now().strftime('%d.%m')}: {amount}р - {category_text} [{category}]")
            save_data(data)
            send(message.chat.id, f"📉 Записал: {amount}р на {category_text}\nКатегория: {category}\nОстаток: {user_data['balance']}р")
            return
        income_match = re.search(r'(зп|яндекс|самокат|подработка)\s*.*?(\d+)', text)
        if income_match:
            source = income_match.group(1).capitalize()
            amount = int(income_match.group(2))
            user_data = data['users'][str(user_id)]
            user_data['balance'] += amount
            user_data['income_history'].append(f"{datetime.now().strftime('%d.%m')}: {amount}р - {source}")
            save_data(data)
            send(message.chat.id, f"💰 Получил {amount}р от {source}. Баланс: {user_data['balance']}р.")
            return
        if 'погас' in text:
            debt_match = re.search(r'(\d+)', text)
            if debt_match:
                amount = int(debt_match.group(1))
                user_data = data['users'][str(user_id)]
                user_data['my_debt'] = user_data.get('my_debt', 0) - amount
                save_data(data)
                send(message.chat.id, f"🔥 Твой долг теперь {user_data['my_debt']}р.")
                return
        if command in ['сейчас', 'now', 'прямо сейчас']:
            user_data = data['users'][str(user_id)]
            send(message.chat.id, get_now_stats(user_data, user_name))
            return
        if command in ['я', 'мне', 'moi', 'ya', 'balance', 'баланс', 'статистика', 'неделя', 'week']:
            user_data = data['users'][str(user_id)]
            send(message.chat.id, get_week_stats(user_data, user_name))
            return
        if command in ['месяц', 'month']:
            user_data = data['users'][str(user_id)]
            send(message.chat.id, get_month_stats(user_data, user_name))
            return
        if command in ['год', 'year']:
            user_data = data['users'][str(user_id)]
            send(message.chat.id, get_year_stats(user_data, user_name))
            return
        if command in ['она', 'он', 'partner', 'ona']:
            partner_data = data['users'][str(partner_id)]
            send(message.chat.id, get_week_stats(partner_data, partner_name))
            return
        if command in ['категории', 'анализ', 'categories']:
            user_data = data['users'][str(user_id)]
            send(message.chat.id, get_categories_stats(user_data, user_name))
            return
        if command in ['день', 'day']:
            partner_emotion = data['emotions'].get(str(partner_id), {})
            if not partner_emotion.get('text'):
                send(message.chat.id, f"{partner_name} ещё не поделился эмоциями.")
                return
            send(message.chat.id, f"💙 {partner_name} ({partner_emotion.get('date')}):\n\n{partner_emotion['text']}")
            return
        if command in ['write', 'написать']:
            data['write_queue'][str(user_id)] = 'waiting'
            save_data(data)
            send(message.chat.id, f"✍️ Напиши сообщение для {partner_name}. Оно отправится завтра утром в 9:00.")
            return
        if command in ['статус', 'status']:
            partner_emotion = data['emotions'].get(str(partner_id), {})
            today = datetime.now().strftime('%d.%m')
            if partner_emotion.get('date') == today:
                send(message.chat.id, f"✅ {partner_name} уже поделился эмоциями сегодня!")
            else:
                send(message.chat.id, f"⏳ {partner_name} ещё не ответил сегодня.")
            return
        if command.startswith('заметк') or command.startswith('note'):
            note_text = re.sub(r'^(заметк[ау]?|note)\s*[:\-]?\s*', '', original_text, flags=re.IGNORECASE)
            if not note_text or note_text == original_text:
                send(message.chat.id, f"Напиши: /note [текст о {partner_name}]")
                return
            data['users'][str(partner_id)]['notes'] += f"{datetime.now().strftime('%d.%m')}: {note_text}\n"
            save_data(data)
            send(message.chat.id, f"✅ Заметка сохранена!\n\nТекст: {note_text}\nСохранено в профиль: {partner_name}\nДата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n{partner_name} увидит это, когда напишет /ksyusha или /zhenya")
            return
        if command in ['ксюша', 'ksyusha']:
            notes = data['users'][str(KSYUSHA_ID)].get('notes', '')
            if not notes or notes.strip() == '':
                send(message.chat.id, "📝 Пока нет заметок о Ксюше.")
                return
            send(message.chat.id, f"💙 Всё о Ксюше:\n\n{notes}\n⚠️ ДР Ксюши — 1 февраля!")
            return
        if command in ['женя', 'zhenya']:
            notes = data['users'][str(ZHENYA_ID)].get('notes', '')
            if not notes or notes.strip() == '':
                send(message.chat.id, "📝 Пока нет заметок о Жене.")
                return
            send(message.chat.id, f"💪 Всё о Жене:\n\n{notes}")
            return
        if command in ['start', 'старт']:
            send(message.chat.id, f"Привет, {user_name}! Напиши /help чтобы увидеть все команды!")
            return
        if command == 'reset':
            if user_id != ZHENYA_ID:
                send(message.chat.id, "🚫 Эта команда доступна только разработчику.")
                return
            data = {"users": {str(ZHENYA_ID): {"name": "Женя", "balance": 0, "my_debt": 90000, "income_history": [], "expense_history": [], "notes": ""}, str(KSYUSHA_ID): {"name": "Ксюша", "balance": 0, "my_debt": 150000, "income_history": [], "expense_history": [], "notes": ""}}, "emotions": {str(ZHENYA_ID): {"date": "", "text": "", "sent": False, "waiting": False}, str(KSYUSHA_ID): {"date": "", "text": "", "sent": False, "waiting": False}}, "write_queue": {str(ZHENYA_ID): None, str(KSYUSHA_ID): None}}
            save_data(data)
            send(message.chat.id, "🗑 ИСТОРИЯ ПОЛНОСТЬЮ ОЧИЩЕНА!\n\n✅ Балансы обнулены (0р)\n✅ Долги восстановлены (Женя: 90к, Ксюша: 150к)\n✅ Все траты, доходы, заметки и сообщения удалены\n\nМожно начинать с чистого листа!")
            return
        if data['emotions'].get(str(user_id), {}).get('waiting', False):
            data['emotions'][str(user_id)] = {"date": datetime.now().strftime('%d.%m'), "text": original_text, "sent": False, "waiting": False}
            save_data(data)
            send(message.chat.id, f"✅ Записал! Утром {partner_name} увидит твоё сообщение.")
            return
        send(message.chat.id, "Напиши / чтобы увидеть меню!")
    except Exception as e:
        print(f"Ошибка в handle_message: {e}")
        import traceback
        traceback.print_exc()
        try:
            send(message.chat.id, f"Произошла ошибка: {e}")
        except:
            pass

# === ОБРАБОТКА КНОПОК ===
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        user_id = call.from_user.id
        user_name = USERS.get(user_id)
        if not user_name:
            return
        partner_id = get_partner_id(user_id)
        partner_name = USERS.get(partner_id, "Партнёр")
        if call.data == 'write_mode':
            data['write_queue'][str(user_id)] = 'waiting'
            save_data(data)
            bot.answer_callback_query(call.id, f"Напиши сообщение для {partner_name}")
            send(user_id, f"✍️ Напиши сообщение для {partner_name}. Оно отправится завтра утром в 9:00.")
    except Exception as e:
        print(f"Ошибка в кнопке: {e}")

# === ЕЖЕДНЕВНАЯ РАССЫЛКА ===
def daily_scheduler():
    while True:
        now = datetime.now()
        current_time = now.strftime('%H:%M')
        if current_time == '21:00':
            for user_id, user_name in USERS.items():
                try:
                    send(user_id, f"💙 {user_name}, как прошёл день? Что чувствуешь?\n\nНапиши ответ, и утром партнёр его увидит!")
                    data['emotions'][str(user_id)]['waiting'] = True
                    save_data(data)
                except Exception as e:
                    print(f"Ошибка рассылки 21:00: {e}")
            time.sleep(60)
        elif current_time == '09:00':
            for user_id, user_name in USERS.items():
                partner_id = get_partner_id(user_id)
                partner_name = USERS.get(partner_id)
                emotion = data['emotions'].get(str(user_id), {})
                if emotion.get('text') and not emotion.get('sent'):
                    try:
                        send(partner_id, f"☀️ Доброе утро! {user_name} пишет:\n\n\"{emotion['text']}\"\n\n({emotion['date']})")
                        data['emotions'][str(user_id)]['sent'] = True
                        save_data(data)
                    except Exception as e:
                        print(f"Ошибка доставки эмоций: {e}")
                write_msg = data['write_queue'].get(str(user_id))
                if write_msg and isinstance(write_msg, dict) and not write_msg.get('sent'):
                    try:
                        send(partner_id, f"💌 Сообщение от {user_name}:\n\n\"{write_msg['text']}\"\n\n({write_msg['date']})")
                        data['write_queue'][str(user_id)]['sent'] = True
                        save_data(data)
                    except Exception as e:
                        print(f"Ошибка доставки write: {e}")
            time.sleep(60)
        time.sleep(30)

# === WEBHOOK ===
@app.route('/' + TG_TOKEN, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return '', 200

@app.route('/')
def index():
    return 'Хеопс работает!'

# === ЗАПУСК ===
if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"🚀 Webhook установлен: {WEBHOOK_URL}")
    threading.Thread(target=daily_scheduler, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
