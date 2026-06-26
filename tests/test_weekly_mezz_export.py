from openpyxl import Workbook

from weekly_mezz.export import COLUMN_SPECS, _write_report_sheet, build_export_row, export_reports


def test_weekly_mezz_export_uses_requested_columns_and_formats():
    row = build_export_row(
        {
            "rcept_no": "20260115000001",
            "report_nm": "[정정] 전환사채권발행결정",
            "corp_name": "발행사",
            "corp_cls": "K",
            "stock_code": "123456",
        },
        {
            "납입일": "2026-01-20",
            "만기일": "2029-01-20",
            "종류": "CB",
            "대상주식": "교환대상 보통주",
            "발행금액": 100.0,
            "행사가액": 5000,
            "할증관련텍스트": "기준주가의 110%로 산정",
            "표면이율": "0%",
            "만기이율": "2.5%",
            "리픽싱(%)": "70%",
            "리픽싱사유": "시가하락",
            "발행대상자": [["(주)투자자A", 100000000000], ["주식회사 투자자B", 25000000000]],
        },
    )

    workbook = Workbook()
    sheet = workbook.active
    _write_report_sheet(sheet, [row])

    assert [spec["header"] for spec in COLUMN_SPECS] == [
        "헤더",
        "최초공시일",
        "공시일",
        "납입일",
        "발행사 기업명",
        "상장시장",
        "교환대상 기업명",
        "종류",
        "벤처여부",
        "시가총액",
        "발행금액",
        "행사가액",
        "할증률",
        "만기",
        "PUT",
        "표면이자율",
        "만기이자율",
        "CALL",
        "Refixing",
        "리픽싱사유",
        "투자자",
        "섹터",
        "당사검토",
        "주관",
        "URL",
    ]
    assert sheet.max_column == 25
    assert sheet.freeze_panes == "A2"
    assert sheet["B2"].value == "26-01-15"
    assert sheet["C2"].value == "26-01-15"
    assert sheet["D2"].value == "26-01-20"
    assert sheet["F2"].value == "코스닥"
    assert sheet["N2"].value == "3.0년"
    assert sheet["O2"].value == "/ "
    assert sheet["P2"].value == "0.0%"
    assert sheet["Q2"].value == "/ 2.5%"
    assert sheet["S2"].value == "70.0%"
    assert sheet["T2"].value == "시가하락"
    assert sheet["U2"].value == "(주)투자자A 1,000, 주식회사 투자자B 250"
    assert sheet["Y2"].value == "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260115000001"
    assert sheet["Y2"].hyperlink.target == "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260115000001"
    assert sheet["Y2"].style == "Hyperlink"
    assert sheet["I2"].value == "-"
    assert sheet["R2"].value == "-"
    assert sheet["V2"].value == "-"
    assert sheet["W2"].value == "-"
    assert sheet["X2"].value == "-"
    assert sheet["E2"].alignment.horizontal == "left"
    assert sheet["E2"].alignment.indent == 1
    assert sheet["K2"].alignment.horizontal == "right"
    assert sheet["K2"].alignment.indent == 1
    assert sheet["N2"].alignment.indent == 0
    assert sheet["O2"].alignment.indent == 0
    assert sheet["P2"].alignment.indent == 0
    assert sheet["Q2"].alignment.indent == 0


def test_weekly_mezz_export_prefers_full_decision_method_for_premium_text():
    row = build_export_row(
        {"rcept_no": "20260115000001", "report_nm": "전환사채권발행결정"},
        {
            "납입일": "2026-01-20",
            "만기일": "2029-01-20",
            "전환가액 결정방법": "가중산술평균주가를 기준으로 긴 산식 전체를 보존하고 기준주가의 110%로 산정한다",
            "할증관련텍스트": "기준주가의 110%",
        },
    )

    assert row["premium_text"] == "가중산술평균주가를 기준으로 긴 산식 전체를 보존하고 기준주가의 110%로 산정한다"


def test_weekly_mezz_export_adds_real_parties_for_trustee_investor_names():
    row = build_export_row(
        {"rcept_no": "20260115000001", "report_nm": "전환사채권발행결정"},
        {
            "발행대상자": [["한국투자증권 주식회사(수탁자)", 10000000000]],
            "발행대상자세부엔티티": [
                ["한국투자증권 주식회사(수탁자)", "엔에이치투자파트너스 주식회사", "주식회사 실제투자자"]
            ],
        },
    )

    assert row["investors_text"] == "한국투자증권 주식회사(수탁자)(엔에이치투자파트너스 주식회사, 주식회사 실제투자자) 100"


def test_weekly_mezz_export_saves_only_excel(tmp_path):
    output_path = tmp_path / "weekly_mezz.xlsx"

    result = export_reports({"list": [], "total_count": 0}, output_path)

    assert result.output_path == output_path
    assert result.raw_path is None
    assert result.audit_path is None
    assert output_path.exists()
    assert not output_path.with_name("weekly_mezz_raw.json").exists()
