from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_role_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="🎓 Я Студент (Вуз / Колледж СКО)"), KeyboardButton(text="🏢 Я Работодатель")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# Список учебных заведений СКО / Петропавловска (Проверенные официальные адреса 2ГИС)
INSTITUTIONS = [
    ("pkmit", "⚙️ Колледж машиностроения и транспорта (ПКМиТ • ул. Ю. Медведева 1А)", "ПКМиТ им. Б. Ашимова (бывш. ПКЖТ)", "ул. Юрия Медведева 1А"),
    ("sku_pushkin", "🏛 СКУ им. Козыбаева (Главный • ул. Пушкина 86)", "СКУ им. М. Козыбаева", "ул. Пушкина 86"),
    ("sku_inter", "🏛 СКУ им. Козыбаева (Корпус №2 • ул. Интернациональная 26)", "СКУ им. М. Козыбаева", "ул. Интернациональная 26"),
    ("zhumabaev", "🎓 Высший колледж им. М. Жумабаева (ул. Абая 28)", "Высший колледж им. М. Жумабаева", "ул. Абая 28"),
    ("psek", "🏗 Строительно-экономический (ВСЭК • ул. Н. Назарбаева 262)", "Высший строительно-экономический колледж", "ул. Нурсултана Назарбаева 262"),
    ("vsppk", "🛠 Проф.-педагогический (ВСППК • пос. Борки, ул. Студенческая 1)", "ВСППК", "пос. Борки, ул. Студенческая 1"),
    ("med", "🩺 Высший медицинский колледж им. Тлеулина (ул. Шухова 42)", "Высший медицинский колледж им. Ж. Тлеулина", "ул. Ивана Шухова 42"),
    ("gtk", "📚 Гуманитарно-технический (ГТК • ул. Театральная 42)", "Гуманитарно-технический колледж", "ул. Театральная 42"),
    ("service", "👔 Колледж сферы обслуживания им. Даутова (ул. Интернациональная 42)", "Колледж сферы обслуживания им. И. Даутова", "ул. Интернациональная 42"),
    ("arts", "🎨 Колледж искусств им. Серкебаева (ул. Интернациональная 81)", "Колледж искусств им. Е. Серкебаева", "ул. Интернациональная 81"),
    ("other_sko", "🏫 Другой колледж СКО (Петропавловск)", "Колледж СКО", "г. Петропавловск")
]

def get_institution_keyboard() -> InlineKeyboardMarkup:
    kb = []
    for code, label, _, _ in INSTITUTIONS:
        kb.append([InlineKeyboardButton(text=label, callback_data=f"inst_{code}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_student_main_keyboard(is_free: bool = False) -> ReplyKeyboardMarkup:
    status_btn = "🔴 Нажать: «Занят на учебе»" if is_free else "🟢 «Свободен сегодня (17:00 – 21:00)»"
    kb = [
        [KeyboardButton(text=status_btn)],
        [KeyboardButton(text="🔍 Найти смены рядом со мной"), KeyboardButton(text="💼 Мой баланс и профиль")],
        [KeyboardButton(text="🏫 Сменить колледж / вуз"), KeyboardButton(text="🔄 Сменить роль")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_employer_main_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="📝 Опубликовать экспресс-заказ")],
        [KeyboardButton(text="📊 Мои активные заказы")],
        [KeyboardButton(text="🔄 Сменить роль")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_shift_inline_keyboard(shift_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="🤝 Взять смену", callback_data=f"take_shift_{shift_id}")],
        [InlineKeyboardButton(text="ℹ️ Подробнее", callback_data=f"info_shift_{shift_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_confirm_shift_keyboard(shift_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅ Опубликовать для студентов всех колледжей", callback_data=f"broadcast_shift_{shift_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_shift")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_employer_shift_actions_keyboard(shift_id: int, status: str):
    if status == "matched":
        kb = [
            [InlineKeyboardButton(text="✅ Завершить смену и перевести Kaspi", callback_data=f"done_shift_{shift_id}")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=kb)
    elif status == "open":
        kb = [
            [InlineKeyboardButton(text="❌ Отменить публикацию", callback_data=f"abort_shift_{shift_id}")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=kb)
    return None
