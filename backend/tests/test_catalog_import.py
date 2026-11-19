import json

import pytest

from homechem.catalog import MaterialCatalog, load_materials, validate_material_references
from homechem.catalog_import import write_catalog


def test_import_validation_preserves_referenced_materials():
    existing = load_materials()
    without_glass = MaterialCatalog(materials=[entry for entry in existing.materials if entry.id != "glass"])
    with pytest.raises(ValueError, match="referenced"):
        validate_material_references(without_glass, {"glass"})


def test_catalog_write_produces_valid_json_and_keeps_original_on_failure(tmp_path, monkeypatch):
    from homechem import catalog_import
    path = tmp_path / "catalog.json"
    write_catalog(path, [{"id": "glass"}])
    original = path.read_bytes()
    assert json.loads(original) == [{"id": "glass"}]
    def fail(*args):
        raise OSError("replacement failed")
    monkeypatch.setattr(catalog_import.os, "replace", fail)
    with pytest.raises(OSError):
        write_catalog(path, [{"id": "copper"}])
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]
