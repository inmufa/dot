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
    4017: {
        "status": 409,
        "show": True,
        "messages": {
            "en": "Dot is using the browser right now. Try again in a moment",
            "ru": "Dot сейчас пользуется браузером. Повторите через минуту",
            "uz": "Dot hozir brauzerdan foydalanmoqda. Birozdan keyin urinib ko'ring",
        },
    },
    4018: {
        "status": 403,
        "show": True,
        "messages": {
            "en": "The browser blocked this address (private or disallowed)",
            "ru": "Браузер заблокировал этот адрес (приватный или запрещённый)",
            "uz": "Brauzer bu manzilni blokladi (shaxsiy yoki ruxsat etilmagan)",
        },
    },
    4019: {
        "status": 502,
        "show": True,
        "messages": {
            "en": "The page did not load (address not found, refused or timed out)",
            "ru": "Страница не загрузилась (адрес не найден, соединение отклонено или истекло время ожидания)",
            "uz": "Sahifa yuklanmadi (manzil topilmadi, ulanish rad etildi yoki vaqt tugadi)",
        },
    },
    4020: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "This image source is not allowed",
            "ru": "Этот источник изображения запрещён",
            "uz": "Bu rasm manbasiga ruxsat yo'q",
        },
    },
    4021: {
        "status": 415,
        "show": True,
        "messages": {
            "en": "Not a supported image",
            "ru": "Неподдерживаемое изображение",
            "uz": "Qo'llab-quvvatlanmaydigan rasm",
        },
    },
    4022: {
        "status": 413,
        "show": True,
        "messages": {
            "en": "The image is too large",
            "ru": "Изображение слишком большое",
            "uz": "Rasm juda katta",
        },
    },
    4023: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Image not found",
            "ru": "Изображение не найдено",
            "uz": "Rasm topilmadi",
        },
    },
}
