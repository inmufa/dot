"""4030-4059: MCP client and scheduler."""

from typing import Any

CATALOG: dict[int, dict[str, Any]] = {
    4030: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "MCP server not found",
            "ru": "MCP-сервер не найден",
            "uz": "MCP server topilmadi",
        },
    },
    4031: {
        "status": 403,
        "show": True,
        "messages": {
            "en": "MCP server is not trusted yet",
            "ru": "MCP-сервер ещё не одобрен",
            "uz": "MCP server hali tasdiqlanmagan",
        },
    },
    4032: {
        "status": 502,
        "show": True,
        "messages": {
            "en": "MCP server connection failed",
            "ru": "Не удалось подключиться к MCP-серверу",
            "uz": "MCP serverga ulanib bo'lmadi",
        },
    },
    4033: {
        "status": 504,
        "show": True,
        "messages": {
            "en": "MCP tool call timed out",
            "ru": "Время вызова MCP-инструмента истекло",
            "uz": "MCP vositasi chaqiruvi vaqti tugadi",
        },
    },
    4034: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "MCP server URL is not allowed",
            "ru": "Адрес MCP-сервера запрещён",
            "uz": "MCP server manzili ruxsat etilmagan",
        },
    },
    4035: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "Invalid cron expression",
            "ru": "Некорректное cron-выражение",
            "uz": "Noto'g'ri cron ifodasi",
        },
    },
    4036: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Schedule not found",
            "ru": "Расписание не найдено",
            "uz": "Jadval topilmadi",
        },
    },
    4037: {
        "status": 409,
        "show": True,
        "messages": {
            "en": "Too many scheduled jobs",
            "ru": "Слишком много заданий в расписании",
            "uz": "Jadvaldagi vazifalar juda ko'p",
        },
    },
    4038: {
        "status": 409,
        "show": True,
        "messages": {
            "en": "Built-in schedules cannot be deleted",
            "ru": "Встроенные задания нельзя удалить",
            "uz": "O'rnatilgan vazifalarni o'chirib bo'lmaydi",
        },
    },
    4039: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "MCP server configuration is invalid",
            "ru": "Некорректная конфигурация MCP-сервера",
            "uz": "MCP server sozlamasi noto'g'ri",
        },
    },
}
