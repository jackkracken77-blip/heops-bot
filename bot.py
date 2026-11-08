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

USERS = {
    ZHENYA_ID: "Женя",
    KSYUSHA_ID: "Ксюша"
}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if str(KSYUSHA_ID) in data.get('users', {}):
            if 'my_debt' not in data['users'][str(KSYUSHA_ID)]:
                data['users'][str(KSYUSHA_ID)]['my_debt'] = 150000
        if 'write_queue' not in data:
            data['write_queue'] = {str(ZHENYA_ID): None, str(KSYUSHA_ID): None}
        save_data(data)
        return data
    return {
        "users": {
            str(ZHENYA_ID): {
                "name": "Женя", "balance": 0, "my_debt": 90000, "mom_debt": 250000,
                "income_history": [], "expense_history": [], "notes": ""
            },
            str(KSYUSHA_ID): {
                "name": "Ксюша", "balance": 0, "my_debt": 150000,
                "income_history": [], "expense_history": [], "notes": ""
            }
        },
        "emotions": {
            str(ZHENYA_ID): {"date": "", "text": "", "sent": False, "waiting": False},
            str(KSYUSHA_ID): {"date": "", "text": "", "sent": False, "waiting": False}
        },
        "write_queue": {str(ZHENYA_ID): None, str(KSYUSHA_ID): None}
    }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()
bot = telebot.TeleBot(TG_TOKEN)
app = Flask(__name__)

def get_category_from_ai(expense_text):
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama3-70b-8192",
            "messages": [
                {"role": "system", "content": "Определи категорию. Ответь ТОЛЬКО одной: Еда, Напитки, Транспорт, Развлечения, Здоровье, Одежда, Бытовое, Связь, Другое."},
                {"role": "user", "content": f"Расход: {expense_text}. Категория:"}
            ],
            "temperature": 0.1,
            "max_tokens": 10
        }
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            category = result['choices'][0]['message']['content'].strip()
            if category in ['Еда', 'Напитки', 'Транспорт', 'Развлечения', 'Здоровье', 'Одежда', 'Бытовое', 'Связь', 'Другое']:
                return category
        return None
    except:
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

def get_partner_id(user_id):
    if user_id == ZHENYA_ID:
        return KSYUSHA_ID
    return ZHENYA_ID

def get_partner_command(user_id):
    if user_id == ZHENYA_ID:
        return "/она"
    return "/он"

def get_week_stats(user_data, user_name):
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    stats = f"👤 **{user_name} — последние 7 дней:**\n\n"
    stats += f"💰 **Баланс:** {user_data['balance']}р\n"
    if user_data.get('my_debt'):
        stats += f"📉 **Долг:** {user_data['my_debt']}р\n"
    if user_data.get('mom_debt'):
        stats += f"📉 **Мамин долг:** {user_data['mom_debt']}р\n"
    stats += "\n"
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
        stats += f"📉 **Расходы за неделю:** {total_week_expenses}р\n"
        for date in sorted(daily_expenses.keys(), reverse=True):
            stats += f"\n📅 {date}:\n"
            for exp in daily_expenses[date]:
                stats += f"  • {exp}\n"
    else:
        stats += "📉 Расходов за неделю нет.\n"
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
        stats += f"\n💰 **Доходы за неделю:** {total_week_income}р\n"
        for date in sorted(daily_incomes.keys(), reverse=True):
            stats += f"\n📅 {date}:\n"
            for inc in daily_incomes[date]:
                stats += f"  • {inc}\n"
    else:
        stats += "\n💰 Доходов за неделю нет.\n"
    return stats

def get_month_stats(user_data, user_name):
    today = datetime.now()
    current_month = today.month
    current_year = today.year
    month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    stats = f"👤 **{user_name} — {month_names[current_month-1]} {current_year}**\n\n"
    stats += f"💰 **Баланс:** {user_data['balance']}р\n"
    if user_data.get('my_debt'):
        stats += f"📉 **Долг:** {user_data['my_debt']}р\n"
    if user_data.get('mom_debt'):
        stats += f"📉 **Мамин долг:** {user_data['mom_debt']}р\n"
    stats += "\n"
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
        stats += f"📉 **Расходы за месяц:** {total_month_expenses}р\n"
        for date in sorted(daily_expenses.keys(), reverse=True):
            stats += f"\n📅 {date}:\n"
            for exp in daily_expenses[date]:
                stats += f"  • {exp}\n"
    else:
        stats += "📉 Расходов за месяц нет.\n"
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
        stats += f"\n💰 **Доходы за месяц:** {total_month_income}р\n"
        for date in sorted(daily_incomes.keys(), reverse=True):
            stats += f"\n📅 {date}:\n"
            for inc in daily_incomes[date]:
                stats += f"  • {inc}\n"
    else:
        stats += "\n💰 Доходов за месяц нет.\n"
    if category_totals:
        stats += f"\n📊 **По категориям:**\n"
        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        for cat, amount in sorted_cats:
            percentage = (amount / total_month_expenses) * 100 if total_month_expenses > 0 else 0
            bar_length = int(percentage / 5)
            bar = '█' * bar_length + '░' * (20 - bar_length)
            stats += f"**{cat}:** {amount}р ({percentage:.1f}%)\n{bar}\n\n"
    return stats

def get_year_stats(user_data, user_name):
    today = datetime.now()
    current_year = today.year
    stats = f"👤 **{user_name} — {current_year} год**\n\n"
    stats += f"💰 **Баланс:** {user_data['balance']}р\n"
    if user_data.get('my_debt'):
        stats += f"📉 **Долг:** {user_data['my_debt']}р\n"
    if user_data.get('mom_debt'):
        stats += f"📉 **Мамин долг:** {user_data['mom_debt']}р\n"
    stats += "\n"
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
    stats += f"📉 **Расходы за год:** {total_year_expenses}р\n"
    stats += f"💰 **Доходы за год:** {total_year_income}р\n"
    stats += f"💵 **Разница:** {total_year_income - total_year_expenses}р\n\n"
    stats += "**По месяцам:**\n"
    for month_num in range(1, 13):
        exp = monthly_expenses.get(month_num, 0)
        inc = monthly_incomes.get(month_num, 0)
        if exp > 0 or inc > 0:
            stats += f"\n📅 **{month_names[month_num-1]}:**\n"
            if exp > 0:
                stats += f"  📉 Расходы: {exp}р\n"
            if inc > 0:
                stats += f"  💰 Доходы: {inc}р\n"
    return stats

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_name = USERS.get(user_id)
    if not user_name:
        bot.reply_to(message, "Привет! Этот бот только для Жени и Ксюши. 😊")
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
        data['write_queue'][str(user_id)] = {
            "text": original_text,
            "date": datetime.now().strftime('%d.%m %H:%M'),
            "sent": False
        }
        save_data(data)
        bot.reply_to(message, f"✅ Записал! Сообщение отправится {partner_name} завтра утром в 9:00.\n\n💌 Твой текст: \"{original_text}\"")
        return
    if command in ['помощь', 'help', 'команды', '']:
        help_text = f"""📋 **Хеопс — для {user_name}:**

💰 **Твой бюджет:**
• `300 шаурма` или `шаурма 300` — расход
• `зп самокат 3000` — доход
• `погасил долг 1000` — погашение

📊 **Статистика:**
• `/now` или `/сейчас` — баланс и операции прямо сейчас
• `/ya`, `/я` или `баланс` — за 7 дней
• `/month` или `/месяц` — календарный месяц
• `/year` или `/год` — календарный год
• `{partner_command}` или `/ona` — бюджет {partner_name}
• `/categories` — по категориям

💙 **Эмоции и связь:**
• `/day` или `/день` — сообщение {partner_name} за вчера
• `/write` — написать {partner_name} (придёт утром в 9:00)
• `/status` или `/статус` — статус

📌 **Заметки:**
• `/note текст` — заметка о {partner_name} (автоматически)

⚙️ **Для разработчика:**
• `/reset` — полный сброс истории"""
        markup = types.InlineKeyboardMarkup()
        btn_write = types.InlineKeyboardButton(f"✉️ Написать {partner_name}", callback_data='write_mode')
        markup.add(btn_write)
        bot.reply_to(message, help_text, reply_markup=markup)
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
        bot.reply_to(message, f"📉 Записал: {amount}р на {category_text}\n📂 Категория: {category}\n💰 Остаток: {user_data['balance']}р")
        return
    income_match = re.search(r'(зп|яндекс|самокат|подработка)\s*.*?(\d+)', text)
    if income_match:
        source = income_match.group(1).capitalize()
        amount = int(income_match.group(2))
        user_data = data['users'][str(user_id)]
        user_data['balance'] += amount
        user_data['income_history'].append(f"{datetime.now().strftime('%d.%m')}: {amount}р - {source}")
        save_data(data)
        bot.reply_to(message, f"💰 Получил {amount}р от {source}. Баланс: {user_data['balance']}р. 🎯")
        return
    if 'погас' in text:
        debt_match = re.search(r'(\d+)', text)
        if debt_match:
            amount = int(debt_match.group(1))
            user_data = data['users'][str(user_id)]
            if 'мамин' in text or 'мам' in text:
                user_data['mom_debt'] = user_data.get('mom_debt', 0) - amount
                save_data(data)
                bot.reply_to(message, f"🙌 Мамин долг теперь {user_data['mom_debt']}р. 💙")
            else:
                user_data['my_debt'] = user_data.get('my_debt', 0) - amount
                save_data(data)
                bot.reply_to(message, f"🔥 Твой долг теперь {user_data['my_debt']}р. 🚀")
            return
    if command in ['сейчас', 'now', 'прямо сейчас']:
        user_data = data['users'][str(user_id)]
        stats = f"⚡ **{user_name} — прямо сейчас:**\n\n"
        stats += f"💰 **Баланс:** {user_data['balance']}р\n"
        if user_data.get('my_debt'):
            stats += f"📉 **Твой долг:** {user_data['my_debt']}р\n"
        if user_data.get('mom_debt'):
            stats += f"📉 **Мамин долг:** {user_data['mom_debt']}р\n"
        if user_data.get('my_debt') or user_data.get('mom_debt'):
            total_debt = user_data.get('my_debt', 0) + user_data.get('mom_debt', 0)
            stats += f"📊 **Всего долгов:** {total_debt}р\n"
        stats += "\n"
        all_transactions = []
        for expense in user_data.get('expense_history', []):
            date_str = expense.split(':')[0]
            all_transactions.append({'date': date_str, 'text': expense.split(': ', 1)[1], 'type': 'expense'})
        for income in user_data.get('income_history', []):
            date_str = income.split(':')[0]
            all_transactions.append({'date': date_str, 'text': income.split(': ', 1)[1], 'type': 'income'})
        all_transactions.sort(key=lambda x: x['date'], reverse=True)
        if all_transactions:
            stats += "📋 **Последние 10 операций:**\n"
            for i, trans in enumerate(all_transactions[:10]):
                icon = '📉' if trans['type'] == 'expense' else '💰'
                stats += f"{icon} {trans['date']}: {trans['text']}\n"
        else:
            stats += "📋 Операций пока нет.\n"
        bot.reply_to(message, stats)
        return
    if command in ['я', 'мне', 'moi', 'ya', 'balance', 'баланс', 'статистика', 'неделя', 'week']:
        user_data = data['users'][str(user_id)]
        bot.reply_to(message, get_week_stats(user_data, user_name))
        return
    if command in ['месяц', 'month']:
        user_data = data['users'][str(user_id)]
        bot.reply_to(message, get_month_stats(user_data, user_name))
        return
    if command in ['год', 'year']:
        user_data = data['users'][str(user_id)]
        bot.reply_to(message, get_year_stats(user_data, user_name))
        return
    if command in ['она', 'он', 'partner', 'ona']:
        partner_data = data['users'][str(partner_id)]
        bot.reply_to(message, get_week_stats(partner_data, partner_name))
        return
    if command in ['категории', 'анализ', 'categories']:
        user_data = data['users'][str(user_id)]
        if not user_data.get('expense_history'):
            bot.reply_to(message, "Пока нет расходов. 📝")
            return
        category_totals = {}
        total_expenses = 0
        for expense in user_data['expense_history']:
            match = re.search(r': (\d+)р - .+ \[(.+)\]', expense)
            if match:
                amount = int(match.group(1))
                category = match.group(2)
                category_totals[category] = category_totals.get(category, 0) + amount
                total_expenses += amount
        report = f"📊 **Анализ расходов {user_name}:**\n\n"
        report += f"💸 **Всего:** {total_expenses}р\n\n"
        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        for category, amount in sorted_categories:
            percentage = (amount / total_expenses) * 100
            bar_length = int(percentage / 5)
            bar = '█' * bar_length + '░' * (20 - bar_length)
            report += f"**{category}:** {amount}р ({percentage:.1f}%)\n{bar}\n\n"
        bot.reply_to(message, report)
        return
    if command in ['день', 'day']:
        partner_emotion = data['emotions'].get(str(partner_id), {})
        if not partner_emotion.get('text'):
            bot.reply_to(message, f"{partner_name} ещё не поделился эмоциями. 💙")
            return
        bot.reply_to(message, f"💙 **{partner_name} ({partner_emotion.get('date')}):**\n\n{partner_emotion['text']}")
        return
    if command in ['write', 'написать']:
        data['write_queue'][str(user_id)] = 'waiting'
        save_data(data)
        bot.reply_to(message, f"✍️ Напиши сообщение для {partner_name}. Оно отправится завтра утром в 9:00.")
        return
    if command in ['статус', 'status']:
        partner_emotion = data['emotions'].get(str(partner_id), {})
        today = datetime.now().strftime('%d.%m')
        if partner_emotion.get('date') == today:
            bot.reply_to(message, f"✅ {partner_name} уже поделился эмоциями сегодня!")
        else:
            bot.reply_to(message, f"⏳ {partner_name} ещё не ответил сегодня.")
        return
    if command.startswith('заметк') or command.startswith('note'):
        note_text = re.sub(r'^(заметк[ау]?|note)\s*[:\-]?\s*', '', original_text, flags=re.IGNORECASE)
        if not note_text or note_text == original_text:
            bot.reply_to(message, f"Напиши: `/note [текст о {partner_name}]`")
            return
        data['users'][str(partner_id)]['notes'] += f"{datetime.now().strftime('%d.%m')}: {note_text}\n"
        save_data(data)
        confirm_text = f"""✅ **Заметка сохранена!**

📝 **Текст:** {note_text}
📂 **Сохранено в профиль:** {partner_name}
📅 **Дата:** {datetime.now().strftime('%d.%m.%Y %H:%M')}

{partner_name} увидит это, когда напишет /ksyusha или /zhenya 💙"""
        bot.reply_to(message, confirm_text)
        return
    if command in ['ксюша', 'ksyusha']:
        notes = data['users'][str(KSYUSHA_ID)].get('notes', '')
        if not notes or notes.strip() == '':
            bot.reply_to(message, "📝 Пока нет заметок о Ксюше.")
            return
        bot.reply_to(message, "💙 **Всё о Ксюше:**\n\n" + notes + "\n⚠️ ДР Ксюши — 1 февраля!")
        return
    if command in ['женя', 'zhenya']:
        notes = data['users'][str(ZHENYA_ID)].get('notes', '')
        if not notes or notes.strip() == '':
            bot.reply_to(message, "📝 Пока нет заметок о Жене.")
            return
        bot.reply_to(message, "💪 **Всё о Жене:**\n\n" + notes)
        return
    if command in ['start', 'старт']:
        bot.reply_to(message, f"Привет, {user_name}! 👋\n\nНапиши `/help` чтобы увидеть все команды!")
        return
    if command == 'reset':
        if user_id != ZHENYA_ID:
            bot.reply_to(message, "🚫 Эта команда доступна только разработчику.")
            return
        data = {
            "users": {
                str(ZHENYA_ID): {
                    "name": "Женя", "balance": 0, "my_debt": 90000, "mom_debt": 250000,
                    "income_history": [], "expense_history": [], "notes": ""
                },
                str(KSYUSHA_ID): {
                    "name": "Ксюша", "balance": 0, "my_debt": 150000,
                    "income_history": [], "expense_history": [], "notes": ""
                }
            },
            "emotions": {
                str(ZHENYA_ID): {"date": "", "text": "", "sent": False, "waiting": False},
                str(KSYUSHA_ID): {"date": "", "text": "", "sent": False, "waiting": False}
            },
            "write_queue": {str(ZHENYA_ID): None, str(KSYUSHA_ID): None}
        }
        save_data(data)
        bot.reply_to(message, """🗑 **ИСТОРИЯ ПОЛНОСТЬЮ ОЧИЩЕНА!**

✅ Балансы обнулены (0р)
✅ Долги восстановлены до начальных (Женя: 90к + 250к, Ксюша: 150к)
✅ Все траты, доходы, заметки и сообщения удалены

Можно начинать с чистого листа! 🚀""")
        return
    if data['emotions'].get(str(user_id), {}).get('waiting', False):
        data['emotions'][str(user_id)] = {
            "date": datetime.now().strftime('%d.%m'),
            "text": original_text,
            "sent": False,
            "waiting": False
        }
        save_data(data)
        bot.reply_to(message, f"✅ Записал! Утром {partner_name} увидит твоё сообщение. 💙")
        return
    bot.reply_to(message, f"Напиши `/` чтобы увидеть меню!")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
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
        bot.send_message(user_id, f"✍️ Напиши сообщение для {partner_name}. Оно отправится завтра утром в 9:00.")

def daily_scheduler():
    while True:
        now = datetime.now()
        current_time = now.strftime('%H:%M')
        if current_time == '21:00':
            for user_id, user_name in USERS.items():
                try:
                    bot.send_message(user_id, f"💙 {user_name}, как прошёл день? Что чувствуешь?\n\nНапиши ответ, и утром партнёр его увидит!")
                    data['emotions'][str(user_id)]['waiting'] = True
                    save_data(data)
                except:
                    pass
            time.sleep(60)
        elif current_time == '09:00':
            for user_id, user_name in USERS.items():
                partner_id = get_partner_id(user_id)
                partner_name = USERS.get(partner_id)
                emotion = data['emotions'].get(str(user_id), {})
                if emotion.get('text') and not emotion.get('sent'):
                    try:
                        bot.send_message(partner_id, f"☀️ Доброе утро! {user_name} пишет:\n\n\"{emotion['text']}\"\n\n({emotion['date']})")
                        data['emotions'][str(user_id)]['sent'] = True
                        save_data(data)
                    except:
                        pass
                write_msg = data['write_queue'].get(str(user_id))
                if write_msg and isinstance(write_msg, dict) and not write_msg.get('sent'):
                    try:
                        bot.send_message(partner_id, f"💌 **Сообщение от {user_name}:**\n\n\"{write_msg['text']}\"\n\n({write_msg['date']})")
                        data['write_queue'][str(user_id)]['sent'] = True
                        save_data(data)
                    except:
                        pass
            time.sleep(60)
        time.sleep(30)

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
    print(f"🚀 Webhook установлен: {WEBHOOK_URL}")
    threading.Thread(target=daily_scheduler, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
