"""Strict schemas for `Present` props, one model per kind, with size caps."""

import math
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

from backend.cognition.services.widgets.sanitize import clean

KINDS = (
    "table",
    "chart",
    "stats",
    "steps",
    "checklist",
    "cards",
    "callout",
    "tabs",
    "accordion",
    "choices",
)
MAX_JSON_CHARS = 40_000
# One correct example per kind, appended to validation errors so the model can fix it.
EXAMPLES = {
    "table": '{"columns": ["Name", "Value"], "rows": [["a", "1"], ["b", "2"]]} (columns are plain strings, cells max 200 chars)',
    "chart": '{"type": "bar", "labels": ["A", "B"], "series": [{"name": "S", "values": [1, 2]}]}',
    "stats": '{"items": [{"label": "Users", "value": "12"}]}',
    "steps": '{"items": [{"label": "Do it", "status": "done"}]}',
    "checklist": '{"items": [{"label": "Task", "checked": false}]}',
    "cards": '{"items": [{"title": "T", "body": "text"}]}',
    "callout": '{"tone": "info", "text": "note"}',
    "tabs": '{"tabs": [{"label": "A", "text": "..."}]}',
    "accordion": '{"items": [{"title": "T", "text": "..."}]}',
    "choices": '{"options": ["yes", "no"]}',
}


def text(max_len: int) -> Any:
    """A plain-text string capped at `max_len` characters."""
    return Annotated[StrictStr, AfterValidator(lambda v: clean(v, max_len))]


def _finite(value: float) -> float:
    if not math.isfinite(value):
        msg = "numbers must be finite"
        raise ValueError(msg)
    return value


Num = Annotated[StrictInt | StrictFloat, AfterValidator(_finite)]
Cell = text(200) | Num | StrictBool | None


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class Table(Strict):
    columns: list[text(60)] = Field(min_length=1, max_length=12)
    rows: list[list[Cell]] = Field(min_length=1, max_length=100)
    caption: text(200) | None = None

    @model_validator(mode="before")
    @classmethod
    def _flat_columns(cls, data: Any) -> Any:
        """Models often send columns as [["A"],["B"]]; read that as ["A","B"]."""
        cols = data.get("columns") if isinstance(data, dict) else None
        if (
            isinstance(cols, list)
            and cols
            and all(isinstance(c, list) and len(c) == 1 for c in cols)
        ):
            return {**data, "columns": [c[0] for c in cols]}
        return data

    @model_validator(mode="after")
    def _rectangular(self) -> "Table":
        for i, row in enumerate(self.rows):
            if len(row) != len(self.columns):
                msg = f"row {i} has {len(row)} cells but there are {len(self.columns)} columns"
                raise ValueError(msg)
        return self


class Series(Strict):
    name: text(40)
    values: list[Num] = Field(min_length=1, max_length=40)


class Chart(Strict):
    type: Literal["bar", "line", "area", "pie"]
    labels: list[text(40)] = Field(min_length=1, max_length=40)
    series: list[Series] = Field(min_length=1, max_length=6)
    unit: text(20) | None = None

    @model_validator(mode="after")
    def _aligned(self) -> "Chart":
        for s in self.series:
            if len(s.values) != len(self.labels):
                msg = f"series '{s.name}' needs {len(self.labels)} values, got {len(s.values)}"
                raise ValueError(msg)
        if self.type == "pie":
            if len(self.series) != 1:
                msg = "a pie chart takes exactly one series"
                raise ValueError(msg)
            if any(v < 0 for v in self.series[0].values):
                msg = "pie values cannot be negative"
                raise ValueError(msg)
        return self


class StatItem(Strict):
    label: text(40)
    value: text(30) | Num
    delta: text(20) | None = None
    trend: Literal["up", "down", "flat"] | None = None


class Stats(Strict):
    items: list[StatItem] = Field(min_length=1, max_length=8)


class StepItem(Strict):
    label: text(120)
    status: Literal["done", "active", "todo"]
    detail: text(300) | None = None


class Steps(Strict):
    items: list[StepItem] = Field(min_length=1, max_length=20)


class CheckItem(Strict):
    label: text(200)
    checked: StrictBool = False


class Checklist(Strict):
    items: list[CheckItem] = Field(min_length=1, max_length=30)


class CardField(Strict):
    label: text(40)
    value: text(120)


class Card(Strict):
    title: text(80)
    subtitle: text(120) | None = None
    body: text(600) | None = None
    tags: list[text(24)] = Field(default_factory=list, max_length=6)
    fields: list[CardField] = Field(default_factory=list, max_length=8)


class Cards(Strict):
    items: list[Card] = Field(min_length=1, max_length=8)


class Callout(Strict):
    tone: Literal["info", "success", "warning", "error"]
    text: text(1000)


class Tab(Strict):
    label: text(30)
    text: text(2000)


class Tabs(Strict):
    tabs: list[Tab] = Field(min_length=1, max_length=8)


class AccordionItem(Strict):
    title: text(80)
    text: text(1500)


class Accordion(Strict):
    items: list[AccordionItem] = Field(min_length=1, max_length=12)


class Choices(Strict):
    options: list[text(80)] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def _unique(self) -> "Choices":
        if len({o.casefold() for o in self.options}) != len(self.options):
            msg = "options must be unique"
            raise ValueError(msg)
        if any(not o for o in self.options):
            msg = "options cannot be empty"
            raise ValueError(msg)
        return self


MODELS: dict[str, type[Strict]] = {
    "table": Table,
    "chart": Chart,
    "stats": Stats,
    "steps": Steps,
    "checklist": Checklist,
    "cards": Cards,
    "callout": Callout,
    "tabs": Tabs,
    "accordion": Accordion,
    "choices": Choices,
}


def explain(exc: ValidationError) -> str:
    """Short, model-readable list of what is wrong (first few problems)."""
    parts = []
    for err in exc.errors()[:5]:
        where = ".".join(str(p) for p in err["loc"])
        parts.append(f"{where or 'props'}: {err['msg']}")
    return "; ".join(parts)
