# Maxawon

Maxawon은 사용자가 직접 로그인한 뒤, 화면에 열린 조건검색 결과 테이블을 CSV로 저장하는 데스크탑 도구입니다.

로그인은 자동으로 처리하지 않습니다. 사용자가 Chrome에서 직접 로그인하고, 앱으로 돌아와 `로그인 완료`를 눌러야 합니다.

## 준비

- Python 3
- Node.js
- Google Chrome
- Maxawon에 접근할 수 있는 계정

처음 한 번만 설치합니다.

```bash
python -m pip install -e .
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
5. 왼쪽 메뉴에서 `조건검색 테이블 CSV 저장`을 엽니다.
6. 필요하면 `최대 페이지`와 `저장 파일`을 변경합니다.
7. `현재 조건검색 테이블 저장`을 누릅니다.

복사가 끝나면 지정한 CSV 파일에 결과가 저장되고, 앱 화면에는 앞부분만 미리보기로 표시됩니다.

## 저장 위치

기본 저장 파일은 앱 데이터 폴더 아래의 `output/maxawon_condition_search.csv`입니다.

다른 위치에 저장하려면 `조건검색 테이블 CSV 저장` 화면에서 `변경`을 누르고 CSV 파일 경로를 선택하세요.

## Chrome 종료

- `실행된 Chrome 종료`: 이 앱에서 연 Chrome만 종료합니다.
- `전체 Chrome 종료`: 사용자가 따로 열어 둔 Chrome까지 모두 종료할 수 있습니다. 필요한 경우에만 사용하세요.

## 아직 지원하지 않는 기능

- 엑셀 파일을 읽어 Maxawon 검색을 자동으로 반복 실행하는 기능
- 여러 후보가 나왔을 때 회사를 자동으로 판별하는 기능
- 로그인 자동화

이 프로그램은 CAPTCHA, 봇 탐지, 접근 제한, 속도 제한 같은 보호 장치를 우회하지 않습니다.

## 기존 Tkinter UI

Electron UI가 기본 실행 방식입니다. 예전 Tkinter UI가 필요하면 아래 명령으로 실행할 수 있습니다.

```bash
python -m maxawon
```

또는:

```bash
maxawon
```
