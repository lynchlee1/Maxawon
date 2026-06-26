from weekly_mezz.export import build_export_row
from weekly_mezz.kind import parse_viewer_stock_code


def test_kind_viewer_header_preserves_leading_zero_stock_code():
    assert parse_viewer_stock_code('<h1 class="ttl type-99 fleft">Samsung Electronics (005930)</h1>') == "005930"


def test_kind_viewer_header_reads_six_digit_stock_code_without_guessing():
    assert parse_viewer_stock_code('<h1 class="ttl type-99 fleft">HEM Pharma (376270)</h1>') == "376270"


def test_export_formats_issuer_stock_code_and_market_cap():
    row = build_export_row(
        {
            "rcept_no": "20260115000001",
            "report_nm": "convertible bond issue",
            "corp_name": "Samsung Electronics",
            "corp_cls": "Y",
            "stock_code": "005930",
        },
        {},
        market_cap_map={"005930": 5_000_000},
    )

    assert row["issuer_stock_code"] == "A005930"
    assert row["market_cap_eok"] == 5_000_000


def test_matches_mezzanine_title_filters_subsidiary():
    from weekly_mezz.kind import _matches_mezzanine_title
    
    assert _matches_mezzanine_title({"report_nm": "전환사채권발행결정"}) is True
    assert _matches_mezzanine_title({"report_nm": "자회사의 주요경영사항(전환사채권발행결정)"}) is False
    assert _matches_mezzanine_title({"report_nm": "자회사의주요경영사항(전환사채권발행결정)"}) is False
    assert _matches_mezzanine_title({"report_nm": "자회사의  주요경영사항 (전환사채권발행결정)"}) is False


def test_market_to_corp_cls_custom_labels():
    from weekly_mezz.kind import _market_to_corp_cls
    
    assert _market_to_corp_cls("유") == "Y"
    assert _market_to_corp_cls("코") == "K"
    assert _market_to_corp_cls("유가") == "Y"
    assert _market_to_corp_cls("코스닥") == "K"
    assert _market_to_corp_cls("코넥스") == "N"
