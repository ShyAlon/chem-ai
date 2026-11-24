"""Validated catalog imports shared by the Bash entry points."""

import argparse
import json
import os
from pathlib import Path
import tempfile

from .catalog import MATERIALS_PATH, MaterialCatalog, validate_material_references
from .definitions import DATA, PROCEDURE_DEFINITIONS, ProcedureCatalog


def write_catalog(path: Path, entries: list[dict]) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
            temporary = output.name
            json.dump(entries, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description="Validate and import a HomeChem catalog")
    parser.add_argument("kind", choices=("materials", "procedures"))
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        entries = json.loads(args.file.read_text())
        if args.kind == "materials":
            catalog = validate_material_references(
                MaterialCatalog(materials=entries), {entry.material for entry in PROCEDURE_DEFINITIONS if entry.material is not None},
            )
            validated = catalog.materials
            destination = MATERIALS_PATH
        else:
            validated = ProcedureCatalog(procedures=entries).procedures
            destination = DATA / "procedures.json"
        write_catalog(destination, [entry.model_dump() for entry in validated])
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Imported {len(validated)} {args.kind}. Restart the API to load the updated catalog.")


if __name__ == "__main__":
    main()
