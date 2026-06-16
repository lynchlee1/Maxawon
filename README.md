# Maxawon

맥사원(Maxawon)은 사용자가 직접 로그인한 뒤, 화면에 열린 조건검색 결과 테이블을 CSV로 저장하는 데스크탑 도구입니다.
이름은 신입사원처럼 열심히 일하는 업무용 에이전트라는 뜻입니다.  

로그인은 자동으로 처리하지 않습니다. 사용자가 Chrome에서 직접 로그인하고, 앱으로 돌아와 `로그인 완료`를 눌러야 합니다.

## 준비

- Python 3
- Node.js
- Google Chrome
- Maxawon에 접근할 수 있는 계정

처음 한 번만 설치합니다.

```bash
python3 -m pip install -e .
npm install
```

## 실행

일반 실행:

```bash
npm run desktop
```

개발자 도구를 같이 열어야 할 때:

```bash
npm run desktop:dev
```

## 사용 순서

1. 앱에서 `Chrome 열기`를 누릅니다.
2. 열린 Chrome에서 Maxawon에 직접 로그인합니다.
3. Maxawon에서 조건검색을 직접 실행하고, 결과 테이블이 보이는 화면까지 이동합니다.
4. 앱으로 돌아와 `로그인 완료`를 누릅니다.
5. 왼쪽 메뉴의 `Cretop` 아래에서 `Cretop 검색결과 저장하기`를 엽니다.
6. 필요하면 `최대 페이지`와 `저장 파일`을 변경합니다.
7. `현재 조건검색 테이블 저장`을 누릅니다.

복사가 끝나면 지정한 CSV 파일에 결과가 저장되고, 앱 화면에는 앞부분만 미리보기로 표시됩니다.

## 저장 위치

기본 저장 파일은 앱 데이터 폴더 아래의 `output/maxawon_condition_search.csv`입니다.

다른 위치에 저장하려면 `조건검색 테이블 CSV 저장` 화면에서 `변경`을 누르고 CSV 파일 경로를 선택하세요.

## PPT Forger

왼쪽 메뉴에서 `PPT Forger`를 열면 `finiq-pptforger`의 PPT 데이터 생성과 PPTX 템플릿 치환 기능을 사용할 수 있습니다.

1. 종목코드, 메자닌 종류, 투자금액, 발행금액, 지분율 조건을 입력합니다.
2. `설정`에서 템플릿 폴더, Gemini API 키, 모델, 프롬프트를 확인합니다.
3. `Model.xlsx`와 `{{key}}` 플레이스홀더가 들어 있는 `.pptx` 템플릿을 확인하거나 직접 선택합니다.
4. 회사 조회 후 주주 목록을 확인하고 필요하면 주주명, 관계, 주식수, 지분율, Call 적용 여부, 표시 순서를 수정합니다.
5. `AI 문구 생성`을 누르거나, 투자포인트/주가 포인트/리스크 문구를 직접 입력합니다.
6. `데이터 만들기`를 눌러 FnGuide/KIND, `Model.xlsx`, 주주 편집값, AI 문구 기반 치환 JSON과 결과 미리보기를 만듭니다.
7. `저장 파일`에서 결과 `.pptx` 경로를 선택하고 `PPT 생성`을 누릅니다.

기본 템플릿 위치는 `templates/Deal_Summary_Template_1.0`입니다. 이 폴더에 `Model.xlsx`와 `deal-summary.pptx`를 넣으면 앱이 기본 템플릿 폴더로 사용하고, 패키징 시에도 extra resource로 포함합니다.

현재 이식 범위는 FnGuide/KIND 회사 조회, `Model.xlsx` 읽기, Gemini 문구 생성과 프롬프트 설정, 회사/주주/ownership 미리보기, 주주 편집, 원본 PPT 치환 데이터 조립, PPTX 템플릿 치환과 저장입니다.

## Chrome 종료

- `실행된 Chrome 종료`: 이 앱에서 연 Chrome만 종료합니다.
- `전체 Chrome 종료`: 사용자가 따로 열어 둔 Chrome까지 모두 종료할 수 있습니다. 필요한 경우에만 사용하세요.

## 지원 범위

- 로그인 자동화는 지원하지 않습니다.
- Maxawon/Cretop에서는 사용자가 직접 로그인하고 직접 검색 화면까지 이동한 뒤, 현재 화면의 검색결과 테이블을 CSV로 저장합니다.

이 프로그램은 CAPTCHA, 봇 탐지, 접근 제한, 속도 제한 같은 보호 장치를 우회하지 않습니다.

## 기존 Tkinter UI

Electron UI가 기본 실행 방식입니다. 예전 Tkinter UI가 필요하면 아래 명령으로 실행할 수 있습니다.

```bash
python3 -m maxawon
```

또는:

```bash
maxawon
```
