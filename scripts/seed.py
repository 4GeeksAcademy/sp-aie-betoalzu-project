#!/usr/bin/env python3
"""Seed suppliers data from supliers.md into TinyDB."""

from __future__ import annotations

import ast
from pathlib import Path

from tinydb import Query, TinyDB


ROOT_DIR = Path(__file__).resolve().parents[1]
SUPPLIERS_MD_PATH = ROOT_DIR / "supliers.md"
DB_PATH = ROOT_DIR / "scripts" / "suppliers_db.json"


def extract_seed_data(md_path: Path) -> list[dict]:
    if not md_path.exists() or not md_path.is_file():
        raise FileNotFoundError(f"No se encontro el archivo: {md_path}")

    content = md_path.read_text(encoding="utf-8")
    marker = "SUPPLIERS_SEED"
    marker_index = content.find(marker)
    if marker_index == -1:
        raise ValueError("No se encontro el bloque SUPPLIERS_SEED en supliers.md")

    list_start = content.find("[", marker_index)
    if list_start == -1:
        raise ValueError("SUPPLIERS_SEED no contiene una lista valida")

    depth = 0
    list_end = -1
    in_string = False
    string_char = ""
    escaped = False

    for i in range(list_start, len(content)):
        char = content[i]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == string_char:
                in_string = False
            continue

        if char in {"\"", "'"}:
            in_string = True
            string_char = char
            continue

        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                list_end = i
                break

    if list_end == -1:
        raise ValueError("No se pudo cerrar la lista SUPPLIERS_SEED")

    raw_list = content[list_start : list_end + 1]
    try:
        data = ast.literal_eval(raw_list)
    except (ValueError, SyntaxError) as exc:
        raise ValueError("El bloque SUPPLIERS_SEED no tiene formato valido") from exc

    if not isinstance(data, list):
        raise ValueError("SUPPLIERS_SEED debe ser una lista de proveedores")

    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Cada proveedor en SUPPLIERS_SEED debe ser un objeto")

    return data


def seed_suppliers(data: list[dict], db_path: Path) -> dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = TinyDB(db_path)
    table = db.table("suppliers")
    supplier = Query()

    inserted = 0
    duplicates = 0

    for item in data:
        name = item.get("name")
        if not name:
            continue

        exists = table.contains(supplier.name == name)
        if exists:
            duplicates += 1
            continue

        table.insert(item)
        inserted += 1

    total = len(table)
    db.close()

    return {
        "inserted": inserted,
        "duplicates": duplicates,
        "total": total,
        "source": len(data),
    }


def main() -> int:
    try:
        data = extract_seed_data(SUPPLIERS_MD_PATH)
        stats = seed_suppliers(data, DB_PATH)
    except Exception as exc:
        print(f"Error durante el seed: {exc}")
        return 1

    print("Seed finalizado correctamente.")
    print(f"Registros leidos: {stats['source']}")
    print(f"Nuevos insertados: {stats['inserted']}")
    print(f"Duplicados omitidos: {stats['duplicates']}")
    print(f"Total en la base de datos: {stats['total']}")
    print(f"Base de datos TinyDB: {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())