# ==========================================
# Voltage Alert Notification Templates
# ==========================================

VOLTAGE_CRITICAL_LOW = (
    "🚨 <b>КРИТИЧНО НИЗЬКА НАПРУГА</b>\n\n"
    "📉 Поточна: <code>{v:.1f} V</code>\n\n"
    "⛔️ <b>Терміново знеструмте техніку!</b>\n"
    "<i>Компресори холодильників та насоси можуть перегрітися і згоріти.</i>"
)

VOLTAGE_LOW = (
    "⚠️ <b>НИЗЬКА НАПРУГА</b>\n\n"
    "📉 Поточна: <code>{v:.1f} V</code>\n\n"
    "🔌 <i>Радимо вимкнути чутливі прилади та утриматися від користування ліфтом.</i>"
)

VOLTAGE_HIGH = (
    "⚠️ <b>ВИСОКА НАПРУГА</b>\n\n"
    "📈 Поточна: <code>{v:.1f} V</code>\n\n"
    "🔌 <i>Вимкніть енергоємні прилади. <b>Уникайте користування ліфтом — це небезпечно!</b></i>"
)

VOLTAGE_CRITICAL_HIGH = (
    "🚨 <b>КРИТИЧНО ВИСОКА НАПРУГА</b>\n\n"
    "📈 Поточна: <code>{v:.1f} V</code>\n\n"
    "⛔️ <b>Загроза виходу техніки з ладу або пожежі!</b>"
)

VOLTAGE_RESTORED = (
    "✅ <b>НАПРУГА СТАБІЛІЗУВАЛАСЬ</b>\n\n"
    "📊 Поточна: <code>{v:.1f} V</code>\n\n"
    "🔌 <i>Мережа в нормі, можна поступово вмикати техніку.</i>"
)


# ==========================================
# Frequency Alert Notification Templates
# ==========================================

FREQUENCY_CRITICAL_LOW = (
    "🚨 <b>КРИТИЧНЕ ПАДІННЯ ЧАСТОТИ</b>\n\n"
    "📉 Поточна: <code>{hz:.2f} Hz</code> (Норма: 50.00 Hz)\n\n"
    "⛔️ <b>Гострий дефіцит генерації в енергосистемі!</b>\n"
    "<i>Можливе миттєве спрацювання автоматичного захисту (САВН). "
    "Не користуйтеся ліфтами — високий ризик раптового знеструмлення.</i>"
)

FREQUENCY_LOW = (
    "⚠️ <b>ПРОСАДКА ЧАСТОТИ МЕРЕЖІ</b>\n\n"
    "📉 Поточна: <code>{hz:.2f} Hz</code> (Норма: 50.00 Hz)\n\n"
    "⚡️ <i>В енергосистемі фіксується дефіцит потужності. "
    "Ймовірне застосування аварійних графіків відключень.</i>"
)

FREQUENCY_HIGH = (
    "⚠️ <b>ПІДВИЩЕНА ЧАСТОТА МЕРЕЖІ</b>\n\n"
    "📈 Поточна: <code>{hz:.2f} Hz</code> (Норма: 50.00 Hz)\n\n"
    "⚡️ <i>Фіксується надлишок генерації в енергосистемі. Диспетчери балансують мережу.</i>"
)

FREQUENCY_RESTORED = (
    "✅ <b>ЧАСТОТА МЕРЕЖІ СТАБІЛІЗУВАЛАСЬ</b>\n\n"
    "📊 Поточна: <code>{hz:.2f} Hz</code>\n\n"
    "🔌 <i>Енергосистема синхронізована та збалансована (50.00 Hz).</i>"
)


# ==========================================
# Schedule Post & Timeline Templates
# ==========================================

TIMELINE_NOT_PUBLISHED = "❓ <i>Графік ще не опубліковано</i>"
TIMELINE_LIGHT_ALL_DAY = "💡 <i>Світло є (за графіком)</i>"

SCHEDULE_UPDATE_CAPTION = (
    "<b>ГРАФІК ВІДКЛЮЧЕНЬ | {group_name}</b>\n"
    "<i>Оновлено: {upd_str} • Мережа: {net_status}</i>\n\n"
    "<b>Сьогодні ({today_date}):</b>\n"
    "{today_text}\n\n"
    "<b>Завтра ({tomorrow_date}):</b>\n"
    "{tomorrow_text}"
)


# ==========================================
# Video & Chart Graphics Text
# ==========================================

CHART_TITLE = "@Napryazhometr"
CHART_SUBTITLE_CURRENT = "Оперативний зріз (24 години)"
CHART_SUBTITLE_WEEK = "Тижневий графік відключень"
CHART_SUBTITLE_STATUS = "Діагностика напруги в реальному часі"

CHART_BADGE_NOW = "ЗАРАЗ"
CHART_HEADER_UPDATED = "Оновлено о {time_str}"

CHART_LEGEND_ON = "Світло є"
CHART_LEGEND_OFF = "Відключення"
CHART_LEGEND_UNKNOWN = "Графік відсутній"

CHART_STATUS_NO_POWER = "ЖИВЛЕННЯ ВІДСУТНЄ (МЕРЕЖА ЗНЕСТРУМЛЕНА)"
CHART_STATUS_NORMAL = "МЕРЕЖА СТАБІЛЬНА (НОРМА)"
CHART_STATUS_ALERT = "УВАГА: ВІДХИЛЕННЯ НАПРУГИ"
CHART_DIAGNOSTICS_FOOTER = "Моніторинг реле PZEM • Частота: {freq_display}"

WEEKDAY_NAMES_UA = (
    "Понеділок",
    "Вівторок",
    "Середа",
    "Четвер",
    "П'ятниця",
    "Субота",
    "Неділя",
)
LABEL_TODAY = "Сьогодні"
LABEL_TOMORROW = "Завтра"


# ==========================================
# Power Event & Plan Badge Templates
# ==========================================

PLAN_BADGES = {
    (True, "planned_outage"): "Нам пощастило! (Поза планом)",
    (True, "normal"): "Все за планом ДТЕК",
    (False, "normal"): "Світло зникло раніше графіка",
    (False, "planned_outage"): "Чітко за планом ДТЕК",
}

DEFAULT_BADGE_ON = "⚠️ Завершення аварійних робіт"
DEFAULT_BADGE_OFF = "⚠️ Аварійне відключення"

DURATION_OFF_SUMMARY = "Світла не було: {duration}"
DURATION_ON_SUMMARY = "Світло було: {duration}"

POWER_ON_PLAN_MESSAGES = {
    "planned_outage": "<tg-emoji emoji-id='5915833712368424979'>🎰</tg-emoji> <b>Нам пощастило!</b> Світло дали, хоча за графіком відключення.",
    "normal": "<tg-emoji emoji-id='5240108114006516325'>✅</tg-emoji> <b>Все за планом.</b> Включення співпадає з графіком.",
}
POWER_ON_PLAN_DEFAULT = "⚠️ <b>Світло з'явилося!</b> (Ймовірно завершення аварійних)."

POWER_OFF_PLAN_MESSAGES = {
    "normal": "<tg-emoji emoji-id='5197248832928227386'>🤬</tg-emoji> Світло зникло, <b>хоча за графіком має бути.</b>",
    "planned_outage": "<tg-emoji emoji-id='5240108114006516325'>✅</tg-emoji> <b>Планове відключення.</b> Все чітко за розкладом.",
}
POWER_OFF_PLAN_DEFAULT = "⚠️ <b>Аварійне/Екстрене відключення.</b>"

POWER_ON_DURATION = "\n⏳ Світла не було {duration}"
POWER_OFF_DURATION = "\n💡 Світло було: {duration}"

POWER_ON_NEXT_OUTAGE = "\n🌚 Наступне відключення: {time_str}"
POWER_OFF_NEXT_CONNECTIVITY = "\n💡 Очікуване ввімкнення: {time_str}"

POWER_ON_MESSAGE = (
    "<b><tg-emoji emoji-id='5458789741136715070'>🟢</tg-emoji> СВІТЛО З'ЯВИЛОСЯ</b>\n\n"
    "⚡️ Напруга: {voltage:.1f} V\n"
    "🕘 Світло з'явилося о {time_str}{dur_str}\n\n"
    "{plan_msg}{next_str}\n\n"
    "⏳ <i>Зачекайте 3-5 хв для стабілізації системи.</i>"
)

POWER_OFF_MESSAGE = (
    "<b><tg-emoji emoji-id='5458733511424876694'>🔴</tg-emoji> СВІТЛО ВИМКНУЛИ</b>\n\n"
    "🕒 Світло зникло о {time_str}{dur_str}\n\n"
    "{plan_msg}{next_str}\n\n"
    "🔋 Переходимо на автономне живлення.\n"
    "<i>Бот моніторить мережу 24/7</i>"
)


# ==========================================
# Event Card & Infographic Templates
# ==========================================

CARD_HEADER_TITLE = "@Napryazhometr"
CARD_SUBTITLE_EVENT = "Оперативне сповіщення мережі"
CARD_TITLE_PLAN_VS_FACT = "@Napryazhometr • ПЛАН ПРОТИ ФАКТУ"
CARD_SUBTITLE_PLAN_VS_FACT = "Аналіз доби ({date}) | {group_name}"

CARD_STATUS_ON = "СВІТЛО З'ЯВИЛОСЯ"
CARD_STATUS_OFF = "СВІТЛО ВИМКНУЛИ"
CARD_LABEL_RECORDED_TIME = "Час фіксації: {time_str}"

CARD_LABEL_PLAN = "ПЛАН"
CARD_LABEL_FACT = "ФАКТ"
CARD_BADGE_NOW = "ЗАРАЗ"

DEFAULT_MEME_TITLE_ON = "СВІТЛО ПОВЕРНУЛОСЯ!"
DEFAULT_MEME_TITLE_OFF = "ТЕМРЯВА НАСТАЛА..."


# ==========================================
# Keyboard & Popup Templates
# ==========================================

BTN_CHECK_STATUS = "👀 Шо там зараз?"

CMD_START_PROMPT = (
    "<b>📊 ПАНЕЛЬ МОНІТОРИНГУ</b>\n\n"
    "Чєкнути поточний стан мережі"
)

POPUP_PLAN_OK = "✅ План"
POPUP_PLAN_UNEXPECTED = "🎰 Поза планом"
POPUP_LIGHT_ON = "💡 Є"
POPUP_LIGHT_OFF = "🔌 Нема"

POPUP_MESSAGE = (
    "{state_icon} • {dur_str}\n"
    "{plan_badge}\n"
    "⚡️ {voltage:.1f}V{volt_warn}{freq_str}"
)

DEV_MENU_PROMPT = "🛠 <b>Панель тестування (DEV MODE)</b>\n\nОберіть подію для тестової відправки:"
