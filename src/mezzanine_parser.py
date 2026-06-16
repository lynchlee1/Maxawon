from bs4 import XMLParsedAsHTMLWarning
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from logics.column_basic_terms import (
    infer_security_type,
    populate_issue_date_from_document_text_if_missing,
    extract_target_table_fields,
    populate_maturity_term,
)
from logics.column_option_schedule import (
    resolve_schedule_dates,
    populate_text_only_option_fields,
    populate_option_schedule_fields,
    populate_option_presence_status_fields,
)
from logics.column_option_sections import (
    find_option_sections,
    populate_option_section_metadata,
)
from logics.column_participants import populate_participant_fields
from logics.column_premium import extract_premium_rate, extract_premium_source_text, populate_premium_fields
from logics.column_refixing import (
    populate_initial_refixing_fields,
    populate_refixing_from_text_if_missing,
)
from logics.document_context import (
    collect_body_tables,
    combine_document_text,
    filter_out_correction_tables,
    find_main_security_table,
)


# Backward-compatible helper names used by tests and scripts.
_combine_document_text = combine_document_text
_extract_premium_rate = extract_premium_rate
_resolve_schedule_dates = resolve_schedule_dates


def extract_table_data(report: dict, tables: list, soups: list | None = None) -> dict:
    result_dict = {}
    report_nm = report.get("report_nm", "")
    result_dict["종류"] = infer_security_type(report_nm)

    preferred_tables = collect_body_tables(soups) if soups else []
    tables = preferred_tables or filter_out_correction_tables(tables)
    document_text = combine_document_text(soups)
    option_sections = find_option_sections(document_text)
    premium_source_text = extract_premium_source_text(document_text)

    populate_option_section_metadata(result_dict, option_sections, document_text)
    populate_premium_fields(result_dict, premium_source_text)
    populate_issue_date_from_document_text_if_missing(result_dict, document_text)

    target_table = find_main_security_table(tables)
    if target_table is None:
        populate_text_only_option_fields(result_dict, option_sections)
        populate_option_presence_status_fields(result_dict, tables, option_sections, document_text)
        return result_dict

    extract_target_table_fields(target_table, result_dict)
    populate_maturity_term(result_dict)
    populate_initial_refixing_fields(result_dict)
    populate_participant_fields(result_dict, tables)
    populate_refixing_from_text_if_missing(result_dict, document_text)

    decision_text = " ".join(result_dict.get("전환가액 결정방법", [])) or premium_source_text
    populate_premium_fields(result_dict, decision_text)
    populate_issue_date_from_document_text_if_missing(result_dict, document_text)
    populate_option_schedule_fields(result_dict, tables, option_sections)
    populate_option_presence_status_fields(result_dict, tables, option_sections, document_text)

    return result_dict
