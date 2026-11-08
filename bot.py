import telebot
import requests
import json
import re
import os
from datetime import datetime, timedelta
from flask import Flask, request
import time
import threading

# === НАСТРОЙКИ ===
TG_TOKEN = os.environ.get('TG_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

if not TG_TOKEN or not GROQ_API_KEY:
    raise Exception("Токены не найдены!")

DATA_FILE = 'data.json'
WEBHOOK_URL = f'https://heops-bot.onrender.com/{TG_TOKEN}'

# ID пользователей
ZHENYA_ID = 3687341185
KSYUSHA_ID = 1981878862

USERS = {
    ZHENYA_ID: "Женя",
    KSYUSHA_ID: "Ксюша"
}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Убедимся, что у Ксюши есть долг 150000
        if str(KSYUSHA_ID) in data.get('users', {}):
            if 'my_debt' not in data['users'][str(KSYUSHA_ID)]:
                data['users'][str(KSYUSHA_ID)]['my_debt'] = 150000
                save_data(data)
        
        return data
    
    return {
        "users": {
            str(ZHENYA_ID): {
                "name": "Женя",
                "balance": 0,
                "my_debt": 90000,
                "mom_debt": 250000,
                "income_history": [],
                "expense_history": [],
                "notes": ""
            },
            str(KSYUSHA_ID): {
                "name": "Ксюша",
                "balance": 0,
                "my_debt": 150000,
                "income_history": [],
                "expense_history": [],
                "notes": ""
            }
        },
        "emotions": {
            str(ZHENYA_ID): {"date": "", "text": "", "sent": False},
            str(KSYUSHA_ID): {"date": "", "text": "", "sent": False}
        }
    }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()
bot = telebot.TeleBot(TG_TOKEN)
app = Flask(__name__)

# === ИИ КАТЕГОРИЗАЦИЯ ===
def get_category_from_ai(expense_text):
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama3-70b-8192",
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
            if category in ['Еда', 'Напитки', 'Транспорт', 'Развлечения', 'Здоровье', 'Одежда', 'Бытовое', 'Связь', 'Другое']:
                return category
        return None
    except:
        return None

def get_category_local(expense_text):
    text = expense_text.lower()
    categories = {
        'Еда': [
            # Базовые продукты
            'шаурм', 'пицц', 'бургер', 'суш', 'ролл', 'рамен', 'борщ', 'суп', 'каш', 
            'мяс', 'колбас', 'сыр', 'хлеб', 'молок', 'яйц', 'фрукт', 'овощ', 'снек', 
            'печень', 'шоколад', 'конфет', 'пельмен', 'вареник', 'блин',
            # Фастфуд и рестораны
            'ростикс', 'kfc', 'кфс', 'мак', 'макдональдс', 'вкусно', 'точка', 'вквс',
            'бургер кинг', 'subway', 'сабвей', 'domino', 'домино', 'папа джонс',
            'теремок', 'крошка', 'картошк', 'шашлык', 'шашлычн', 'пельменн',
            'ресторан', 'кафе', 'столов', 'бистро', 'фудкорт', 'фуд-корт',
            'обед', 'ужин', 'завтрак', 'ланч', 'перекус', 'поел', 'поесть',
            'вок', 'wok', 'суши-бар', 'суши бар', 'итальян', 'грузин', 'узбек',
            'хачапур', 'хинкал', 'плов', 'лаванш', 'лаваш', 'фалафель',
            'кебаб', 'шаурмичн', 'чебурек', 'чебуречн', 'пышк', 'пышечн',
            'торт', 'пирожн', 'морожен', 'десерт'
        ],
        'Напитки': [
            'вод', 'чай', 'кофе', 'сок', 'газировк', 'энергетик', 'ред булл', 
            'monster', 'burn', 'алкоголь', 'пиво', 'вин', 'водк',
            'starbucks', 'кофе хаус', 'шоколадниц', 'кофейн', 'кофейня',
            'лимонад', 'квас', 'морс', 'компот', 'смузи', 'латте', 'капучин',
            'американо', 'эспрессо', 'матча'
        ],
        'Транспорт': [
            'такси', 'автобус', 'метро', 'трамвай', 'бензин', 'топлив', 
            'парковк', 'самокат', 'каршеринг', 'яндекс такси', 'ситимобил',
            'uber', 'убер', 'поезд', 'электричк', 'авиабилет', 'самолет',
            'билет', 'проезд', 'троллейбус', 'маршрутк'
        ],
        'Развлечения': [
            'кино', 'игр', 'cs', 'steam', 'playstation', 'xbox', 'подписк', 
            'нетфликс', 'spotify', 'концерт', 'театр', 'выставк', 'музей',
            'бар', 'клуб', 'караок', 'боулинг', 'бильярд', 'квест', 'парк',
            'аттракцион', 'цирк', 'зоопарк', 'аквариум', 'дельфинарий'
        ],
        'Здоровье': [
            'аптек', 'лекарств', 'врач', 'больниц', 'спортзал', 'тренировк',
            'фитнес', 'йога', 'бассейн', 'массаж', 'стоматолог', 'зуб',
            'анализ', 'обследован', 'прививк', 'вакцин', 'витамины', 'бад'
        ],
        'Одежда': [
            'одежд', 'обувь', 'куртк', 'джинс', 'футболк', 'кроссовк', 'ботинк',
            'сумк', 'рюкзак', 'аксессуар', 'часы', 'украшен', 'кольц', 'серьг'
        ],
        'Бытовое': [
            'бытов', 'уборк', 'стирк', 'шампун', 'мыл', 'туалет', 'зубн',
            'порошок', 'средство', 'губк', 'тряпк', 'полотенц', 'постельн',
            'ремонт', 'инструмент', 'лампочк', 'батарейк'
        ],
        'Связь': [
            'интернет', 'телефон', 'мобильн', 'сим', 'роуминг', 'мтс', 'билайн',
            'мегафон', 'теле2', 'йота', 'оплат', 'пополн', 'минут', 'гб', 'трафик'
        ],
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

# === ФОРМАТ НЕДЕЛИ ===
def get_week_stats(user_data, user_name):
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    
    stats = f"💰 **Баланс:** {user_data['balance']}р\n"
    if user_data.get('my_debt'):
        stats += f"📉 **Долг:** {user_data['my_debt']}р\n"
    if user_data.get('mom_debt'):
        stats += f"📉 **Мамин долг:** {user_data['mom_debt']}р\n"
    stats += "\n"
    
    # Расходы по дням
    daily_expenses = {}
    for expense in user_data.get('expense_history', []):
        date_str = expense.split(':')[0]
        try:
            exp_date = datetime.strptime(date_str, '%d.%m')
            if exp_date >= week_ago:
                if date_str not in daily_expenses:
                    daily_expenses[date_str] = []
                daily_expenses[date_str].append(expense.split(': ', 1)[1])
        except:
            pass
    
    if daily_expenses:
        stats += "📉 **Расходы за неделю:**\n"
        for date in sorted(daily_expenses.keys(), reverse=True):
            stats += f"\n📅 {date}:\n"
            for exp in daily_expenses[date]:
                stats += f"  • {exp}\n"
    else:
        stats += "📉 Расходов за неделю нет.\n"
    
    # Доходы по дням
    daily_incomes = {}
    for income in user_data.get('income_history', []):
        date_str = income.split(':')[0]
        try:
            inc_date = datetime.strptime(date_str, '%d.%m')
            if inc_date >= week_ago:
                if date_str not in daily_incomes:
                    daily_incomes[date_str] = []
                daily_incomes[date_str].append(income.split(': ', 1)[1])
        except:
            pass
    
    if daily_incomes:
        stats += "\n💰 **Доходы за неделю:**\n"
        for date in sorted(daily_incomes.keys(), reverse=True):
            stats += f"\n📅 {date}:\n"
            for inc in daily_incomes[date]:
                stats += f"  • {inc}\n"
    else:
        stats += "\n💰 Доходов за неделю нет.\n"
    
    return stats

# === ОБРАБОТКА СООБЩЕНИЙ ===
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_name = USERS.get(user_id)
    
    if not user_name:
        bot.reply_to(message, "Привет! Этот бот только для Жени и Ксюши. 😊")
        return
    
    partner_id = get_partner_id(user_id)
    partner_name = USERS.get(partner_id, "Партнёр")
    
    text = message.text.lower().strip() if message.text else ''
    original_text = message.text.strip() if message.text else ''
    
    is_command = text.startswith('/')
    command = text[1:] if is_command else text
    
    if is_command and not command:
        command = 'помощь'
    
    # 1. Помощь
    if command in ['помощь', 'help', 'команды', '']:
        help_text = f"""📋 **Хеопс — для {user_name}:**

💰 **Твой бюджет:**
• `300 шаурма` или `шаурма 300` — расход
• `зп самокат 3000` — доход
• `погасил долг 1000` — погашение

📊 **Просмотр (7 дней):**
• `/я` — твой бюджет
• `/она` — бюджет {partner_name} (только просмотр)

💙 **Эмоции:**
• `/день` — сообщение {partner_name} за вчера
• `/написать я скучаю` — отправить сейчас
• `/статус` — ответил ли {partner_name} сегодня

📌 **Заметки:**
• `/заметка ксюша любит рамен` — о {partner_name}
• `/заметка я устал` — о себе"""
        bot.reply_to(message, help_text)
        return

    # 2. Личные расходы (только для себя)
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

    # 3. Доходы
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

    # 4. Погашение долга (только своего)
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

    # 5. Просмотр своего бюджета
    if command in ['я', 'мне', 'moi']:
        user_data = data['users'][str(user_id)]
        stats = f"👤 **{user_name} — последние 7 дней:**\n\n"
        stats += get_week_stats(user_data, user_name)
        bot.reply_to(message, stats)
        return

    # 6. Просмотр бюджета партнёра (ТОЛЬКО ПРОСМОТР)
    if command in ['она', 'он', 'partner']:
        partner_data = data['users'][str(partner_id)]
        stats = f"💙 **{partner_name} — последние 7 дней:**\n\n"
        stats += get_week_stats(partner_data, partner_name)
        bot.reply_to(message, stats)
        return

    # 7. Эмоциональный обмен
    if command == 'день':
        partner_emotion = data['emotions'].get(str(partner_id), {})
        if not partner_emotion.get('text'):
            bot.reply_to(message, f"{partner_name} ещё не поделился эмоциями. Напомни написать `/день`! 💙")
            return
        emotion_date = partner_emotion.get('date', 'Неизвестно')
        emotion_text = partner_emotion['text']
        bot.reply_to(message, f"💙 **{partner_name} ({emotion_date}):**\n\n{emotion_text}")
        return

    if command.startswith('написать') or command.startswith('write'):
        message_text = re.sub(r'^(написать|write)\s*[:\-]?\s*', '', original_text, flags=re.IGNORECASE)
        if not message_text or message_text == original_text:
            bot.reply_to(message, f"Напиши: `/написать [текст для {partner_name}]`")
            return
        try:
            bot.send_message(partner_id, f"💌 **Сообщение от {user_name}:**\n\n{message_text}")
            bot.reply_to(message, f"✅ Отправлено {partner_name}!")
        except:
            bot.reply_to(message, f"❌ Не удалось отправить. {partner_name} должен сначала написать боту /старт")
        return

    if command == 'статус':
        partner_emotion = data['emotions'].get(str(partner_id), {})
        today = datetime.now().strftime('%d.%m')
        if partner_emotion.get('date') == today:
            bot.reply_to(message, f"✅ {partner_name} уже поделился эмоциями сегодня!")
        else:
            bot.reply_to(message, f"⏳ {partner_name} ещё не ответил сегодня.")
        return

    # 8. Заметки
    if command.startswith('заметк') or command.startswith('note'):
        note_text = re.sub(r'^(заметк[ау]?|note)\s*[:\-]?\s*', '', original_text, flags=re.IGNORECASE)
        
        if 'ксюш' in note_text.lower() or note_text.lower().startswith('к '):
            clean_note = re.sub(r'^(ксюш[ау]?|к)\s*[:\-]?\s*', '', note_text, flags=re.IGNORECASE)
            if not clean_note or clean_note == note_text:
                clean_note = note_text
            data['users'][str(KSYUSHA_ID)]['notes'] += f"{datetime.now().strftime('%d.%m')}: {clean_note}\n"
            save_data(data)
            bot.reply_to(message, f"📌 Запомнил про Ксюшу: {clean_note}. 💙")
            return
        elif 'жен' in note_text.lower() or note_text.lower().startswith('ж ') or note_text.lower().startswith('я '):
            clean_note = re.sub(r'^(жен[яю]?|ж|я)\s*[:\-]?\s*', '', note_text, flags=re.IGNORECASE)
            if not clean_note or clean_note == note_text:
                clean_note = note_text
            data['users'][str(ZHENYA_ID)]['notes'] += f"{datetime.now().strftime('%d.%m')}: {clean_note}\n"
            save_data(data)
            bot.reply_to(message, f"📌 Запомнил про Женю: {clean_note}. 💪")
            return
        else:
            data['users'][str(user_id)]['notes'] += f"{datetime.now().strftime('%d.%m')}: {note_text}\n"
            save_data(data)
            bot.reply_to(message, f"📌 Запомнил: {note_text}.")
            return

    # 9. Показать заметки
    if command in ['ксюша', 'ksyusha']:
        notes = data['users'][str(KSYUSHA_ID)].get('notes', '')
        if not notes or notes.strip() == '':
            bot.reply_to(message, "📝 Пока нет заметок о Ксюше.")
            return
        report = "💙 **Всё о Ксюше:**\n\n" + notes + "\n⚠️ ДР Ксюши — 1 февраля!"
        bot.reply_to(message, report)
        return

    if command in ['женя', 'zhenya']:
        notes = data['users'][str(ZHENYA_ID)].get('notes', '')
        if not notes or notes.strip() == '':
            bot.reply_to(message, "📝 Пока нет заметок о Жене.")
            return
        report = "💪 **Всё о Жене:**\n\n" + notes
        bot.reply_to(message, report)
        return

    # 10. Старт
    if command == 'start' or command == 'старт':
        bot.reply_to(message, f"Привет, {user_name}! 👋\n\nНапиши `/помощь` чтобы увидеть все команды!")
        return

    # 11. Ответ на ежедневный вопрос (сохраняем эмоцию)
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

    # 12. Остальное
    bot.reply_to(message, f"Я помогаю {user_name} и {partner_name}. 😊\n\nНапиши `/` чтобы увидеть меню!")

# === ЕЖЕДНЕВНАЯ РАССЫЛКА ===
def daily_scheduler():
    while True:
        now = datetime.now()
        current_time = now.strftime('%H:%M')
        
        # В 21:00 — задаём вопрос
        if current_time == '21:00':
            for user_id, user_name in USERS.items():
                try:
                    bot.send_message(user_id, f"💙 {user_name}, как прошёл день? Что чувствуешь?\n\nНапиши ответ, и утром партнёр его увидит!")
                    data['emotions'][str(user_id)]['waiting'] = True
                    save_data(data)
                except:
                    pass
            time.sleep(60)
        
        # В 09:00 — доставляем сообщения
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
    return 'Хеопс работает! 🤖'

# === ЗАПУСК ===
if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    
    # Запускаем планировщик
    threading.Thread(target=daily_scheduler, daemon=True).start()
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
