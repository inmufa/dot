"""3000-3999: permissions, classifier, approvals, read-before-edit."""

from typing import Any

CATALOG: dict[int, dict[str, Any]] = {
    3000: {
        "status": 403,
        "show": True,
        "messages": {
            "en": "Denied by permission rule",
            "ru": "Запрещено правилом доступа",
            "uz": "Ruxsat qoidasi bilan taqiqlangan",
        },
    },
    3001: {
        "status": 408,
        "show": True,
        "messages": {
            "en": "Approval timed out",
            "ru": "Время подтверждения истекло",
            "uz": "Tasdiqlash vaqti tugadi",
        },
    },
    3002: {
        "status": 409,
        "show": True,
        "messages": {
            "en": "File must be read with Read before editing",
            "ru": "Перед правкой файл нужно прочитать через Read",
            "uz": "Tahrirlashdan oldin faylni Read bilan o'qish kerak",
        },
    },
    3003: {
        "status": 404,
        "show": True,
        "messages": {
            "en": "Approval not found or already resolved",
            "ru": "Подтверждение не найдено или уже обработано",
            "uz": "Tasdiq topilmadi yoki allaqachon hal qilingan",
        },
    },
    3004: {
        "status": 500,
        "show": True,
        "messages": {
            "en": "Could not restore a file during rewind",
            "ru": "Не удалось восстановить файл при откате",
            "uz": "Qaytarishda faylni tiklab bo'lmadi",
        },
    },
    3005: {
        "status": 400,
        "show": True,
        "messages": {
            "en": "Settings file is invalid",
            "ru": "Файл настроек некорректен",
            "uz": "Sozlamalar fayli noto'g'ri",
        },
    },
    3006: {
        "status": 403,
        "show": True,
        "messages": {
            "en": "Prompt blocked by a hook",
            "ru": "Запрос заблокирован хуком",
            "uz": "So'rov hook tomonidan bloklandi",
        },
    },
    3007: {
        "status": 500,
        "show": True,
        "messages": {
            "en": "Could not create a checkpoint before the edit",
            "ru": "Не удалось создать контрольную точку перед правкой",
            "uz": "Tahrirdan oldin nazorat nuqtasini yaratib bo'lmadi",
        },
    },
}
