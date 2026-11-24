"""2000-2999: session, lock, context budget."""

from typing import Any

CATALOG: dict[int, dict[str, Any]] = {
    2000: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Session not found",
            "ru": "Сессия не найдена",
            "uz": "Sessiya topilmadi",
        },
    },
    2001: {
        "status": 409,
        "show": True,
        "messages": {
            "en": "Session is busy with another turn",
            "ru": "Сессия занята другим ходом",
            "uz": "Sessiya boshqa qadam bilan band",
        },
    },
    2002: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "Invalid rewind target",
            "ru": "Недопустимая точка отката",
            "uz": "Noto'g'ri qaytarish nuqtasi",
        },
    },
    2020: {
        "status": 502,
        "show": True,
        "messages": {
            "en": "Compaction failed",
            "ru": "Не удалось сжать контекст",
            "uz": "Kontekstni siqish amalga oshmadi",
        },
    },
    2021: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Memory fact not found",
            "ru": "Запись памяти не найдена",
            "uz": "Xotira yozuvi topilmadi",
        },
    },
    2022: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "Invalid memory fact",
            "ru": "Недопустимая запись памяти",
            "uz": "Xotira yozuvi noto'g'ri",
        },
    },
    2003: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Question not found or already answered",
            "ru": "Вопрос не найден или уже получил ответ",
            "uz": "Savol topilmadi yoki allaqachon javob berilgan",
        },
    },
    2004: {
        "status": 408,
        "show": True,
        "messages": {
            "en": "The question timed out without an answer",
            "ru": "Время ожидания ответа на вопрос истекло",
            "uz": "Savolga javob kutish vaqti tugadi",
        },
    },
    2005: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "Answer does not match the question options",
            "ru": "Ответ не соответствует вариантам вопроса",
            "uz": "Javob savol variantlariga mos kelmaydi",
        },
    },
}
