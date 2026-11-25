"""2030-2039 session features, 4100-4129 uploads, files, models."""

from typing import Any

CATALOG: dict[int, dict[str, Any]] = {
    2030: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "Confirm deletion by passing confirm=<session id>",
            "ru": "Подтвердите удаление: confirm=<id сессии>",
            "uz": "O'chirishni tasdiqlang: confirm=<sessiya id>",
        },
    },
    2031: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "Invalid branch point",
            "ru": "Недопустимая точка ветвления",
            "uz": "Tarmoqlanish nuqtasi noto'g'ri",
        },
    },
    2032: {
        "status": 409,
        "show": True,
        "messages": {
            "en": "Nothing to regenerate",
            "ru": "Нечего перегенерировать",
            "uz": "Qayta yaratish uchun hech narsa yo'q",
        },
    },
    2033: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Project not found",
            "ru": "Проект не найден",
            "uz": "Loyiha topilmadi",
        },
    },
    2034: {
        "status": 409,
        "show": True,
        "messages": {
            "en": "Project already exists",
            "ru": "Проект уже существует",
            "uz": "Loyiha allaqachon mavjud",
        },
    },
    4100: {
        "status": 413,
        "show": True,
        "messages": {
            "en": "File is too large",
            "ru": "Файл слишком большой",
            "uz": "Fayl juda katta",
        },
    },
    4101: {
        "status": 415,
        "show": True,
        "messages": {
            "en": "This file type is not supported",
            "ru": "Этот тип файла не поддерживается",
            "uz": "Bu fayl turi qo'llab-quvvatlanmaydi",
        },
    },
    4102: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "Too many files in one upload",
            "ru": "Слишком много файлов за раз",
            "uz": "Bir vaqtda juda ko'p fayl",
        },
    },
    4103: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Attachment not found",
            "ru": "Вложение не найдено",
            "uz": "Biriktirma topilmadi",
        },
    },
    4104: {
        "status": 415,
        "show": True,
        "messages": {
            "en": "File content does not match its type",
            "ru": "Содержимое файла не соответствует его типу",
            "uz": "Fayl mazmuni turiga mos kelmaydi",
        },
    },
    4105: {
        "status": 422,
        "show": True,
        "messages": {
            "en": "The document could not be read",
            "ru": "Не удалось прочитать документ",
            "uz": "Hujjatni o'qib bo'lmadi",
        },
    },
    4110: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "File not found",
            "ru": "Файл не найден",
            "uz": "Fayl topilmadi",
        },
    },
    4111: {
        "status": 413,
        "show": True,
        "messages": {
            "en": "File is too large to preview",
            "ru": "Файл слишком большой для просмотра",
            "uz": "Fayl ko'rish uchun juda katta",
        },
    },
    4112: {
        "status": 403,
        "show": True,
        "messages": {
            "en": "Path is outside the workspace",
            "ru": "Путь вне рабочей папки",
            "uz": "Yo'l ishchi papkadan tashqarida",
        },
    },
    4120: {
        "status": 501,
        "show": True,
        "messages": {
            "en": "Model switching is not available; run: make model NAME=<file>",
            "ru": "Переключение модели недоступно; выполните: make model NAME=<файл>",
            "uz": "Modelni almashtirish mavjud emas; bajaring: make model NAME=<fayl>",
        },
    },
    4121: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Unknown model",
            "ru": "Неизвестная модель",
            "uz": "Noma'lum model",
        },
    },
    4122: {
        "status": 503,
        "show": True,
        "messages": {
            "en": "Telemetry is unavailable",
            "ru": "Телеметрия недоступна",
            "uz": "Telemetriya mavjud emas",
        },
    },
    4113: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "File is empty",
            "ru": "Файл пустой",
            "uz": "Fayl bo'sh",
        },
    },
}
