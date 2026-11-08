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
    
    # 1. Помощь
    if command in ['помощь', 'help', 'команды', '']:
        help_text = f"""📋 **Хеопс — для {user_name}:**

💰 **Твой бюджет:**
• `300 шаурма` или `шаурма 300` — расход
• `зп самокат 3000` — доход
• `погасил долг 1000` — погашение

📊 **Просмотр (7 дней):**
• `/ya` или `/я` — твой бюджет
• `{partner_command}` или `/ona` — бюджет {partner_name} (только просмотр)

💙 **Эмоции:**
• `/day` или `/день` — сообщение {partner_name} за вчера
• `/write я скучаю` или `/написать я скучаю` — отправить сейчас
• `/status` или `/статус` — ответил ли {partner_name} сегодня

📌 **Заметки:**
• `/note ксюша любит рамен` — о {partner_name}
• `/note я устал` — о себе"""
        bot.reply_to(message, help_text)
        return

    # 2. Личные расходы
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

    # 4. Погашение долга
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

    # 5. Просмотр своего бюджета (/ya или /я)
    if command in ['я', 'мне', 'moi', 'ya', 'balance', 'баланс', 'статистика']:
        user_data = data['users'][str(user_id)]
        stats = f"👤 **{user_name} — последние 7 дней:**\n\n"
        stats += get_week_stats(user_data, user_name)
        bot.reply_to(message, stats)
        return

    # 6. Просмотр бюджета партнёра (/ona или /она)
    if command in ['она', 'он', 'partner', 'ona']:
        partner_data = data['users'][str(partner_id)]
        stats = f"💙 **{partner_name} — последние 7 дней:**\n\n"
        stats += get_week_stats(partner_data, partner_name)
        bot.reply_to(message, stats)
        return

    # 7. Анализ по категориям
    if command in ['категории', 'анализ', 'categories']:
        user_data = data['users'][str(user_id)]
        if not user_data.get('expense_history'):
            bot.reply_to(message, "Пока нет расходов для анализа. 📝")
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

    # 8. Эмоциональный обмен
    if command in ['день', 'day']:
        partner_emotion = data['emotions'].get(str(partner_id), {})
        if not partner_emotion.get('text'):
            bot.reply_to(message, f"{partner_name} ещё не поделился эмоциями. Напомни написать `/day`! 💙")
            return
        emotion_date = partner_emotion.get('date', 'Неизвестно')
        emotion_text = partner_emotion['text']
        bot.reply_to(message, f"💙 **{partner_name} ({emotion_date}):**\n\n{emotion_text}")
        return

    if command.startswith('написать') or command.startswith('write'):
        message_text = re.sub(r'^(написать|write)\s*[:\-]?\s*', '', original_text, flags=re.IGNORECASE)
        if not message_text or message_text == original_text:
            bot.reply_to(message, f"Напиши: `/write [текст для {partner_name}]`")
            return
        try:
            bot.send_message(partner_id, f"💌 **Сообщение от {user_name}:**\n\n{message_text}")
            bot.reply_to(message, f"✅ Отправлено {partner_name}!")
        except:
            bot.reply_to(message, f"❌ Не удалось отправить. {partner_name} должен сначала написать боту /start")
        return

    if command in ['статус', 'status']:
        partner_emotion = data['emotions'].get(str(partner_id), {})
        today = datetime.now().strftime('%d.%m')
        if partner_emotion.get('date') == today:
            bot.reply_to(message, f"✅ {partner_name} уже поделился эмоциями сегодня!")
        else:
            bot.reply_to(message, f"⏳ {partner_name} ещё не ответил сегодня.")
        return

    # 9. Заметки
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

    # 10. Показать заметки
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

    # 11. Старт
    if command in ['start', 'старт']:
        bot.reply_to(message, f"Привет, {user_name}! 👋\n\nНапиши `/help` чтобы увидеть все команды!")
        return

    # 12. Ответ на ежедневный вопрос
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

    # 13. Остальное
    bot.reply_to(message, f"Я помогаю {user_name} и {partner_name}. 😊\n\nНапиши `/` чтобы увидеть меню!")
