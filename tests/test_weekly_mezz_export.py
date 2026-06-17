from openpyxl import Workbook

from weekly_mezz.export import COLUMN_SPECS, _write_report_sheet, build_export_row


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
            "발행대상자": [["투자자A", 10000000000]],
        },
    )

    workbook = Workbook()
    sheet = workbook.active
    _write_report_sheet(sheet, [row])

    assert [spec["header"] for spec in COLUMN_SPECS] == [
        "헤더",
        "공시일",
        "납입일",
        "발행사 기업명",
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
        "투자자",
        "섹터",
        "당사검토",
        "주관",
    ]
    assert sheet.max_column == 21
    assert sheet.freeze_panes == "A2"
    assert sheet["B2"].value == "26-01-15"
    assert sheet["C2"].value == "26-01-20"
    assert sheet["L2"].value == "3.0년"
    assert sheet["M2"].value == "/ "
    assert sheet["N2"].value == "0.0%"
    assert sheet["O2"].value == "/ 2.5%"
    assert sheet["Q2"].value == "70.0% 시가하락"
    assert sheet["D2"].alignment.horizontal == "left"
    assert sheet["D2"].alignment.indent == 1
    assert sheet["I2"].alignment.horizontal == "right"
    assert sheet["I2"].alignment.indent == 1
    assert sheet["L2"].alignment.indent == 0
    assert sheet["M2"].alignment.indent == 0
    assert sheet["N2"].alignment.indent == 0
    assert sheet["O2"].alignment.indent == 0
