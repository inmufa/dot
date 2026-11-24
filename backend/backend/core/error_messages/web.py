"""4010-4019: web search, web fetch and browser tools."""

from typing import Any

CATALOG: dict[int, dict[str, Any]] = {
    4010: {
        "status": 502,
        "show": True,
        "messages": {
            "en": "Search service is unavailable",
            "ru": "Поисковый сервис недоступен",
            "uz": "Qidiruv xizmati mavjud emas",
        },
    },
    4011: {
        "status": 502,
        "show": True,
        "messages": {
            "en": "Search service returned an invalid response",
            "ru": "Поисковый сервис вернул некорректный ответ",
            "uz": "Qidiruv xizmati noto'g'ri javob qaytardi",
        },
    },
    4012: {
        "status": 403,
        "show": True,
        "messages": {
            "en": "This URL is not allowed",
            "ru": "Этот URL запрещён",
            "uz": "Bu URL ga ruxsat yo'q",
        },
    },
    4013: {
        "status": 502,
        "show": True,
        "messages": {
            "en": "Could not fetch the page",
            "ru": "Не удалось загрузить страницу",
            "uz": "Sahifani yuklab bo'lmadi",
        },
    },
    4014: {
        "status": 415,
        "show": True,
        "messages": {
            "en": "Unsupported or oversized page content",
            "ru": "Неподдерживаемое или слишком большое содержимое страницы",
            "uz": "Sahifa tarkibi qo'llab-quvvatlanmaydi yoki juda katta",
        },
    },
    4015: {
        "status": 502,
        "show": True,
        "messages": {
            "en": "Browser is unavailable (start the 'browser' compose profile)",
            "ru": "Браузер недоступен (запустите профиль compose 'browser')",
            "uz": "Brauzer mavjud emas ('browser' compose profilini ishga tushiring)",
        },
    },
    4016: {
        "status": 502,
        "show": True,
        "messages": {
            "en": "Browser action failed",
            "ru": "Действие в браузере не удалось",
            "uz": "Brauzer amali bajarilmadi",
        },
    },
}
