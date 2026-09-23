import os
import json
import re
from typing import Dict, Any, Optional
from google import genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Warning: Failed to init Gemini client: {e}")

# Популярные точки подработки в Петропавловске
PETROPAVLOVSK_LOCATIONS = {
    "dostyk": {
        "keywords": ["достык", "dostyk", "достык молл", "жамбыла 119"],
        "name": "ТРЦ Dostyk Mall",
        "address": "ул. Жамбыла Жабаева, 119"
    },
    "city_mall": {
        "keywords": ["сити", "сити молл", "city mall", "уалиханова", "муканова"],
        "name": "ТРЦ City Mall",
        "address": "ул. Ш. Уалиханова, 56"
    },
    "tsum": {
        "keywords": ["цум", "арбат", "конституции", "центр", "театральная"],
        "name": "ЦУМ / ул. Конституции Казахстана",
        "address": "ул. Конституции Казахстана"
    },
    "cafe": {
        "keywords": ["кофейня", "кофе", "додо", "dodo", "zheka", "бум", "boom", "ресторан"],
        "name": "Кофейня / Общепит в центре",
        "address": "ул. Конституции Казахстана / Интернациональная"
    },
    "warehouse": {
        "keywords": ["склад", "промзона", "гашека", "база", "оптовый"],
        "name": "Складской комплекс",
        "address": "ул. Гашека / промзона"
    }
}

def get_location_info(text: str, institution: str = "СКУ им. М. Козыбаева", campus: str = "") -> Dict[str, str]:
    """Рассчитывает пешую/транспортную доступность от выбранного колледжа или вуза СКО"""
    text_lower = text.lower()
    matched_loc = None
    for loc_id, loc_data in PETROPAVLOVSK_LOCATIONS.items():
        for kw in loc_data["keywords"]:
            if kw in text_lower:
                matched_loc = loc_data
                break
        if matched_loc:
            break

    if not matched_loc:
        matched_loc = {
            "name": "Петропавловск (центр)",
            "address": "Центральный район"
        }

    # Логика расчета времени от учебного заведения
    inst_lower = (institution + " " + campus).lower()
    
    if "достык" in matched_loc["name"].lower():
        if "жумабаева" in inst_lower or "абая" in inst_lower:
            walk_time = "🚶 10 минут пешком (~850 м)"
        elif "интернациональная" in inst_lower:
            walk_time = "🚶 12 минут пешком (1.1 км)"
        elif "пушкина" in inst_lower:
            walk_time = "🚶 15 минут пешком (1.4 км)"
        elif "театральная" in inst_lower or "гтк" in inst_lower:
            walk_time = "🚶 9 минут пешком (750 м)"
        elif "пкмит" in inst_lower or "медведева" in inst_lower or "машиностр" in inst_lower:
            walk_time = "🚌 12 минут (прямой автобус №24 / №4А)"
        elif "псек" in inst_lower or "всэк" in inst_lower or "назарбаева" in inst_lower:
            walk_time = "🚶 14 минут пешком / 🚌 5 минут"
        elif "мед" in inst_lower or "шухова" in inst_lower:
            walk_time = "🚌 12 минут (автобус №25)"
        elif "всппк" in inst_lower or "борки" in inst_lower:
            walk_time = "🚌 16 минут (автобус №4А)"
        else:
            walk_time = "🚶 ~10-15 минут от вашего колледжа"
    elif "сити" in matched_loc["name"].lower():
        if "мед" in inst_lower or "шухова" in inst_lower:
            walk_time = "🚶 5 минут пешком (450 м)"
        elif "псек" in inst_lower or "всэк" in inst_lower or "назарбаева" in inst_lower:
            walk_time = "🚶 10 минут пешком (900 м)"
        elif "пкмит" in inst_lower or "медведева" in inst_lower or "машиностр" in inst_lower:
            walk_time = "🚌 15 минут (автобус №4А)"
        elif "жумабаева" in inst_lower:
            walk_time = "🚌 8 минут на автобусе"
        elif "интернациональная" in inst_lower or "пушкина" in inst_lower:
            walk_time = "🚌 8 минут на автобусе"
        else:
            walk_time = "🚌 ~10 минут на транспорте"
    elif "цум" in matched_loc["name"].lower() or "конституции" in matched_loc["name"].lower():
        if "жумабаева" in inst_lower or "абая" in inst_lower:
            walk_time = "🚶 5 минут пешком"
        elif "интернациональная" in inst_lower:
            walk_time = "🚶 7 минут пешком"
        elif "театральная" in inst_lower or "гтк" in inst_lower:
            walk_time = "🚶 8 минут пешком"
        elif "пкмит" in inst_lower or "медведева" in inst_lower:
            walk_time = "🚌 10 минут (автобус №2)"
        else:
            walk_time = "🚶 8-10 минут пешком"
    else:
        walk_time = "🚶 ~10-15 минут от вашего учебного заведения"

    return {
        "name": matched_loc["name"],
        "address": matched_loc["address"],
        "walk_time": walk_time
    }

def fallback_rule_parser(raw_text: str) -> Dict[str, Any]:
    """Резервный оффлайн-парсер на случай отсутствия связи"""
    text_lower = raw_text.lower()
    
    pay_amount = 5000
    pay_match = re.search(r'(\d+[\s\.]?\d*)\s*(?:к|k|тыс|тенге|тг|₸)', text_lower)
    if pay_match:
        val = pay_match.group(1).replace(" ", "").replace(".", "")
        try:
            num = int(val)
            pay_amount = num * 1000 if num < 50 else num
        except:
            pay_amount = 5000
    else:
        num_match = re.search(r'\b(3000|4000|5000|6000|7000|8000|10000)\b', text_lower)
        if num_match:
            pay_amount = int(num_match.group(1))

    duration_hours = 3
    dur_match = re.search(r'(\d+)\s*(?:час|ч|hour)', text_lower)
    if dur_match:
        duration_hours = int(dur_match.group(1))

    category = "Погрузка / Разгрузка"
    title = "Помощь на складе / разгрузка"
    if any(w in text_lower for w in ["короб", "разгруз", "погруз", "таскать", "мешки", "ящик"]):
        category = "Погрузка / Разгрузка"
        title = "Разгрузка коробок / товара"
    elif any(w in text_lower for w in ["промо", "листовк", "флаер", "раздача"]):
        category = "Промо / Маркетинг"
        title = "Раздача промо-материалов"
    elif any(w in text_lower for w in ["официант", "бариста", "посуд", "кухн", "кафе", "кофе"]):
        category = "Общепит / HoReCa"
        title = "Помощник в кофейню / ресторан"
    elif any(w in text_lower for w in ["курьер", "доставк", "отвезти"]):
        category = "Курьерские поручения"
        title = "Пешая доставка по центру"
    elif any(w in text_lower for w in ["магаз", "бутик", "развес", "вешалки", "инвентар"]):
        category = "Ритейл / Магазин"
        title = "Помощь в бутике / раскладка товара"

    loc_info = get_location_info(raw_text)

    return {
        "title": title,
        "category": category,
        "location_name": loc_info["name"],
        "address": loc_info["address"],
        "duration_hours": duration_hours,
        "pay_amount": pay_amount,
        "time_window": "17:00 - 20:00",
        "description": raw_text.strip(),
        "parsed_by": "Local NLP Fallback"
    }

def parse_shift_request(raw_text: str) -> Dict[str, Any]:
    """Парсинг произвольного текста работодателя через Gemini AI с резервным fallback"""
    if not client or not GEMINI_API_KEY:
        return fallback_rule_parser(raw_text)

    prompt = f"""
Ты — AI-диспетчер сервиса студенческих подработок для студентов вузов и колледжей города Петропавловск и Северо-Казахстанской области.
Работодатель отправил запрос на подработку в свободной форме:
"{raw_text}"

Твоя задача — извлечь параметры смены и вернуть СТРОГО валидный JSON:
{{
  "title": "краткое емкое название смены (например, 'Разгрузка коробок в бутик', 'Раздача флаеров на Арбате')",
  "category": "одна из категорий: 'Погрузка / Разгрузка', 'Ритейл / Торговля', 'Общепит / Кафе', 'Промо / Мероприятия', 'Курьер / Доставка'",
  "location_name": "название места (например: ТРЦ Dostyk Mall, ТРЦ City Mall, ЦУМ, Арбат, кафе Додо)",
  "address": "улица и номер дома, если упомянуты",
  "duration_hours": 3,
  "pay_amount": 5000,
  "time_window": "интервал времени (например: '17:00 - 20:00' или 'сегодня вечер')",
  "description": "краткое описание задачи в 1-2 предложениях"
}}
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        
        raw_res = response.text.strip()
        if "```" in raw_res:
            raw_res = re.sub(r'```(?:json)?', '', raw_res).strip()
        
        parsed = json.loads(raw_res)
        parsed["parsed_by"] = "Google Gemini AI (3.5-Flash)"
        
        loc_info = get_location_info(parsed.get("location_name", "") + " " + raw_text)
        if not parsed.get("address") or parsed.get("address") == "не указан":
            parsed["address"] = loc_info["address"]
        if not parsed.get("location_name"):
            parsed["location_name"] = loc_info["name"]

        return parsed
    except Exception as e:
        print(f"Gemini API error, falling back to rule parser: {e}")
        return fallback_rule_parser(raw_text)
