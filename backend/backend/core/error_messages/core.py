"""1000-1999: server, auth, not found, validation, rate limit, http, readiness."""

from typing import Any

CATALOG: dict[int, dict[str, Any]] = {
    1000: {
        "status": 500,
        "show": True,
        "messages": {
            "en": "Internal error",
            "ru": "Внутренняя ошибка",
            "uz": "Ichki xatolik",
        },
    },
    1001: {
        "status": 401,
        "show": True,
        "messages": {
            "en": "Invalid or missing API token",
            "ru": "Неверный или отсутствующий токен",
            "uz": "Token noto'g'ri yoki yo'q",
        },
    },
    1002: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Not found",
            "ru": "Не найдено",
            "uz": "Topilmadi",
        },
    },
    1003: {
        "status": 422,
        "show": True,
        "messages": {
            "en": "Invalid request data",
            "ru": "Некорректные данные запроса",
            "uz": "So'rov ma'lumotlari noto'g'ri",
        },
    },
    1004: {
        "status": 429,
        "show": True,
        "messages": {
            "en": "Too many requests",
            "ru": "Слишком много запросов",
            "uz": "So'rovlar juda ko'p",
        },
    },
    1005: {
        "status": 403,
        "show": True,
        "messages": {
            "en": "Forbidden",
            "ru": "Доступ запрещён",
            "uz": "Ruxsat yo'q",
        },
    },
    1006: {
        "status": 405,
        "show": True,
        "messages": {
            "en": "Method not allowed",
            "ru": "Метод не поддерживается",
            "uz": "Metod qo'llab-quvvatlanmaydi",
        },
    },
    1007: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "Bad request",
            "ru": "Некорректный запрос",
            "uz": "Noto'g'ri so'rov",
        },
    },
    1008: {
        "status": 503,
        "show": True,
        "messages": {
            "en": "Service not ready",
            "ru": "Сервис не готов",
            "uz": "Xizmat tayyor emas",
        },
    },
    1010: {
        "status": 413,
        "show": True,
        "messages": {
            "en": "Message is too long",
            "ru": "Сообщение слишком длинное",
            "uz": "Xabar juda uzun",
        },
    },
    1011: {
        "status": 413,
        "show": True,
        "messages": {
            "en": "Request body is too large",
            "ru": "Тело запроса слишком большое",
            "uz": "So'rov hajmi juda katta",
        },
    },
}
