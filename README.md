# GMP Automation System

[![Korean README](https://img.shields.io/badge/README-한국어-2563eb)](README.kr.md)

A web application that uses online OCR to convert Korean GMP environmental measurement and gas-quality verification PDFs into standardized Microsoft Excel reports.

## Features

- Provides one workflow for five measurement types: select a type, upload PDFs, generate, and download.
- Processes multiple PDFs of the same measurement type in one request.
- Extracts handwritten and printed data through the Anthropic Claude API.
- Groups tests A-D by AHU and measurement semester; test E uses a flat gas-quality measurement log.
- Produces data, summary, and Pivot chart sheets without a separate review/edit step.
- Highlights measurements outside their configured limits in red.
- Supports Korean and English interfaces.

## Supported Tests

| Code | Test | Excel File |
| --- | --- | --- |
| A | Airborne Particle Test | `Airborne_Particle_Test_Result_and_Graph.xlsx` |
| B | Air Velocity Test | `Air_Velocity_Test_Result_and_Graph.xlsx` |
| C | Air Change Rate Test | `Air_Change_Rate_Test_Result_and_Graph.xlsx` |
| D | HEPA Filter Test | `HEPA_Filter_Test_Result_and_Graph.xlsx` |
| E | Airborne Particle for Gas Quality Verification Test | `Airborne_Particle_for_Gas_Quality_Verification_Test_Result_and_Graph.xlsx` |

## Workbook Structure

### A. Airborne Particle Test

Each AHU receives shared Data and Table sheets, followed by two Pivot chart sheets for every grade present:

```text
AHU-33 Data
AHU-33 Table
AHU-33 Pivot 0.5µm Grade A
AHU-33 Pivot 0.5µm Grade B
AHU-33 Pivot 5.0µm Grade A
AHU-33 Pivot 5.0µm Grade B
...
```

Each Pivot sheet contains only locations from its grade and only that grade's warning/action limit lines. Grade availability is determined from all uploaded data, regardless of whether the newest measurement is from the first (`상`) or second (`하`) half of the year.

### B-D. AHU Tests

Air Velocity, Air Change Rate, and HEPA Filter generate Data, Table, and Pivot sheets for each AHU.

### E. Gas Quality Verification

Test E is not grouped by AHU. It creates one shared data sheet and separate particle-size charts for every grade present:

```text
데이터
Pivot 0.5µm Grade A
Pivot 0.5µm Grade B
Pivot 5.0µm Grade A
Pivot 5.0µm Grade B
...
```

Each Pivot sheet contains only records and the warning limit for its grade.

## Requirements

- Python 3.10 or later
- Poppler, used to convert PDF pages into images
- An internet connection and an Anthropic API key for OCR

### Installing Poppler

```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt install poppler-utils
```

On Windows, download [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases), extract it to `C:\poppler`, and add `C:\poppler\Library\bin` to the system `PATH` environment variable.

## Installation

```bash
git clone --branch gmp-online --single-branch https://github.com/irfanqs/gmp-automation.git
cd gmp-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the virtual environment with:

```bat
.venv\Scripts\activate
```

## Configure the Anthropic API Key

The Online OCR service requires an Anthropic API key. Create one in the [Anthropic Console](https://console.anthropic.com/settings/keys), then create the local environment file:

```bash
cp .env.example .env
```

Open `.env` and add the key after the equals sign:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Keep `.env` private. It is ignored by Git and must not be committed or shared. The application reads this key on the server, so users do not enter it in the web interface.

## Running the Application

```bash
python app.py
```

Alternatively, use the provided startup scripts:

```bash
# macOS/Linux
bash START_LINUX.sh

# Windows
START_WINDOWS.bat
```

On the first Windows startup, the script asks for an Anthropic API key and stores it privately in `.env`. The key is not displayed in the terminal or stored in Git.

Open `http://localhost:5001/online` in a browser.

## Docker Deployment

Docker Engine and the Docker Compose plugin are required. Complete the API key setup above, then deploy this branch with:

```bash
bash deploy.sh
```

The API key remains on the server and is not sent to the browser.

The Online OCR application is available at `http://localhost:5001/online`. To use a different host port:

```bash
HOST_PORT=8081 bash deploy.sh
```

Generated files and temporary uploads are stored in Docker volumes. Use the following commands to inspect logs or stop the application:

```bash
docker compose -p gmp-online logs -f
docker compose -p gmp-online down
```

## Usage

1. Select one of the supported test types (A-E).
2. Upload one or more PDFs of the same test type.
3. Click `Start Excel Generation` to generate and download the report.

No review form is shown between OCR and report generation. For tests A-D, each PDF must contain one AHU measurement record for one semester. Test E accepts gas-quality airborne particle measurement logs. OCR accuracy depends on scan quality and handwriting clarity.

## Project Structure

```text
gmp-automation/
├── .env.example           # Environment variable template
├── app.py                 # Flask routes and one-click processing pipeline
├── ahu_utils.py           # AHU extraction, fallback, and sorting helpers
├── config.py              # Test registry, limits, paths, and Excel styles
├── ocr_engine.py          # Anthropic OCR prompts and PDF image processing
├── excel_generator.py     # Excel data, table, and Pivot chart generators
├── templates/
│   └── index.html         # Bilingual web interface
├── boilerplate/           # Reference Excel templates
├── tests/                 # Unit tests for processing and workbooks
├── uploads/               # Temporary uploaded PDFs
├── outputs/               # Generated Excel reports
├── Dockerfile             # Production container image
├── docker-compose.yml     # App service, volumes, port, and health check
├── deploy.sh              # Docker Compose deployment helper
├── START_LINUX.sh         # Linux/macOS Gunicorn startup
├── START_WINDOWS.bat      # Windows Waitress startup
└── requirements.txt       # Python dependencies
```

## Testing

Run the complete unit test suite with:

```bash
python -m unittest discover -s tests -v
```

## Notes

- OCR requests may incur charges depending on your Anthropic account usage.
- Test limits and measurement registrations are configured in `config.py`.
- Airborne Pivot sheets are created only for grades found in the uploaded data; there is no first-half/second-half grade filter.
- The upload limit is 100 MB per request.
- Temporary uploaded PDFs are deleted automatically after an Excel report is generated successfully.
- Reports use one fixed output filename per test type, so a later run of the same type replaces the previous generated report.
