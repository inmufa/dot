"""`Ask` form fields: schema validation and validation of the user's values."""

import json
import math
import re
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    ValidationError,
    model_validator,
)

from backend.cognition.services.widgets.models import Num, text
from backend.cognition.services.widgets.sanitize import clean, soft_clean

FieldType = Literal[
    "single_select",
    "multi_select",
    "text",
    "number",
    "slider",
    "toggle",
    "date",
    "rank",
]
OPTION_TYPES = ("single_select", "multi_select", "rank")
MAX_FIELDS = 8
MAX_TEXT_ANSWER = 2000
MAX_VALUES_JSON = 20_000
_ID = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FormField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[StrictStr, Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
    type: FieldType
    label: text(120)
    options: list[text(80)] | None = Field(default=None, min_length=2, max_length=12)
    required: StrictBool = True
    default: str | list[str] | Num | StrictBool | None = None
    min: Num | None = None
    max: Num | None = None
    step: Num | None = Field(default=None, gt=0)
    placeholder: text(80) | None = None
    multiline: StrictBool = False

    @model_validator(mode="after")
    def _consistent(self) -> "FormField":
        opts = self.options
        if self.type in OPTION_TYPES:
            if not opts:
                msg = f"field '{self.id}' ({self.type}) needs options (2-12)"
                raise ValueError(msg)
            if len({o.casefold() for o in opts}) != len(opts) or "" in opts:
                msg = f"field '{self.id}': options must be unique and not empty"
                raise ValueError(msg)
        elif opts is not None:
            msg = f"field '{self.id}' ({self.type}) takes no options"
            raise ValueError(msg)
        if self.type == "slider" and (self.min is None or self.max is None):
            msg = f"slider '{self.id}' needs min and max"
            raise ValueError(msg)
        if self.min is not None and self.max is not None and self.min >= self.max:
            msg = f"field '{self.id}': min must be below max"
            raise ValueError(msg)
        if self.default is not None:
            self.default = _checked(self, self.default, is_default=True)
        return self


class Form(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: text(120) | None = None
    question: text(500) | None = None
    fields: list[FormField] = Field(min_length=1, max_length=MAX_FIELDS)

    @model_validator(mode="after")
    def _ids(self) -> "Form":
        ids = [f.id for f in self.fields]
        if len(set(ids)) != len(ids):
            msg = "field ids must be unique"
            raise ValueError(msg)
        return self


def parse_form(args: dict[str, Any]) -> Form:
    """Validate the `fields` shape of an Ask call (ValidationError on problems)."""
    keys = {k: args[k] for k in ("title", "question", "fields") if k in args}
    return Form.model_validate(keys)


class AnswerError(ValueError):
    """The submitted values do not fit the form."""


def _fail(field: FormField, why: str) -> None:
    msg = f"'{field.id}': {why}"
    raise AnswerError(msg)


def _checked(field: FormField, value: Any, *, is_default: bool = False) -> Any:  # noqa: C901, PLR0911, PLR0912
    t = field.type
    if t == "toggle":
        if not isinstance(value, bool):
            _fail(field, "must be true or false")
        return value
    if t in ("number", "slider"):
        if isinstance(value, bool) or not isinstance(value, int | float):
            _fail(field, "must be a number")
        if not math.isfinite(value):
            _fail(field, "must be finite")
        if field.min is not None and value < field.min:
            _fail(field, f"must be at least {field.min}")
        if field.max is not None and value > field.max:
            _fail(field, f"must be at most {field.max}")
        return value
    if t == "date":
        if not isinstance(value, str) or not _DATE.match(value):
            _fail(field, "must be a date YYYY-MM-DD")
        try:
            date.fromisoformat(value)
        except ValueError:
            _fail(field, "is not a real date")
        return value
    if t == "text":
        if not isinstance(value, str):
            _fail(field, "must be text")
        if is_default:
            return clean(value, MAX_TEXT_ANSWER)
        return soft_clean(value, MAX_TEXT_ANSWER)
    opts = field.options or []
    if t == "single_select":
        if not isinstance(value, str) or value not in opts:
            _fail(field, f"must be one of {opts}")
        return value
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        _fail(field, "must be a list of options")
    if len(set(value)) != len(value) or any(v not in opts for v in value):
        _fail(field, f"must be unique items from {opts}")
    if t == "rank" and sorted(value) != sorted(opts):
        _fail(field, "must list every option exactly once, in order")
    return value


def validate_answers(fields: list[dict[str, Any]], values: dict[str, Any]) -> dict:
    """Check the user's `values` against the stored field specs; returns clean values."""
    if len(json.dumps(values, default=str)) > MAX_VALUES_JSON:
        msg = "answer is too large"
        raise AnswerError(msg)
    parsed = [FormField.model_validate(f) for f in fields]
    unknown = set(values) - {f.id for f in parsed}
    if unknown:
        msg = f"unknown field(s): {sorted(unknown)[:3]}"
        raise AnswerError(msg)
    out: dict[str, Any] = {}
    for f in parsed:
        if f.id not in values or values[f.id] in (None, "", []):
            if f.required and f.type not in ("toggle", "multi_select"):
                _fail(f, "is required")
            out[f.id] = {"toggle": False, "multi_select": []}.get(f.type)
            continue
        out[f.id] = _checked(f, values[f.id])
    return out


def describe(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5]
    )


__all__ = ["AnswerError", "Form", "FormField", "parse_form", "validate_answers"]
