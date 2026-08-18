import csv
from pathlib import Path


def append_row(path, fields, row):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if p.exists() and p.stat().st_size > 0:
        with p.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing = list(reader)
            old_fields = reader.fieldnames or []
        if old_fields != fields:
            with p.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                for old in existing:
                    writer.writerow({k: old.get(k, "") for k in fields})
    exists = p.exists() and p.stat().st_size > 0
    with p.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fields})
