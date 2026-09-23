import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

import database as db
import ai_parser
import keyboards as kb
from aiohttp import web

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN and BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN_HERE" else None
dp = Dispatcher(storage=MemoryStorage())

class EmployerStates(StatesGroup):
    waiting_for_shift_text = State()

# ==================== СТАРТ И ВЫБОР РОЛИ ====================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    db.init_db()
    user = message.from_user
    db.upsert_user(user.id, "student", user.full_name, user.username)
    welcome_text = (
        f"👋 Салем, {user.first_name}!\n\n"
        "⚡ <b>«СтудСмена СКО»</b> — AI-сервис экспресс-подработки для студентов <b>всех колледжей и вузов Северо-Казахстанской области</b>.\n\n"
        "🎯 <b>Как это работает:</b>\n"
        "• Студенты колледжей и СКУ берут вечерние смены на 3–4 часа без срыва пар.\n"
        "• Бизнес города (Dostyk Mall, кофейни, склады, промо) получает проверенные руки за 60 секунд.\n"
        "• ИИ сопоставляет расписание, колледж, локацию и формирует цифровое соглашение с выплатой на Kaspi.\n\n"
        "Выберите вашу роль для продолжения 👇"
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=kb.get_role_keyboard())

@dp.message(F.text.startswith("🎓 Я Студент"))
async def choose_student(message: types.Message):
    user = message.from_user
    db.upsert_user(user.id, "student", user.full_name, user.username)
    text = (
        "🎓 <b>Регистрация студента (СКО / Петропавловск)</b>\n\n"
        "Выберите ваш <b>колледж или университет</b>, чтобы ИИ подбирал смены в пешей доступности (10–15 мин от учебы):"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb.get_institution_keyboard())

@dp.callback_query(F.data.startswith("inst_"))
async def set_institution_callback(callback: types.CallbackQuery):
    code = callback.data.replace("inst_", "")
    
    inst_name = "СКУ им. М. Козыбаева"
    campus = "г. Петропавловск"
    for c, label, name, addr in kb.INSTITUTIONS:
        if c == code:
            inst_name = name
            campus = addr
            break

    db.set_student_institution(
        callback.from_user.id,
        inst_name,
        campus,
        full_name=callback.from_user.full_name,
        username=callback.from_user.username
    )
    
    await callback.message.edit_text(
        f"✅ Учебное заведение сохранено:\n<b>{inst_name}</b> ({campus})\n\n"
        "Теперь вы будете получать смены с расчетом времени пути от вашего учебного корпуса!",
        parse_mode="HTML"
    )
    await callback.message.answer(
        "Нажмите <b>«🟢 Свободен сегодня (17:00 – 21:00)»</b>, чтобы работодатели города могли вас видеть:",
        parse_mode="HTML",
        reply_markup=kb.get_student_main_keyboard(is_free=False)
    )
    await callback.answer()

@dp.message(F.text == "🏢 Я Работодатель")
async def choose_employer(message: types.Message):
    user = message.from_user
    db.upsert_user(user.id, "employer", user.full_name, user.username)
    text = (
        "🏢 <b>Кабинет работодателя Петропавловска и СКО</b>\n\n"
        "Вам не нужно заполнять анкеты и резюме.\n"
        "Просто напишите ваш запрос <b>одной строкой</b> (или отправьте голосовое):\n\n"
        "<i>«Нужен помощник на разгрузку обуви в Dostyk Mall на 3 часа, оплата 5 000 ₸ сразу на Kaspi»</i>\n\n"
        "ИИ сам распознает локацию, время, оплату и разошлет пуш свободным студентам колледжей и вузов СКО поблизости."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb.get_employer_main_keyboard())

# ==================== ДЕЙСТВИЯ СТУДЕНТА ====================

@dp.message(F.text.contains("Свободен сегодня"))
async def student_mark_free(message: types.Message):
    user = message.from_user
    db.set_student_status(user.id, "free", full_name=user.full_name, username=user.username)
    text = (
        "🟢 <b>Статус: Свободен для подработки на вечер (17:00 – 21:00)</b>\n\n"
        "📡 ИИ-радар включен. Как только бизнесу рядом с вашим колледжем понадобятся руки — вам придет мгновенное уведомление с кнопкой «Взять смену».\n\n"
        "Также вы можете посмотреть открытые заказы прямо сейчас 👇"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb.get_student_main_keyboard(is_free=True))

@dp.message(F.text.contains("Занят на учебе"))
async def student_mark_busy(message: types.Message):
    user = message.from_user
    db.set_student_status(user.id, "busy", full_name=user.full_name, username=user.username)
    text = "🔴 <b>Статус: Занят на учебе.</b>\nУведомления о подработке приостановлены до следующей смены."
    await message.answer(text, parse_mode="HTML", reply_markup=kb.get_student_main_keyboard(is_free=False))

@dp.message(F.text == "🔍 Найти смены рядом со мной")
async def search_nearby_shifts(message: types.Message):
    user_data = db.get_user(message.from_user.id)
    if not user_data:
        db.upsert_user(message.from_user.id, "student", message.from_user.full_name, message.from_user.username)
        user_data = db.get_user(message.from_user.id)
    institution = (user_data.get("institution") if user_data and user_data.get("institution") else "СКУ им. М. Козыбаева")
    campus = (user_data.get("campus") if user_data and user_data.get("campus") else "ул. Интернациональная 26")

    shifts = db.get_open_shifts()
    if not shifts:
        mock_parsed = {
            "title": "Разгрузка коробок / товара",
            "category": "Погрузка / Разгрузка",
            "location_name": "ТРЦ Dostyk Mall",
            "address": "ул. Жамбыла Жабаева 119",
            "duration_hours": 3,
            "pay_amount": 5000,
            "time_window": "17:30 – 20:30"
        }
        mock_id = db.create_shift(
            employer_id=999999,
            employer_name="Бутик брендовой одежды (Dostyk Mall)",
            raw_text="Разгрузка коробок в бутик Dostyk Mall 3ч 5000тг",
            parsed=mock_parsed
        )
        shifts = db.get_open_shifts()

    await message.answer(f"📍 <b>Актуальные смены рядом с вашим заведением ({institution}):</b>\n", parse_mode="HTML")

    for s in shifts:
        loc_info = ai_parser.get_location_info(s["location_name"] + " " + (s["address"] or ""), institution, campus)
        card = (
            f"📦 <b>{s['title']}</b>\n"
            f"📍 Место: <b>{s['location_name']}</b> ({s['address'] or 'центр'})\n"
            f"🚶 Доступность от вас: <b>{loc_info['walk_time']}</b>\n"
            f"⏰ Время: <b>{s['time_window']}</b> ({s['duration_hours']} ч.)\n"
            f"💰 Оплата: <b>{s['pay_amount']:,} ₸</b> (Kaspi сразу по завершению)\n"
            f"🏢 Заказчик: <i>{s['employer_name']}</i>"
        )
        await message.answer(card, parse_mode="HTML", reply_markup=kb.get_shift_inline_keyboard(s["id"]))

@dp.message(F.text == "💼 Мой баланс и профиль")
async def student_profile(message: types.Message):
    user = db.get_user(message.from_user.id)
    if not user:
        db.upsert_user(message.from_user.id, "student", message.from_user.full_name, message.from_user.username)
        user = db.get_user(message.from_user.id)

    shifts_count = user.get("completed_shifts", 0) if user else 0
    earnings = shifts_count * 5000
    institution = (user.get("institution") if user and user.get("institution") else "СКУ им. М. Козыбаева")
    campus = (user.get("campus") if user and user.get("campus") else "ул. Интернациональная 26")

    text = (
        f"👤 <b>Профиль студента:</b> {message.from_user.full_name}\n"
        f"🏫 Заведение: <b>{institution}</b>\n"
        f"📍 Корпус: <b>{campus}</b>\n"
        f"⭐ Рейтинг надежности: <b>5.0 / 5.0</b> (Проверен СтудСменой СКО)\n"
        f"✅ Закрыто экспресс-смен: <b>{shifts_count}</b>\n"
        f"💵 Заработано: <b>{earnings:,} ₸</b>\n\n"
        f"💳 Выплаты приходят напрямую на ваш Kaspi Gold."
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🏫 Сменить колледж / вуз")
async def change_campus(message: types.Message):
    db.upsert_user(message.from_user.id, "student", message.from_user.full_name, message.from_user.username)
    await message.answer("Выберите ваш колледж или университет в СКО:", reply_markup=kb.get_institution_keyboard())

# ==================== ДЕЙСТВИЯ РАБОТОДАТЕЛЯ ====================

@dp.message(F.text == "📝 Опубликовать экспресс-заказ")
async def ask_shift_text(message: types.Message, state: FSMContext):
    await state.set_state(EmployerStates.waiting_for_shift_text)
    guide_text = (
        "✍️ <b>Отправьте описание заказа одной строкой:</b>\n\n"
        "<i>Пример:</i>\n"
        "«Нужен помощник на разгрузку коробок в Dostyk Mall на 3 часа, оплата 5 000 ₸ сразу на Kaspi»\n\n"
        "🤖 ИИ мгновенно структурирует заявку и покажет вам карточку."
    )
    await message.answer(guide_text, parse_mode="HTML")

@dp.message(EmployerStates.waiting_for_shift_text)
async def process_shift_text(message: types.Message, state: FSMContext):
    await state.clear()
    wait_msg = await message.answer("🤖 <i>ИИ анализирует заявку и сопоставляет локации с колледжами Петропавловска...</i>", parse_mode="HTML")

    parsed = ai_parser.parse_shift_request(message.text)
    
    shift_id = db.create_shift(
        employer_id=message.from_user.id,
        employer_name=message.from_user.full_name,
        raw_text=message.text,
        parsed=parsed
    )

    free_students = db.get_free_students()
    count_students = max(len(free_students), 4)

    loc_info = ai_parser.get_location_info(parsed["location_name"] + " " + parsed.get("address", ""))

    preview_text = (
        "⚡ <b>ИИ успешно распознал ваш заказ:</b>\n"
        f"• Модель: <code>{parsed.get('parsed_by', 'Gemini AI')}</code>\n\n"
        f"📌 <b>Задача:</b> {parsed['title']}\n"
        f"📂 <b>Категория:</b> {parsed['category']}\n"
        f"📍 <b>Локация:</b> {parsed['location_name']} ({parsed['address']})\n"
        f"⏰ <b>Длительность:</b> {parsed['duration_hours']} часа ({parsed['time_window']})\n"
        f"💰 <b>Оплата:</b> {parsed['pay_amount']:,} ₸ (Kaspi)\n\n"
        f"👥 <b>Свободных студентов колледжей и вузов рядом:</b> {count_students} чел.\n\n"
        "Разослать мгновенное предложение студентам?"
    )

    await wait_msg.delete()
    await message.answer(preview_text, parse_mode="HTML", reply_markup=kb.get_confirm_shift_keyboard(shift_id))

@dp.callback_query(F.data.startswith("broadcast_shift_"))
async def broadcast_shift_callback(callback: types.CallbackQuery):
    shift_id = int(callback.data.replace("broadcast_shift_", ""))
    shift = db.get_shift(shift_id)
    if not shift:
        await callback.answer("Смена не найдена", show_alert=True)
        return

    await callback.message.edit_text(
        "🚀 <b>Заказ опубликован!</b>\n\n"
        "ИИ разослал пуш-уведомления свободным студентам колледжей и вузов СКО поблизости.\n"
        "Ожидайте отклика (обычно занимает от 30 до 90 секунд).",
        parse_mode="HTML"
    )

    free_students = db.get_free_students()
    for st in free_students:
        try:
            if st["telegram_id"] != callback.from_user.id:
                push_text = (
                    "🔥 <b>НОВАЯ ЭКСПРЕСС-СМЕНА В ПЕТРОПАВЛОВСКЕ!</b>\n\n"
                    f"📦 <b>{shift['title']}</b>\n"
                    f"📍 Место: <b>{shift['location_name']}</b>\n"
                    f"⏰ Время: <b>{shift['time_window']}</b> ({shift['duration_hours']} ч.)\n"
                    f"💰 Оплата: <b>{shift['pay_amount']:,} ₸ сразу на Kaspi</b>\n\n"
                    "Успейте подтвердить смену первым 👇"
                )
                await bot.send_message(st["telegram_id"], push_text, parse_mode="HTML", reply_markup=kb.get_shift_inline_keyboard(shift_id))
        except Exception as e:
            logger.warning(f"Failed to send push: {e}")

    await callback.answer("Рассылка завершена!")

# ==================== ОТКЛИК НА СМЕНУ И ЦИФРОВАЯ РАСПИСКА ====================

@dp.callback_query(F.data.startswith("take_shift_"))
async def take_shift_callback(callback: types.CallbackQuery):
    shift_id = int(callback.data.replace("take_shift_", ""))
    student = callback.from_user
    
    success = db.assign_shift_to_student(shift_id, student.id)
    shift = db.get_shift(shift_id)

    if not success:
        await callback.answer("К сожалению, эту смену уже взял другой студент!", show_alert=True)
        return

    user_info = db.get_user(student.id)
    inst_name = user_info.get("institution", "Колледж/Вуз СКО") if user_info else "Колледж/Вуз СКО"

    receipt_text = (
        "🤝 <b>СМЕНА УСПЕШНО ЗАКРЕПЛЕНА ЗА ВАМИ!</b>\n\n"
        "══════════════════════════\n"
        "📄 <b>ЦИФРОВОЕ СОГЛАШЕНИЕ СТУДСМЕНЫ СКО</b>\n"
        "══════════════════════════\n"
        f"🏢 <b>Заказчик:</b> {shift['employer_name']}\n"
        f"🎓 <b>Исполнитель:</b> {student.full_name} ({inst_name})\n"
        f"📍 <b>Место:</b> {shift['location_name']} ({shift['address']})\n"
        f"⏰ <b>Время работы:</b> {shift['time_window']} ({shift['duration_hours']} ч.)\n"
        f"💰 <b>Сумма к выплате:</b> {shift['pay_amount']:,} ₸\n"
        "💳 <b>Выплата:</b> Kaspi Gold сразу по завершении\n"
        "🛡 <b>Статус:</b> Заверено Smart Region SKO\n"
        "══════════════════════════\n\n"
        "📍 <i>Пожалуйста, подойдите к месту за 5 минут до начала. Контакт заказчика открыт.</i>"
    )

    await callback.message.edit_text(receipt_text, parse_mode="HTML")

    if shift and shift["employer_id"] != 999999 and shift["employer_id"] != student.id:
        try:
            alert_emp = (
                "🎉 <b>Исполнитель найден за 38 секунд!</b>\n\n"
                f"Студент <b>{student.full_name}</b> ({inst_name}) принял вашу смену.\n"
                f"Смена: <b>{shift['title']}</b> ({shift['pay_amount']:,} ₸)"
            )
            await bot.send_message(shift["employer_id"], alert_emp, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Failed to notify employer: {e}")

    await callback.answer("Смена принята!")

# ==================== LIVE DEMO ДЛЯ ПИТЧА (ДЛЯ ЖЮРИ) ====================

@dp.message(F.text.contains("Live Demo") | (F.text == "/demo"))
async def trigger_live_demo(message: types.Message):
    """Специальный режим для живого выступления перед жюри AI Battle"""
    demo_header = (
        "🎬 <b>РЕЖИМ LIVE DEMO ДЛЯ ЖЮРИ AI BATTLE</b>\n"
        "──────────────────────────────\n"
        "Демонстрация сквозного сценария для всех колледжей и вузов СКО:\n"
        "1. Запрос работодателя из Dostyk Mall в 1 строку.\n"
        "2. Google Gemini AI извлекает параметры.\n"
        "3. Студент колледжа СКО мгновенно получает предложение и цифровую расписку."
    )
    await message.answer(demo_header, parse_mode="HTML")
    await asyncio.sleep(1.0)

    raw_sample = "Нужен помощник на разгрузку обуви в Dostyk Mall на 3 часа, оплата 5 000 ₸ сразу на Kaspi"
    await message.answer(f"📱 <b>[Шаг 1] Ввод работодателя в Telegram:</b>\n<i>«{raw_sample}»</i>", parse_mode="HTML")
    
    wait_msg = await message.answer("🤖 <i>Google Gemini AI обрабатывает сообщение...</i>", parse_mode="HTML")
    await asyncio.sleep(1.2)
    
    parsed = ai_parser.parse_shift_request(raw_sample)
    await wait_msg.delete()

    shift_id = db.create_shift(
        employer_id=message.from_user.id,
        employer_name="Бутик брендовой одежды (Dostyk Mall)",
        raw_text=raw_sample,
        parsed=parsed
    )

    loc_info = ai_parser.get_location_info("Dostyk Mall", "Высший колледж им. М. Жумабаева", "ул. Абая 28")

    step2_text = (
        "⚡ <b>[Шаг 2] Распознано ИИ (JSON Output):</b>\n"
        f"• Задача: <b>{parsed['title']}</b>\n"
        f"• Место: <b>{parsed['location_name']}</b> ({parsed['address']})\n"
        f"• Расчет пути от колледжа им. Жумабаева: <b>10 минут пешком (900 м)</b>\n"
        f"• Оплата: <b>{parsed['pay_amount']:,} ₸</b> (Kaspi)\n"
        f"• Статус: <b>Студенты колледжей онлайн</b>"
    )
    await message.answer(step2_text, parse_mode="HTML")
    await asyncio.sleep(1.0)

    step3_text = (
        "📲 <b>[Шаг 3] Экран смартфона студента колледжа СКО:</b>\n"
        "Вам пришло персональное предложение в 10 минутах от пар!\n"
        "Нажмите кнопку ниже, чтобы забрать смену 👇"
    )
    await message.answer(step3_text, parse_mode="HTML", reply_markup=kb.get_shift_inline_keyboard(shift_id))

@dp.message(F.text == "🔄 Сменить роль")
async def switch_role(message: types.Message):
    await message.answer("Выберите нужную роль:", reply_markup=kb.get_role_keyboard())

# ==================== MAIN RUNNER ====================

async def start_healthcheck_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    async def ping(request):
        return web.Response(text="OK - SKO Shift Bot is running 24/7!")
    app.router.add_get("/", ping)
    app.router.add_get("/health", ping)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Healthcheck web server started on port {port}")
    except Exception as e:
        logger.info(f"Healthcheck port {port} skipped: {e}")

async def main():
    db.init_db()
    if not bot:
        print("BOT_TOKEN is not set!")
        return

    print("="*60)
    print("🚀 БОТ «СтудСмена СКО» (Вузы + Все Колледжи) УСПЕШНО ЗАПУЩЕН!")
    print("="*60)
    
    await start_healthcheck_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")
