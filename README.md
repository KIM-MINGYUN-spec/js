# 한국 주식 오전 단타 급등 후보 시스템

전일 한국시장 마감 데이터를 바탕으로, 다음 날 오전 9시~10시 사이 다시 수급이 붙을 가능성이 있는 종목을 최대 2개까지 추려주는 Streamlit 앱입니다.

현재 버전은 "아무 종목이나 2개 채우기"보다 "강한 후보만 남기기"에 초점을 둡니다. 그래서 조건이 애매하면 0개 또는 1개만 추천하고, 대신 `관찰 후보`를 함께 보여줍니다.

## 현재 구조

- 미국장 / 글로벌 매크로: `yfinance`
- 한국 종목 후보 수집: `yfinance` 기반 대표 유동성 종목 유니버스
- 점수화 기준:
  - 거래대금 / 유동성
  - 고가권 마감 강도
  - 업종 상대 강도
  - 단기 차트 전환
  - 글로벌 정합성
  - 최근 3일 과열 패널티

## 주요 특징

- 전일 거래대금과 고가권 마감 강도를 가장 먼저 봅니다.
- 최근 3일 급등 과열 종목은 강하게 감점하거나 제외합니다.
- 추천 종목이 부족하면 억지로 2개를 채우지 않습니다.
- 정식 추천 외에 `관찰 후보`를 별도로 보여줘 장초반 체크 대상을 확보합니다.
- 무료 데이터만 사용하며 API 키가 필요 없습니다.

## 파일 구성

- `app.py`: Streamlit 화면
- `market_context.py`: 미국장 / 글로벌 매크로 분류
- `scanner.py`: 한국 종목 후보 수집, 필터, 추천 선정
- `scoring.py`: 총점 / 급등 가능성 점수 계산
- `reason_writer.py`: 추천 이유, 트레이더 코멘트, 매매 가이드 문구
- `requirements.txt`: 설치 패키지

## 권장 환경

- Python `3.11` 권장
- Python `3.12`도 가능
- Python `3.13`은 이 프로젝트에서 권장하지 않습니다

## 설치

```powershell
cd C:\Users\PC\Desktop\영웅
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 실행

```powershell
cd C:\Users\PC\Desktop\영웅
.\.venv311\Scripts\Activate.ps1
python -m streamlit run app.py
```

브라우저가 자동으로 안 열리면 아래 주소로 접속하면 됩니다.

- [http://localhost:8501](http://localhost:8501)

## 다른 컴퓨터에서 사용하는 방법

아래 파일만 옮기면 됩니다.

- `app.py`
- `market_context.py`
- `scanner.py`
- `scoring.py`
- `reason_writer.py`
- `requirements.txt`
- `README.md`

옮기지 않아도 되는 폴더:

- `.venv`
- `.venv311`
- `__pycache__`

다른 컴퓨터에서는 Python 3.11 설치 후 아래 순서로 실행하면 됩니다.

```powershell
cd 프로젝트폴더
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

## exe로 만드는 방법

웹앱 형태는 그대로 유지되지만, `exe`를 실행하면 서버를 띄우고 브라우저를 자동으로 여는 방식으로 사용할 수 있습니다.

### 1. 빌드 PC에서 exe 만들기

```powershell
cd C:\Users\PC\Desktop\영웅
.\.venv311\Scripts\Activate.ps1
build_exe.bat
```

빌드가 끝나면 아래 경로가 생성됩니다.

- `dist\KoreanStockMorningPicker\KoreanStockMorningPicker.exe`

### 2. 다른 PC로 옮길 파일

아래 폴더 전체를 옮기는 편이 가장 안전합니다.

- `dist\KoreanStockMorningPicker`

### 3. 다른 PC에서 실행

- `KoreanStockMorningPicker.exe` 더블클릭
- 잠시 후 브라우저가 자동으로 열리며 앱이 실행됩니다

### 참고

- exe 방식도 인터넷 연결은 필요합니다
- 보안 프로그램에 따라 처음 실행 시 확인 창이 뜰 수 있습니다
- 만약 브라우저가 자동으로 안 열리면 `http://127.0.0.1:8501` 로 직접 접속하면 됩니다

## 출력 항목

- 종목명 / 종목코드
- 전일 종가
- 총점
- 급등 가능성 점수
- 유형
- 감시 가격
- 손절 가격
- 1차 목표가
- 2차 목표가
- 트레이더 코멘트
- 선정 이유
- 관찰 후보

## 참고 사항

- 이 앱은 실시간 호가창이 아니라 전일 일봉 기반 후보 선별용입니다.
- 장중 최종 매매 전에는 반드시 호가, 체결 강도, 시초 5분 흐름을 직접 확인해야 합니다.
- 데이터 제공처 응답 상태에 따라 특정 날짜에는 후보가 적거나 없을 수 있습니다.
- 현재 한국 종목 추천은 대표 유동성 종목 유니버스 중심이라 시장 전체를 완전 탐색하는 구조는 아닙니다.

## 실전 해석 팁

- `정식 추천`: 실제 매매 우선순위가 높은 후보
- `관찰 후보`: 점수는 아쉽지만 장초반 체크할 가치가 있는 후보
- `필터 통과 0개`: 쉬는 날일 수 있고, 데이터 응답이 약한 날일 수도 있습니다
- `후보 수집 0개`: 데이터 공급 상태를 다시 확인하는 편이 좋습니다

## 웹서버로 배포하기

가장 쉬운 방법은 `Streamlit Community Cloud`이고, 일반 웹서버처럼 올리고 싶으면 `Render`도 가능합니다.

### 방법 1. Streamlit Community Cloud

가장 간단합니다. 다만 GitHub 저장소가 필요합니다.

1. 이 프로젝트 폴더를 GitHub 저장소로 올립니다.
2. [Streamlit Community Cloud](https://share.streamlit.io/) 에 로그인합니다.
3. `New app`을 누릅니다.
4. 저장소와 브랜치, 메인 파일을 아래처럼 지정합니다.

- Main file path: `app.py`

5. Deploy를 누르면 웹 주소가 발급됩니다.

이 프로젝트는 이미 배포용 설정 파일 `.streamlit/config.toml`이 포함되어 있어 바로 올릴 수 있습니다.

### 방법 2. Render

GitHub에 올린 뒤 Render에서 연결하는 방식입니다.

1. 프로젝트를 GitHub에 올립니다.
2. [Render](https://render.com/) 에 로그인합니다.
3. `New +` -> `Blueprint` 또는 `Web Service`를 선택합니다.
4. 저장소를 연결합니다.

이 프로젝트에는 `render.yaml`이 포함되어 있어서 Blueprint 방식으로 바로 읽을 수 있습니다.

기본 실행 명령은 아래와 같습니다.

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

### 배포 전 체크

- Python 3.11 기준으로 맞춰져 있습니다
- `requirements.txt`만 설치되면 실행되도록 정리되어 있습니다
- 인터넷 연결이 있어야 미국장 / 한국 종목 데이터를 읽어올 수 있습니다

### 주의사항

- 이 앱은 외부 무료 데이터에 의존하므로, 배포 후에도 데이터 제공처 응답이 느리거나 비는 날이 있을 수 있습니다
- 모바일에서는 `exe`는 실행할 수 없지만, 웹 배포 주소로는 접속할 수 있습니다
