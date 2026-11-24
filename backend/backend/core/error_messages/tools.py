"""4000-4999: sandbox, browser, search, MCP, LLM."""

from typing import Any

CATALOG: dict[int, dict[str, Any]] = {
    4000: {
        "status": 502,
        "show": True,
        "messages": {
            "en": "Language model is unavailable",
            "ru": "Языковая модель недоступна",
            "uz": "Til modeli mavjud emas",
        },
    },
    4001: {
        "status": 502,
        "show": True,
        "messages": {
            "en": "Sandbox is unavailable",
            "ru": "Песочница недоступна",
            "uz": "Sandbox mavjud emas",
        },
    },
    4002: {
        "status": 504,
        "show": True,
        "messages": {
            "en": "Tool call timed out",
            "ru": "Время выполнения инструмента истекло",
            "uz": "Vosita bajarilishi vaqti tugadi",
        },
    },
    4003: {
        "status": 502,
        "show": True,
        "messages": {
            "en": "Model produced malformed tool calls repeatedly",
            "ru": "Модель повторно выдала некорректные вызовы инструментов",
            "uz": "Model takroran noto'g'ri vosita chaqiruvlarini yaratdi",
        },
    },
    4004: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Task not found",
            "ru": "Задача не найдена",
            "uz": "Vazifa topilmadi",
        },
    },
}
