"""Shared API presentation schemas rendered by generic client components."""

from typing import Literal

from pydantic import BaseModel, Field

type Language = Literal["en", "he"]
type Text = dict[Language, str]


class InputOption(BaseModel):
    id: str
    label: Text


class InputField(BaseModel):
    id: str
    label: Text
    kind: Literal["text", "number", "select"]
    required: bool = True
    minimum: float | None = None
    maximum: float | None = None
    max_length: int | None = None
    options: list[InputOption] = Field(default_factory=list)


class DisplayField(BaseModel):
    label: str
    value: str
