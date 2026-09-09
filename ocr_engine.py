"""
GMP Automation System - OCR Engine
Uses Anthropic Claude API to extract structured data from scanned PDF images.
"""

import base64
import json
import re
import requests
import os
from pdf2image import convert_from_path
from io import BytesIO
from PIL import ImageEnhance, ImageFilter
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_API_URL


def pdf_to_images(pdf_path, dpi=150):
    """Convert PDF pages to PIL Images."""
    images = convert_from_path(pdf_path, dpi=dpi)
    return images


def image_to_base64(pil_image):
    """Convert PIL Image to base64 string."""
    buffer = BytesIO()
    pil_image.save(buffer, format='PNG')
    return base64.standard_b64encode(buffer.getvalue()).decode('utf-8')


def call_claude_api(images_b64, prompt, api_key=None, image_descriptions=None):
    """Call Claude API with images and a prompt. Returns parsed JSON."""
    key = api_key or ANTHROPIC_API_KEY
    if not key:
        raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY in the server environment.")

    content = []
    for index, img_b64 in enumerate(images_b64):
        if image_descriptions:
            content.append({"type": "text", "text": image_descriptions[index]})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_b64
            }
        })
    content.append({"type": "text", "text": prompt})

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": content}]
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01"
    }

    response = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers, timeout=300)

    if response.status_code != 200:
        raise Exception(f"Claude API Error {response.status_code}: {response.text}")

    result = response.json()
    text = ""
    for block in result.get("content", []):
        if block.get("type") == "text":
            text += block["text"]

    # Extract JSON from response
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse Claude response as JSON: {e}\nResponse: {text[:500]}")


# =============================================================================
# OCR PROMPTS FOR EACH TEST TYPE
# =============================================================================

PROMPT_AIRBORNE_PARTICLE = """You are analyzing a scanned Korean GMP document: 부유입자 측정 기록서 (Airborne Particle Test Record).

Extract ALL data and return ONLY valid JSON (no other text) with this exact structure:

{
  "ahu": "the AHU number from 해당 공조기 field (e.g., '33' if it says 공조기-33)",
  "date": "the measurement date from 측정일자 field (e.g., '2025.08.14')",
  "result": "측정결과 value (e.g., '적합')",
  "rooms": [
    {
      "no_start": 1,
      "no_end": 6,
      "grade": "B",
      "room_number": "2142",
      "room_name": "무균 실험실",
      "measurements": [
        {"point": 1, "value_05": 121, "value_50": 7},
        {"point": 2, "value_05": 194, "value_50": 0}
      ]
    }
  ]
}

IMPORTANT RULES:
- Extract EVERY row from the bottom table (Tabel Bawah / 측정값 table)
- "grade" is from 청정등급 column (A, B, C, or D)
- "room_number" is from 실번호 column
- "room_name" is from 실명 column
- "point" is from 측정번호 column
- "value_05" is the 0.5 µm measurement value (integer)
- "value_50" is the 5.0 µm measurement value (integer)
- Group measurements by room (same room_number + room_name = same room object)
- Include ALL pages of data
- Inspect the metadata section on every page and read AHU ONLY from the 해당 공조기 field.
- The AHU value may be beside or below the label and may appear as 공조기-33, 공조기 번호 33, 공조기 No. 33, AHU No. 33, or a bare 33 in the value cell. Return only "33".
- Never infer AHU from NO, 측정번호, particle sizes such as 0.5 µm, or measurement values; return "unknown" if unreadable
- Return ONLY the JSON, no markdown, no explanation"""


PROMPT_AIR_VELOCITY = """You are analyzing a scanned Korean GMP document: 풍속 측정 기록서 (Air Velocity Test Record).

Extract ALL data and return ONLY valid JSON (no other text) with this exact structure:

{
  "ahu": "the AHU number (e.g., '33' if it says 공조기-33)",
  "date": "the measurement date from 측정일자 (e.g., '2025.08.02')",
  "result": "측정결과 value",
  "machines": [
    {
      "no_start": 1,
      "no_end": 4,
      "grade": "A",
      "room_number": "2142",
      "machine_name": "무균시험실 BSC\\nBio SafetyCabinet-1(16830)",
      "measurements": [
        {"point": 1, "value": 0.47},
        {"point": 2, "value": 0.44},
        {"point": 3, "value": 0.46},
        {"point": 4, "value": 0.44}
      ]
    }
  ]
}

IMPORTANT RULES:
- Extract EVERY row from the measurement table
- "grade" is from 청정등급 column (A, B, C, or D)
- "room_number" is from 실번호 column
- "machine_name" is from 실명 column. Include the full name with both Korean name and model/code on separate lines using \\n
- "value" is the measurement value in m/s (decimal number)
- Group measurements by machine (same machine_name = same machine object)
- Include ALL pages of data
- Read AHU ONLY from the top 해당 공조기 field; never infer it from NO or 측정번호, and return "unknown" if unreadable
- Return ONLY the JSON, no markdown, no explanation"""


PROMPT_AIR_CHANGE_RATE = """You are analyzing a scanned Korean GMP document: 환기횟수 측정 기록서 (Air Change Rate Test Record).

Extract ALL data and return ONLY valid JSON (no other text) with this exact structure:

{
  "ahu": "the AHU number (e.g., '33' if it says 공조기-33)",
  "date": "the measurement date from 측정일자 (e.g., '2025.08.02')",
  "result": "측정결과 value",
  "rooms": [
    {
      "no": 1,
      "grade": "B",
      "room_number": "2142",
      "room_name": "무균시험실",
      "volume": 22.4,
      "air_flow_measurements": [
        {"point": 1, "air_flow": 657.8},
        {"point": 2, "air_flow": 760.1}
      ],
      "total_air_flow": 1417.9,
      "ach": 63
    }
  ]
}

IMPORTANT RULES:
- Extract EVERY row from the measurement table
- The table uses merged cells: multiple measurement rows followed by a 합계 row belong to ONE room
- Put only numbered measurement rows in "air_flow_measurements"; do not treat 합계 as another room or measurement point
- Read "total_air_flow" from the 풍량 value on the 합계 row
- "grade" is from 청정등급 column (B, C, or D - no A for ACH)
- "room_number" is from 실번호 column
- "room_name" is from 실명 column
- "volume" is from 체적 column (decimal number)
- "air_flow" values are from 풍량(m³/hr) column
- "total_air_flow" is the 합계 value (sum of air_flow values). If only 1 measurement point, total = that single value.
- "ach" is from 환기횟수(회/hr) column (integer)
- Read "ahu" ONLY from the top 해당 공조기 field; never infer it from NO, 측정번호, or measurement values
- If 해당 공조기 is unreadable, return "unknown"
- Include ALL rows
- Return ONLY the JSON, no markdown, no explanation"""


PROMPT_HEPA_FILTER = """You are analyzing a scanned Korean GMP document: HEPA FILTER 성능 검사 집계표 (HEPA Filter Test Record).

Extract ALL data and return ONLY valid JSON (no other text) with this exact structure:

{
  "ahu": "the AHU number (e.g., '33' if it says 공조기-33)",
  "date": "the measurement date from 측정일자 (e.g., '2025.08.03')",
  "result": "측정결과 value",
  "standard": "측정기준 value (e.g., '0.01%')",
  "items": [
    {
      "no_start": 1,
      "no_end": 1,
      "room_number": "2142",
      "item_name": "무균시험실 BSC",
      "measurements": [
        {"point": 1, "value": 0.003}
      ]
    }
  ]
}

IMPORTANT RULES:
- Extract EVERY row from the measurement table
- "room_number" is from 실번호 column
- "item_name" is from 실명 column
- "value" is the 측정값 percentage value as a NUMBER (e.g., if it shows "0.003%", enter 0.003)
- Do NOT include the % sign in the value - just the number
- Group measurements by item (same room_number + item_name = same item object)
- There is NO 청정등급 column in this test type
- Include ALL pages of data
- Read AHU ONLY from the top 해당 공조기 field (the value below it may be 공조기-33)
- Never use NO, 측정번호, 0.01%, or 측정값 as AHU; return "unknown" if the field is unreadable
- Return ONLY the JSON, no markdown, no explanation"""


PROMPT_GAS_AIRBORNE_PARTICLE = """You are analyzing a scanned Korean GMP gas quality document: 부유입자 측정 일지 (Airborne Particle for Gas Quality Verification Test).

Extract ALL numbered measurement rows and return ONLY valid JSON (no other text) with this exact structure:

{
  "records": [
    {
      "no": "1",
      "management_number": "CA-01",
      "location": "충전 3실 (2505)",
      "grade": "B",
      "particle_05": 13,
      "particle_50": 0,
      "judgement": "적합",
      "criteria_text": "the printed 허용기준 text",
      "performed_date": "2025.08.28"
    }
  ]
}

IMPORTANT RULES:
- Create exactly one record per numbered measurement row and include ALL rows from ALL pages
- "management_number" is from 관리번호 and "location" is from 측정위치
- "grade" must be the row's cleanroom grade (A, B, C, or D)
- "particle_05" and "particle_50" are handwritten integer counts from the 0.5 μm and 5.0 μm columns; return JSON numbers
- Use enhanced table close-ups only to verify handwriting; they do not contain additional records
- Carefully distinguish ambiguous handwritten digits such as 3/4, 1/7, 0/6, and 6/8 by their pen strokes
- Never infer a measured value from a printed limit
- Before returning JSON, compare each count with its grade limit and checked judgement; if they conflict, re-inspect the handwriting rather than changing a clearly written value
- "judgement" must be exactly "적합" or "부적합"
- Repeat the document-level criterion, judgement, and performed date in every record
- Read "criteria_text" only from the printed 허용기준 section
- Read "performed_date" only from the handwritten left-side Performed by date, never the right-side Verified by date
- Normalize "performed_date" as YYYY.MM.DD and carefully distinguish handwritten 08 from 06
- Preserve Korean text exactly and return ONLY the JSON, no markdown, no explanation"""


def _normalize_gas_airborne_data(payload):
    """Validate and normalize the flat record schema returned by OCR."""
    normalized = []
    seen = set()
    if isinstance(payload, dict):
        source = payload.get('records', [])
    elif isinstance(payload, list):
        source = payload
    else:
        source = []

    for index, row in enumerate(source, start=1):
        if not isinstance(row, dict):
            continue
        management_number = str(row.get('management_number', '')).strip()
        location = str(row.get('location', '')).strip()
        if not management_number or not location:
            continue

        particle_values = []
        for field in ('particle_05', 'particle_50'):
            match = re.search(r'-?[\d,]+(?:\.\d+)?', str(row.get(field, '')))
            if not match:
                particle_values.append(None)
                continue
            value = float(match.group(0).replace(',', ''))
            particle_values.append(int(value) if value.is_integer() else value)
        if particle_values == [None, None]:
            continue

        date_match = re.search(
            r'(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})',
            str(row.get('performed_date', '')),
        )
        performed_date = ''
        if date_match:
            year, month, day = date_match.groups()
            performed_date = f'{year}.{int(month):02d}.{int(day):02d}'

        record = {
            'no': str(row.get('no', index)).strip(),
            'management_number': management_number,
            'location': location,
            'grade': str(row.get('grade', '')).strip().upper(),
            'particle_05': particle_values[0] if particle_values[0] is not None else 0,
            'particle_50': particle_values[1] if particle_values[1] is not None else 0,
            'judgement': '부적합' if str(row.get('judgement', '')).strip() == '부적합' else '적합',
            'criteria_text': str(row.get('criteria_text', '')).strip(),
            'performed_date': performed_date,
        }
        identity = tuple(
            re.sub(r'\s+', '', str(record[field]))
            for field in ('performed_date', 'no', 'management_number', 'location')
        )
        if identity not in seen:
            seen.add(identity)
            normalized.append(record)

    return {'records': normalized}


def extract_airborne_particle(pdf_path, api_key=None):
    """Extract data from Airborne Particle Test PDF."""
    images = pdf_to_images(pdf_path)
    images_b64 = [image_to_base64(img) for img in images]
    return call_claude_api(images_b64, PROMPT_AIRBORNE_PARTICLE, api_key)


def extract_air_velocity(pdf_path, api_key=None):
    """Extract data from Air Velocity Test PDF."""
    images = pdf_to_images(pdf_path)
    images_b64 = [image_to_base64(img) for img in images]
    return call_claude_api(images_b64, PROMPT_AIR_VELOCITY, api_key)


def extract_air_change_rate(pdf_path, api_key=None):
    """Extract data from Air Change Rate Test PDF."""
    images = pdf_to_images(pdf_path)
    images_b64 = [image_to_base64(img) for img in images]
    return call_claude_api(images_b64, PROMPT_AIR_CHANGE_RATE, api_key)


def extract_hepa_filter(pdf_path, api_key=None):
    """Extract data from HEPA Filter Test PDF."""
    images = pdf_to_images(pdf_path)
    images_b64 = [image_to_base64(img) for img in images]
    return call_claude_api(images_b64, PROMPT_HEPA_FILTER, api_key)


def extract_gas_airborne_particle(pdf_path, api_key=None):
    """Extract flat measurement rows from the gas-quality airborne log."""
    images = pdf_to_images(pdf_path, dpi=200)
    images_b64 = []
    descriptions = []

    for page_number, image in enumerate(images, start=1):
        images_b64.append(image_to_base64(image))
        descriptions.append(f"Full scanned document page {page_number}.")

        width, height = image.size
        table_detail = image.crop((
            int(width * 0.02),
            int(height * 0.07),
            int(width * 0.98),
            int(height * 0.48),
        ))
        table_detail = ImageEnhance.Contrast(table_detail).enhance(1.35)
        table_detail = table_detail.filter(ImageFilter.SHARPEN)
        images_b64.append(image_to_base64(table_detail))
        descriptions.append(
            f"Enhanced measurement-table close-up for page {page_number}; "
            "use it only to verify handwritten values."
        )

    if images:
        width, height = images[-1].size
        date_detail = images[-1].crop((0, int(height * 0.68), int(width * 0.58), height))
        images_b64.append(image_to_base64(date_detail))
        descriptions.append(
            "Close-up of the left-side Performed by signature and date from the final page."
        )

    payload = call_claude_api(
        images_b64,
        PROMPT_GAS_AIRBORNE_PARTICLE,
        api_key,
        image_descriptions=descriptions,
    )
    return _normalize_gas_airborne_data(payload)


# Map test types to extraction functions
EXTRACTORS = {
    'airborne_particle': extract_airborne_particle,
    'air_velocity': extract_air_velocity,
    'air_change_rate': extract_air_change_rate,
    'hepa_filter': extract_hepa_filter,
    'gas_airborne_particle': extract_gas_airborne_particle,
}
