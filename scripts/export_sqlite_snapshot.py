#!/usr/bin/env python3
"""
Exporte un snapshot SQLite complet avant migration vers PostgreSQL.

Le script produit:
- un manifeste JSON avec le detail des tables exportees
- un dump des objets SQLite (tables, index, triggers, vues)
- un dossier `tables/` contenant un export CSV et/ou JSONL par table
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]


def default_data_dir() -> Path:
    mounted_data_dir = Path("/data")
    if mounted_data_dir.is_dir():
        return mounted_data_dir
    return ROOT_DIR / "data"


def default_database_path() -> str:
    return os.getenv("DATABASE_PATH", str(default_data_dir() / "cerveau.db"))


def parse_args() -> argparse.Namespace:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    default_output_dir = default_data_dir() / "exports" / f"sqlite_snapshot_{timestamp}"

    parser = argparse.ArgumentParser(
        description=(
            "Exporte toutes les tables SQLite dans un dossier versionnable "
            "ou archivable avant migration."
        )
    )
    parser.add_argument(
        "--database-path",
        default=default_database_path(),
        help="Chemin du fichier SQLite source.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output_dir),
        help="Dossier de sortie. Il doit etre inexistant ou vide.",
    )
    parser.add_argument(
        "--format",
        choices=("csv", "jsonl", "both"),
        default="both",
        help="Format d'export par table.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Nombre de lignes lues par lot pendant l'export.",
    )
    return parser.parse_args()


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def prepare_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise SystemExit(
                f"Le dossier de sortie {output_dir} existe deja et n'est pas vide."
            )
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "tables").mkdir(exist_ok=True)


def connect_read_only(database_path: Path) -> sqlite3.Connection:
    if not database_path.is_file():
        raise SystemExit(f"Base SQLite introuvable: {database_path}")

    connection = sqlite3.connect(
        f"file:{database_path.resolve()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def list_tables(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    )


def list_schema_objects(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
              AND sql IS NOT NULL
            ORDER BY
                CASE type
                    WHEN 'table' THEN 0
                    WHEN 'index' THEN 1
                    WHEN 'trigger' THEN 2
                    ELSE 3
                END,
                name
            """
        )
    )


def fetch_columns(connection: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    pragma = f"PRAGMA table_info({quote_identifier(table_name)})"
    rows = connection.execute(pragma).fetchall()
    return [
        {
            "cid": row["cid"],
            "name": row["name"],
            "type": row["type"],
            "notnull": bool(row["notnull"]),
            "default": row["dflt_value"],
            "primary_key": bool(row["pk"]),
        }
        for row in rows
    ]


def fetch_row_count(connection: sqlite3.Connection, table_name: str) -> int:
    query = f"SELECT COUNT(*) AS row_count FROM {quote_identifier(table_name)}"
    row = connection.execute(query).fetchone()
    return int(row["row_count"])


def serialize_json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"encoding": "hex", "value": value.hex()}
    return value


def serialize_csv_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.hex()
    return value


def export_table_csv(
    connection: sqlite3.Connection,
    table_name: str,
    column_names: list[str],
    output_path: Path,
    batch_size: int,
) -> None:
    select_sql = (
        f"SELECT {', '.join(quote_identifier(name) for name in column_names)} "
        f"FROM {quote_identifier(table_name)}"
    )
    cursor = connection.execute(select_sql)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(column_names)

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                writer.writerow(
                    [serialize_csv_value(row[column_name]) for column_name in column_names]
                )


def export_table_jsonl(
    connection: sqlite3.Connection,
    table_name: str,
    column_names: list[str],
    output_path: Path,
    batch_size: int,
) -> None:
    select_sql = (
        f"SELECT {', '.join(quote_identifier(name) for name in column_names)} "
        f"FROM {quote_identifier(table_name)}"
    )
    cursor = connection.execute(select_sql)

    with output_path.open("w", encoding="utf-8") as handle:
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                payload = {
                    column_name: serialize_json_value(row[column_name])
                    for column_name in column_names
                }
                handle.write(json.dumps(payload, ensure_ascii=True))
                handle.write("\n")


def write_schema_dump(schema_objects: list[sqlite3.Row], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as handle:
        for schema_object in schema_objects:
            handle.write(f"-- {schema_object['type']}: {schema_object['name']}\n")
            handle.write(schema_object["sql"])
            handle.write(";\n\n")


def build_manifest(
    database_path: Path,
    output_dir: Path,
    export_format: str,
    tables: list[dict[str, Any]],
    schema_objects: list[sqlite3.Row],
) -> dict[str, Any]:
    return {
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_path": str(database_path.resolve()),
        "sqlite_version": sqlite3.sqlite_version,
        "export_format": export_format,
        "output_dir": str(output_dir.resolve()),
        "table_count": len(tables),
        "schema_object_count": len(schema_objects),
        "tables": tables,
    }


def main() -> int:
    args = parse_args()
    database_path = Path(args.database_path).expanduser()
    output_dir = Path(args.output_dir).expanduser()

    if args.batch_size < 1:
        raise SystemExit("--batch-size doit etre >= 1")

    prepare_output_dir(output_dir)

    connection = connect_read_only(database_path)
    try:
        table_rows = list_tables(connection)
        schema_objects = list_schema_objects(connection)
        write_schema_dump(schema_objects, output_dir / "sqlite_master.sql")

        manifest_tables: list[dict[str, Any]] = []
        for table_row in table_rows:
            table_name = table_row["name"]
            columns = fetch_columns(connection, table_name)
            column_names = [column["name"] for column in columns]
            row_count = fetch_row_count(connection, table_name)

            exported_files: list[str] = []
            if args.format in {"csv", "both"}:
                csv_path = output_dir / "tables" / f"{table_name}.csv"
                export_table_csv(
                    connection=connection,
                    table_name=table_name,
                    column_names=column_names,
                    output_path=csv_path,
                    batch_size=args.batch_size,
                )
                exported_files.append(str(csv_path.relative_to(output_dir)))

            if args.format in {"jsonl", "both"}:
                jsonl_path = output_dir / "tables" / f"{table_name}.jsonl"
                export_table_jsonl(
                    connection=connection,
                    table_name=table_name,
                    column_names=column_names,
                    output_path=jsonl_path,
                    batch_size=args.batch_size,
                )
                exported_files.append(str(jsonl_path.relative_to(output_dir)))

            manifest_tables.append(
                {
                    "name": table_name,
                    "row_count": row_count,
                    "columns": columns,
                    "files": exported_files,
                }
            )

        manifest = build_manifest(
            database_path=database_path,
            output_dir=output_dir,
            export_format=args.format,
            tables=manifest_tables,
            schema_objects=schema_objects,
        )
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

        print(
            json.dumps(
                {
                    "status": "ok",
                    "tables": len(manifest_tables),
                    "output_dir": str(output_dir.resolve()),
                    "manifest": str(manifest_path.resolve()),
                },
                ensure_ascii=True,
            )
        )
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
