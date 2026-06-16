import argparse
from calendar import monthrange
from datetime import date, datetime, timedelta

from pathlib import Path

from weekly_mezz.kind import fetch_mezzanine_reports
from weekly_mezz.export import default_output_path, export_reports
from weekly_mezz.settings import get_api_key


def parse_yyyymmdd(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def format_yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def default_date_range(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    days_since_monday = today.weekday() if today.weekday() != 0 else 7
    recent_monday = today - timedelta(days=days_since_monday)
    return recent_monday, today


def validate_period(start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")
    if end_date >= add_months(start_date, 3):
        raise ValueError("조회 기간은 3개월 미만이어야 합니다.")


def collect_and_export(
    start_date: date,
    end_date: date,
    output_path,
    audit_json_path=None,
    api_key: str | None = None,
    last_reprt_at: str = "N",
    progress_callback=None,
):
    validate_period(start_date, end_date)
    api_key = api_key or get_api_key()
    output_parent = Path(output_path).expanduser().resolve().parent
    data = fetch_mezzanine_reports(
        start_date,
        end_date,
        output_dir=output_parent / "kind_downloads",
        progress_callback=progress_callback,
        last_reprt_at=last_reprt_at,
    )
    return export_reports(
        data,
        output_path,
        audit_json_path=audit_json_path,
        api_key=api_key,
        progress_callback=progress_callback,
    )


def build_parser() -> argparse.ArgumentParser:
    default_start, default_end = default_date_range()
    parser = argparse.ArgumentParser(prog="weekly-mezz")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--from", dest="from_date", default=format_yyyymmdd(default_start))
    collect_parser.add_argument("--to", dest="to_date", default=format_yyyymmdd(default_end))
    collect_parser.add_argument("--output", default=str(default_output_path()))
    collect_parser.add_argument("--audit-json", default="")
    collect_parser.add_argument("--last-reprt-at", default="N", choices=("Y", "N"))
    collect_parser.add_argument("--api-key", default="", help="OpenDART corpCode.xml API key for target-stock mapping")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "collect":
        result = collect_and_export(
            parse_yyyymmdd(args.from_date),
            parse_yyyymmdd(args.to_date),
            args.output,
            audit_json_path=args.audit_json or None,
            api_key=args.api_key or None,
            last_reprt_at=args.last_reprt_at,
            progress_callback=print,
        )
        print(f"Saved XLSX: {result.output_path}")
        if result.audit_path:
            print(f"Saved audit JSON: {result.audit_path}")
        print(f"Saved raw JSON: {result.raw_path}")
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

