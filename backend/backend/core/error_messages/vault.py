"""4140-4159: credential vault."""

from typing import Any

CATALOG: dict[int, dict[str, Any]] = {
    4140: {
        "status": 503,
        "show": True,
        "messages": {
            "en": "Credential vault is off: DOT_VAULT_KEY is not set (run 'make vault-key')",
            "ru": "Хранилище паролей выключено: не задан DOT_VAULT_KEY (выполните 'make vault-key')",
            "uz": "Parollar ombori o'chiq: DOT_VAULT_KEY berilmagan ('make vault-key' ni ishga tushiring)",
        },
    },
    4141: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Saved login not found",
            "ru": "Сохранённый вход не найден",
            "uz": "Saqlangan kirish topilmadi",
        },
    },
    4142: {
        "status": 409,
        "show": True,
        "messages": {
            "en": "A saved login with this label already exists",
            "ru": "Сохранённый вход с такой меткой уже есть",
            "uz": "Bunday yorliqli saqlangan kirish allaqachon bor",
        },
    },
    4143: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "Confirm the deletion with confirm=<id>",
            "ru": "Подтвердите удаление: confirm=<id>",
            "uz": "O'chirishni tasdiqlang: confirm=<id>",
        },
    },
    4144: {
        "status": 403,
        "show": True,
        "messages": {
            "en": "This page is not on a site bound to the saved login; nothing was typed",
            "ru": "Эта страница не относится к сайту сохранённого входа; ничего не введено",
            "uz": "Bu sahifa saqlangan kirishga bog'langan saytga tegishli emas; hech narsa kiritilmadi",
        },
    },
    4145: {
        "status": 429,
        "show": True,
        "messages": {
            "en": "Too many login attempts for this saved login. Wait a few minutes",
            "ru": "Слишком много попыток входа с этими данными. Подождите несколько минут",
            "uz": "Bu kirish uchun urinishlar juda ko'p. Bir necha daqiqa kuting",
        },
    },
    4146: {
        "status": 422,
        "show": True,
        "messages": {
            "en": "Saved logins limit reached",
            "ru": "Достигнут предел сохранённых входов",
            "uz": "Saqlangan kirishlar chegarasiga yetildi",
        },
    },
    4147: {
        "status": 500,
        "show": True,
        "messages": {
            "en": "Vault data cannot be decrypted (wrong key or damaged record)",
            "ru": "Данные хранилища не расшифровываются (неверный ключ или повреждённая запись)",
            "uz": "Ombor ma'lumotlarini ochib bo'lmadi (kalit noto'g'ri yoki yozuv buzilgan)",
        },
    },
    4148: {
        "status": 403,
        "show": True,
        "messages": {
            "en": "The login form looks unsafe (hidden, framed or posting to another site); nothing was typed",
            "ru": "Форма входа выглядит небезопасной (скрыта, во фрейме или шлёт данные на другой сайт); ничего не введено",
            "uz": "Kirish shakli xavfli ko'rinadi (yashirin, freymda yoki boshqa saytga yuboradi); hech narsa kiritilmadi",
        },
    },
    4149: {
        "status": 422,
        "show": True,
        "messages": {
            "en": "Invalid site address for a saved login (use https://host)",
            "ru": "Недопустимый адрес сайта для сохранённого входа (используйте https://host)",
            "uz": "Saqlangan kirish uchun sayt manzili yaroqsiz (https://host dan foydalaning)",
        },
    },
    4150: {
        "status": 409,
        "show": True,
        "messages": {
            "en": "Open the site in the Browser tab first, then save the session",
            "ru": "Сначала откройте сайт во вкладке «Браузер», затем сохраните сеанс",
            "uz": "Avval saytni 'Brauzer' bo'limida oching, so'ng seansni saqlang",
        },
    },
    4151: {
        "status": 409,
        "show": True,
        "messages": {
            "en": "No browser session to save for this site (nothing signed in)",
            "ru": "Нет сеанса браузера для сохранения на этом сайте (вход не выполнен)",
            "uz": "Bu sayt uchun saqlanadigan brauzer seansi yo'q (kirilmagan)",
        },
    },
}
