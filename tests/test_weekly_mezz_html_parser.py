from weekly_mezz.html_bond_parser import parse_bond_issuance_html


def test_html_parser_preserves_stable_basic_and_refixing_keys(tmp_path):
    html = """
    <html>
      <head><title>전환사채권발행결정</title></head>
      <body>
        <h1>전환사채권발행결정</h1>
        <table>
          <tr><th>사채의 종류</th><td>회차</td><td>1</td><td>전환사채</td></tr>
          <tr><th>사채의 권면(전자등록)총액</th><td>10,000,000,000</td></tr>
          <tr><th>자금조달의 목적</th><td>운영자금</td><td>10,000,000,000</td></tr>
          <tr><th>표면이자율</th><td>0.0</td></tr>
          <tr><th>만기이자율</th><td>2.0</td></tr>
          <tr><th>사채만기일</th><td>2029년 01월 01일</td></tr>
          <tr><th>전환가액 (원/주)</th><td>5,000</td></tr>
          <tr><th>납입일</th><td>2026년 01월 01일</td></tr>
          <tr><th>시가하락에 따른 전환가액 조정</th><td>3,500</td></tr>
          <tr><th>전환가액 조정에 관한 사항</th><td>매 3개월마다 전환가액의 70% 이상으로 한다</td></tr>
        </table>
      </body>
    </html>
    """
    html_path = tmp_path / "report.html"
    html_path.write_text(html, encoding="utf-8")

    parsed = parse_bond_issuance_html(
        html,
        file_path=html_path,
        report={"report_nm": "전환사채권발행결정", "rcept_no": "20260101000001"},
    )

    assert parsed["발행금액"] == 100.0
    assert parsed["발행금액(억)"] == 100.0
    assert parsed["행사가액"] == 5000
    assert parsed["전환가액(원)"] == 5000
    assert parsed["리픽싱(원)"] == 3500
    assert parsed["리픽싱(%)"] in {"70%", "70.0%"}
    assert parsed["리픽싱가격"] in {"70%", "70.0%"}
    assert parsed["리픽싱주가"] == 3
