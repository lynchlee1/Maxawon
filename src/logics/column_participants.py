"""Participant and investor extraction.

Output columns:
- 발행대상
- 검산
- 투자자별투자액

Stability:
- medium: relies on last valid participant table and header matching
"""

from participant_parser import extract_investor_rows, list_fund_participants


def populate_participant_fields(result_dict, tables):
    try:
        result_dict["발행대상"], result_dict["검산"] = list_fund_participants(tables)
    except Exception:
        result_dict["발행대상"], result_dict["검산"] = "-", 0.0

    investor_rows = extract_investor_rows(tables)
    if investor_rows:
        result_dict["투자자별투자액"] = investor_rows
