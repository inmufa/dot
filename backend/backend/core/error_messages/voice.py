"""4130-4139: voice (speech-to-text, text-to-speech) proxy."""

from typing import Any


def _entry(status: int, en: str, ru: str, uz: str) -> dict[str, Any]:
    return {"status": status, "show": True, "messages": {"en": en, "ru": ru, "uz": uz}}


CATALOG: dict[int, dict[str, Any]] = {
    4130: _entry(
        503,
        "Voice is not running (set DOT_VOICE=on and run: make up-voice)",
        "Голос не запущен (задайте DOT_VOICE=on и выполните: make up-voice)",
        "Ovoz ishlamayapti (DOT_VOICE=on qiling va bajaring: make up-voice)",
    ),
    4131: _entry(
        413,
        "Audio is too large",
        "Аудио слишком большое",
        "Audio juda katta",
    ),
    4132: _entry(
        413,
        "Audio is too long",
        "Аудио слишком длинное",
        "Audio juda uzun",
    ),
    4133: _entry(
        415,
        "Unsupported audio (need 16 kHz mono 16-bit WAV)",
        "Неподдерживаемое аудио (нужен WAV 16 кГц, моно, 16 бит)",
        "Audio qo'llab-quvvatlanmaydi (16 kHz mono 16-bit WAV kerak)",
    ),
    4134: _entry(
        422,
        "Nothing to read aloud, or the text is too long",
        "Нечего озвучивать, или текст слишком длинный",
        "O'qib berish uchun matn yo'q yoki matn juda uzun",
    ),
    4135: _entry(
        502,
        "Voice service failed",
        "Голосовой сервис не справился",
        "Ovoz xizmati xatolik berdi",
    ),
    4136: _entry(
        422,
        "Unknown voice",
        "Неизвестный голос",
        "Noma'lum ovoz",
    ),
}
