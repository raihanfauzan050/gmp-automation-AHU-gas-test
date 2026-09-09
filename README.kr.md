# GMP Automation System

[![English README](https://img.shields.io/badge/README-English-2563eb)](README.md)

한국어 GMP 환경측정 및 가스 품질 검증 PDF를 온라인 OCR로 분석하여 표준 Microsoft Excel 보고서로 자동 변환하는 웹 애플리케이션입니다.

## 주요 기능

- **통합 처리 흐름:** 5개 측정 항목을 선택, PDF 업로드, Excel 생성, 다운로드의 동일한 흐름으로 처리합니다.
- **다중 PDF 일괄 처리:** 동일한 측정 항목의 PDF 여러 개를 한 번에 처리합니다.
- **Claude 기반 OCR:** Anthropic Claude API로 인쇄 문자와 필기 측정값을 추출합니다.
- **데이터 자동 구성:** A~D는 AHU 및 측정 반기별로 구성하고, E는 가스 품질 측정 일지 형식으로 구성합니다.
- **자동 Excel 보고서:** 별도 검토/수정 단계 없이 데이터, 요약, 등급별 Pivot 차트를 생성합니다.
- **기준 초과 시각화:** 설정된 기준을 벗어난 측정값을 빨간색으로 표시합니다.
- **다국어 UI:** 한국어와 영어 인터페이스를 제공합니다.

## 지원되는 측정 항목

| 코드 | 측정 항목 | 생성 Excel 파일명 |
| --- | --- | --- |
| A | 부유입자 측정 (Airborne Particle Test) | `Airborne_Particle_Test_Result_and_Graph.xlsx` |
| B | 풍속 측정 (Air Velocity Test) | `Air_Velocity_Test_Result_and_Graph.xlsx` |
| C | 환기횟수 측정 (Air Change Rate Test) | `Air_Change_Rate_Test_Result_and_Graph.xlsx` |
| D | HEPA 필터 검사 (HEPA Filter Test) | `HEPA_Filter_Test_Result_and_Graph.xlsx` |
| E | 가스 품질 검증 부유입자 시험 (Airborne Particle for Gas Quality Verification Test) | `Airborne_Particle_for_Gas_Quality_Verification_Test_Result_and_Graph.xlsx` |

## Excel 구성

### A. 부유입자 측정

각 AHU에는 공통 Data 및 Table 시트와 데이터에 존재하는 등급별 Pivot 차트 시트가 생성됩니다:

```text
AHU-33 Data
AHU-33 Table
AHU-33 Pivot 0.5µm Grade A
AHU-33 Pivot 0.5µm Grade B
AHU-33 Pivot 5.0µm Grade A
AHU-33 Pivot 5.0µm Grade B
...
```

각 Pivot 시트에는 해당 등급의 측정 위치와 해당 등급의 경고/조치 기준선만 표시됩니다. 최신 측정 시점이 상반기(`상`)인지 하반기(`하`)인지와 관계없이 업로드된 전체 데이터에서 등급을 결정합니다.

### B~D. AHU 측정

풍속, 환기횟수, HEPA 필터 측정은 AHU별 Data, Table, Pivot 시트를 생성합니다.

### E. 가스 품질 검증

E 항목은 AHU로 그룹화하지 않습니다. 공통 데이터 시트와 데이터에 존재하는 등급별 입자 크기 차트 시트를 생성합니다:

```text
데이터
Pivot 0.5µm Grade A
Pivot 0.5µm Grade B
Pivot 5.0µm Grade A
Pivot 5.0µm Grade B
...
```

각 Pivot 시트에는 해당 등급의 측정 기록과 경고 기준선만 표시됩니다.

## 사전 요구 사항

- Python 3.10 이상
- Poppler (PDF 페이지를 이미지로 변환하기 위해 필요)
- OCR 실행을 위한 네트워크 연결 및 Anthropic API Key

### Poppler 설치 방법:

```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt install poppler-utils
```

Windows의 경우 [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)를 다운로드하여 `C:\poppler`에 압축 해제 후, `C:\poppler\Library\bin` 경로를 System `PATH` 환경 변수에 추가하세요.

## 설치 방법

```bash
git clone --branch gmp-online --single-branch https://github.com/irfanqs/gmp-automation.git
cd gmp-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows 환경에서는 아래 명령어로 가상환경을 활성화합니다:

```bat
.venv\Scripts\activate
```

## Anthropic API Key 설정

Online OCR 서비스를 사용하려면 Anthropic API Key가 필요합니다. [Anthropic Console](https://console.anthropic.com/settings/keys)에서 키를 생성한 후 로컬 환경 파일을 만드세요:

```bash
cp .env.example .env
```

`.env` 파일을 열고 등호 뒤에 키를 입력합니다:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

`.env` 파일은 Git에서 제외되므로 커밋하거나 공유하지 마세요. 애플리케이션이 서버에서 이 키를 읽기 때문에 사용자는 웹 인터페이스에 키를 입력하지 않습니다.

## 애플리케이션 실행

```bash
python app.py
```

또는 제공된 실행 스크립트를 사용할 수 있습니다:

```bash
# macOS/Linux
bash START_LINUX.sh

# Windows
START_WINDOWS.bat
```

Windows에서 처음 실행하면 스크립트가 Anthropic API Key를 요청하고 `.env`에 안전하게 저장합니다. 키는 터미널에 표시되거나 Git에 저장되지 않습니다.

웹 브라우저에서 `http://localhost:5001/online`에 접속하세요.

## Docker 배포

Docker Engine 및 Docker Compose 플러그인이 필요합니다. 위의 API Key 설정을 완료한 후 아래 명령어로 실행하세요:

```bash
bash deploy.sh
```

API Key는 서버에만 유지되며 브라우저로 전송되지 않습니다.

Online OCR 애플리케이션은 `http://localhost:5001/online`에서 접속할 수 있습니다. 포트를 변경해야 하는 경우:

```bash
HOST_PORT=8081 bash deploy.sh
```

생성된 Excel 파일과 임시 업로드 파일은 Docker 볼륨에 저장됩니다. 로그 확인 및 정지는 아래 명령어를 사용하세요:

```bash
docker compose -p gmp-online logs -f
docker compose -p gmp-online down
```

## 사용 방법

1. 측정할 시험 항목(A~E) 중 하나를 선택합니다.
2. 동일한 시험 항목의 PDF 파일을 하나 이상 업로드합니다.
3. `Excel 자동 생성 시작` 버튼을 클릭하여 보고서를 생성하고 다운로드합니다.

OCR과 보고서 생성 사이에 별도 검토 화면은 표시되지 않습니다. A~D의 각 PDF는 1개 AHU의 1개 반기 측정 기록서여야 하며, E는 가스 품질 부유입자 측정 일지를 사용합니다. OCR 정확도는 스캔 품질과 필기 상태에 영향을 받습니다.

## 프로젝트 구조

```text
gmp-automation/
├── .env.example           # 환경 변수 템플릿
├── app.py                 # Flask 라우트 및 원클릭 처리 파이프라인
├── ahu_utils.py           # AHU 추출, 기본값, 정렬 유틸리티
├── config.py              # 측정 등록, 기준값, 경로, Excel 스타일
├── ocr_engine.py          # Anthropic OCR 프롬프트 및 PDF 이미지 처리
├── excel_generator.py     # Excel 데이터, 테이블, Pivot 차트 생성
├── templates/
│   └── index.html         # 한국어/영어 웹 인터페이스
├── boilerplate/           # 참고 Excel 템플릿
├── tests/                 # 처리 흐름 및 Excel 단위 테스트
├── uploads/               # 업로드 PDF 임시 저장소
├── outputs/               # 생성된 Excel 보고서
├── Dockerfile             # 운영 컨테이너 이미지
├── docker-compose.yml     # 서비스, 볼륨, 포트, 상태 확인 설정
├── deploy.sh              # Docker Compose 배포 스크립트
├── START_LINUX.sh         # Linux/macOS Gunicorn 실행
├── START_WINDOWS.bat      # Windows Waitress 실행
└── requirements.txt       # Python 의존성 목록
```

## 테스트

전체 단위 테스트는 다음 명령어로 실행합니다:

```bash
python -m unittest discover -s tests -v
```

## 참고 사항

- Online OCR 사용 시 Anthropic 계정에 따라 API 비용이 발생합니다.
- 시험 기준값과 측정 항목 등록은 `config.py`에서 관리합니다.
- 부유입자 Pivot 시트는 업로드 데이터에 존재하는 등급에 대해서만 생성하며 상·하반기 등급 필터는 적용하지 않습니다.
- 1회 업로드 용량 제한은 100MB입니다.
- Excel 보고서가 성공적으로 생성되면 업로드된 임시 PDF 파일은 자동으로 삭제됩니다.
- 측정 항목별 출력 파일명은 고정되어 있으므로 같은 항목을 다시 실행하면 이전 보고서를 대체합니다.
