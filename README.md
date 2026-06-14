# CretopDataReader

사용자가 Cretop에 직접 로그인한 뒤 엑셀 검색 대상을 처리하기 위한 GUI 도구입니다.

## 실행

### Electron 데스크탑 UI

```powershell
pip install -e .
npm install
npm run desktop
```

Electron UI는 최신 데스크탑 앱 구조로 구성된 기본 실행 경로입니다. 화면은 Electron renderer가 담당하고, Chrome 실행/파일 선택/조건검색 테이블 복사 같은 기존 Python 기능은 Electron main process에서 Python 모듈을 호출해 재사용합니다.

개발자 도구를 함께 열려면 다음 명령을 사용합니다.

```powershell
npm run desktop:dev
```

### 기존 Tkinter UI

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
- 사용자가 Cretop 조건검색을 직접 실행한 뒤 현재 화면의 결과 테이블을 페이지 단위로 CSV 저장
- `.xlsx`, `.xlsm`, `.csv` 검색 대상 파일 선택
- 선택한 파일의 앞부분 미리보기
- Scrapling 설치 여부 확인

## 조건검색 결과 복사

1. 앱의 `세션` 탭에서 Chrome을 엽니다.
2. 열린 Chrome에서 사용자가 직접 Cretop에 로그인합니다.
3. Cretop에서 조건검색을 직접 입력하고 검색 결과 화면까지 이동합니다.
4. 앱에서 `로그인 완료`를 누른 뒤 `조건검색 복사` 탭의 `화면 테이블 복사`를 누릅니다.

앱은 Chrome의 원격 디버깅 포트로 현재 Cretop 탭에 연결해 화면의 HTML table을 읽고, 다음 페이지 버튼이 보이면 지정한 최대 페이지 수까지 반복합니다. CAPTCHA, 봇 탐지, 접근 통제, rate limit 우회 기능은 포함하지 않습니다.

엑셀 기반 검색 자동 처리와 중복 후보 선택 흐름은 아직 구현 전입니다. 향후 처리 로직은 Scrapling을 사용하되, 접근 통제나 크롤링 방지 우회 기능은 포함하지 않습니다.
