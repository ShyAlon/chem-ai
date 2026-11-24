import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .normalization import words

MATERIALS_PATH = Path(__file__).parent / "data" / "materials.json"


class MaterialLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")
    en: str = Field(min_length=1, max_length=100)
    he: str = Field(min_length=1, max_length=100)


class MaterialDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    labels: MaterialLabels
    aliases: list[str] = Field(min_length=1, max_length=50)
    parents: list[str] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)


class MaterialCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    materials: list[MaterialDefinition] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_terms(self):
        ids = set()
        owners = {}
        for material in self.materials:
            if not material.labels.en.strip() or not material.labels.he.strip():
                raise ValueError("Material labels must contain text")
            if material.id in ids:
                raise ValueError(f"Duplicate material ID: {material.id}")
            ids.add(material.id)
            for alias in material.aliases:
                normalized = tuple(words(alias))
                if not normalized or len(alias) > 100 or not alias.isascii():
                    raise ValueError("Aliases must be English phrases of 1–100 characters")
                if normalized in owners and owners[normalized] != material.id:
                    raise ValueError(f"Alias collision: {alias}")
                owners[normalized] = material.id
        by_id = {item.id: item for item in self.materials}
        for material in self.materials:
            if len(set(material.parents)) != len(material.parents) or any(parent not in by_id for parent in material.parents):
                raise ValueError("Material parents must be unique existing IDs")
            pending, visited = list(material.parents), set()
            while pending:
                parent = pending.pop()
                if parent == material.id:
                    raise ValueError("Material hierarchy must not contain cycles")
                if parent not in visited:
                    visited.add(parent)
                    pending.extend(by_id[parent].parents)
        return self


def load_materials() -> MaterialCatalog:
    return MaterialCatalog(materials=json.loads(MATERIALS_PATH.read_text()))


def validate_material_references(catalog: MaterialCatalog, required_ids: set[str]) -> MaterialCatalog:
    if not required_ids <= {item.id for item in catalog.materials}:
        raise ValueError("Materials referenced by reviewed procedures must remain")
    return catalog
