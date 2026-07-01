"""
Просмотр и экспорт структурированных логов domik-posting.

Примеры:
  py -3 scripts/view_logs.py                         # последние 50 событий
  py -3 scripts/view_logs.py --tail 100
  py -3 scripts/view_logs.py --event publish
  py -3 scripts/view_logs.py --event login_ok login_fail
  py -3 scripts/view_logs.py --since 2026-07-01
  py -3 scripts/view_logs.py --export events.csv
  py -3 scripts/view_logs.py --all --event gigachat_call --export giga.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path

LOG_FILE = Path("logs/app.jsonl")


def read_events(event_filter=None, since=None):
    if not LOG_FILE.exists():
        print(f"Файл логов не найден: {LOG_FILE}", file=sys.stderr)
        return []
    events = []
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event_filter and rec.get("event") not in event_filter:
                continue
            if since and rec.get("ts", "") < since:
                continue
            events.append(rec)
    return events


def fmt_event(rec):
    rec = dict(rec)
    ts = rec.pop("ts", "?")
    event = rec.pop("event", "?")
    parts = []
    for k, v in rec.items():
        if v is None:
            continue
        if isinstance(v, list):
            v = ",".join(str(x) for x in v)
        parts.append(f"{k}={v}")
    return f"{ts}  {event:<22}  {' '.join(parts)}"


def main():
    parser = argparse.ArgumentParser(description="Просмотр логов domik-posting")
    parser.add_argument("--tail", type=int, default=50, metavar="N",
                        help="Последние N событий (по умолчанию 50)")
    parser.add_argument("--event", nargs="+", metavar="TYPE",
                        help="Фильтр по типу события (можно несколько)")
    parser.add_argument("--since", metavar="YYYY-MM-DD",
                        help="События не раньше этой даты")
    parser.add_argument("--export", metavar="FILE",
                        help="Экспорт в CSV-файл")
    parser.add_argument("--all", action="store_true",
                        help="Все события без ограничения --tail")
    args = parser.parse_args()

    since = (args.since + "T00:00:00Z") if args.since else None
    events = read_events(event_filter=args.event, since=since)

    if not args.all:
        events = events[-args.tail:]

    if not events:
        print("Событий не найдено.")
        return

    if args.export:
        # Собираем все уникальные ключи в порядке появления
        all_keys: list[str] = []
        seen: set[str] = set()
        for e in events:
            for k in e:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)
        with open(args.export, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            writer.writeheader()
            for e in events:
                row = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v)
                       for k, v in e.items()}
                writer.writerow(row)
        print(f"Экспортировано {len(events)} событий → {args.export}")
        return

    for e in events:
        print(fmt_event(e))

    print(f"\n  Итого: {len(events)} событий")


if __name__ == "__main__":
    main()
