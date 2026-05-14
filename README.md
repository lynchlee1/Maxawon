# CretopDataReader

사용자가 Cretop에 직접 로그인한 뒤 엑셀 검색 대상을 처리하기 위한 GUI 도구입니다.

## 실행

```powershell
pip install -e .
python -m cretop_data_reader
```

Editable install 후에는 콘솔 명령으로도 실행할 수 있습니다.

```powershell
cretop-data-reader
```

## 현재 기능

- 일반 Chrome 창으로 Cretop 열기
- 사용자가 직접 로그인한 뒤 `로그인 완료` 버튼으로 진행 상태 표시
- `.xlsx`, `.xlsm`, `.csv` 검색 대상 파일 선택
- 선택한 파일의 앞부분 미리보기
- Scrapling 설치 여부 확인

엑셀 기반 검색 자동 처리와 중복 후보 선택 흐름은 아직 구현 전입니다. 향후 처리 로직은 Scrapling을 사용하되, 접근 통제나 크롤링 방지 우회 기능은 포함하지 않습니다.
