"""
GMP Automation System - Main Web Application
Flask-based web interface for processing environmental measurement PDFs.
"""

import os
import json
import uuid
import traceback
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
from ahu_utils import ahu_sort_key, extract_ahu_number
from config import ANTHROPIC_API_KEY, UPLOAD_FOLDER, OUTPUT_FOLDER, get_semester_label, TEST_TYPES
from ocr_engine import EXTRACTORS as CLAUDE_EXTRACTORS
from excel_generator import GENERATORS

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}

ERROR_MESSAGES = {
    'ko': {
        'invalid_test': '잘못된 측정 종류가 선택되었습니다.',
        'api_key_required': 'Anthropic API Key를 입력하세요.',
        'no_files': '업로드된 PDF 파일이 없습니다.',
        'no_valid_files': '유효한 PDF 파일을 찾을 수 없습니다.',
        'extract_failed': '모든 PDF에서 데이터를 추출하지 못했습니다.',
        'file_not_found': '파일을 찾을 수 없습니다.',
        'server_error': '서버 오류:',
        'processing_error': '처리 오류:',
        'empty_data': '측정표에서 데이터를 찾을 수 없습니다.',
        'ahu_missing': '해당 공조기 필드와 파일명에서 유효한 AHU 번호를 찾을 수 없습니다.',
    },
    'en': {
        'invalid_test': 'Invalid test type selected.',
        'api_key_required': 'Anthropic API Key is required.',
        'no_files': 'No PDF files uploaded.',
        'no_valid_files': 'No valid PDF files found.',
        'extract_failed': 'Failed to extract data from all PDFs.',
        'file_not_found': 'File not found.',
        'server_error': 'Server error:',
        'processing_error': 'Error processing:',
        'empty_data': 'No measurement data was found in the table.',
        'ahu_missing': 'No valid AHU number was found in the 해당 공조기 field or filename.',
    },
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _batch_state_path(batch_id):
    """Return temporary state path for one multi-request upload job."""
    if not batch_id or len(batch_id) > 64 or not all(c.isalnum() or c == '-' for c in batch_id):
        raise ValueError('Invalid batch id')
    batch_dir = os.path.join(UPLOAD_FOLDER, '.batches')
    os.makedirs(batch_dir, exist_ok=True)
    return os.path.join(batch_dir, f'{batch_id}.json')


def _merge_batch_data(existing, current, test_type):
    """Merge extracted records from one batch into accumulated job data."""
    warnings = list(existing.get('warnings', [])) + list(current.get('warnings', []))
    if test_type == 'gas_airborne_particle':
        return {
            'gas_records': existing.get('gas_records', []) + current.get('gas_records', []),
            'ahu_data': {},
            'warnings': warnings,
        }

    merged = {key: list(value) for key, value in existing.get('ahu_data', {}).items()}
    for ahu, entries in current.get('ahu_data', {}).items():
        existing_entries = merged.setdefault(ahu, [])
        existing_keys = {(entry.get('semester'), entry.get('date')) for entry in existing_entries}
        for entry in entries:
            entry_key = (entry.get('semester'), entry.get('date'))
            if entry_key in existing_keys:
                warnings.append(
                    f'Duplicate AHU {ahu} measurement for {entry.get("semester", "unknown semester")}.'
                )
            existing_entries.append(entry)
            existing_keys.add(entry_key)
    return {'ahu_data': merged, 'gas_records': [], 'warnings': warnings}


@app.route('/')
def index():
    """Redirect the root URL to the online OCR workflow."""
    return redirect(url_for('online'))


@app.route('/online')
def online():
    """Online OCR workflow using the hosted API."""
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process():
    """Process uploaded PDFs and generate Excel files."""
    try:
        test_type = request.form.get('test_type')
        language = request.form.get('language', 'ko').strip()
        messages = ERROR_MESSAGES.get(language, ERROR_MESSAGES['ko'])
        api_key = ANTHROPIC_API_KEY

        if not test_type or test_type not in CLAUDE_EXTRACTORS:
            return jsonify({'error': messages['invalid_test']}), 400

        if not api_key:
            return jsonify({'error': messages['api_key_required']}), 400

        files = request.files.getlist('pdf_files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': messages['no_files']}), 400

        batch_id = request.form.get('batch_id')
        try:
            batch_index = int(request.form.get('batch_index', '0'))
            batch_total = int(request.form.get('batch_total', '1'))
        except ValueError:
            return jsonify({'error': 'Invalid batch metadata.'}), 400
        if batch_total < 1 or batch_index < 0 or batch_index >= batch_total:
            return jsonify({'error': 'Invalid batch metadata.'}), 400
        is_batched = batch_id is not None
        state_path = _batch_state_path(batch_id) if is_batched else None

        # Save uploaded files
        saved_paths = []
        for f in files:
            if f and allowed_file(f.filename):
                filename = secure_filename(f.filename)
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                filepath = os.path.join(UPLOAD_FOLDER, unique_name)
                f.save(filepath)
                saved_paths.append(filepath)

        if not saved_paths:
            return jsonify({'error': messages['no_valid_files']}), 400

        # Extract data from each PDF
        extractor = CLAUDE_EXTRACTORS[test_type]
        is_gas_airborne = test_type == 'gas_airborne_particle'
        all_ahu_data = {}
        all_gas_records = []
        errors = []

        for pdf_path in saved_paths:
            try:
                data = extractor(pdf_path, api_key=api_key)
                if is_gas_airborne:
                    records = data.get('records', [])
                    if not records:
                        raise ValueError(messages['empty_data'])
                    all_gas_records.extend(records)
                    continue

                data_key = {
                    'airborne_particle': 'rooms',
                    'air_velocity': 'machines',
                    'air_change_rate': 'rooms',
                    'hepa_filter': 'items',
                }[test_type]
                if not data.get(data_key):
                    raise ValueError(messages['empty_data'])
                ahu_num = extract_ahu_number(
                    data.get('ahu'),
                    pdf_path,
                )
                if ahu_num == 'unknown':
                    raise ValueError(messages['ahu_missing'])
                date_str = data.get('date')
                date_str = date_str or '2025.08.01'
                semester_label = get_semester_label(date_str)

                # Organize data by AHU
                if ahu_num not in all_ahu_data:
                    all_ahu_data[ahu_num] = []

                # Build semester data based on test type
                sem_entry = {'semester': semester_label, 'date': date_str}

                if test_type == 'airborne_particle':
                    sem_entry['rooms'] = data.get('rooms', [])
                elif test_type == 'air_velocity':
                    sem_entry['machines'] = data.get('machines', [])
                elif test_type == 'air_change_rate':
                    sem_entry['rooms'] = data.get('rooms', [])
                elif test_type == 'hepa_filter':
                    sem_entry['items'] = data.get('items', [])

                all_ahu_data[ahu_num].append(sem_entry)

            except Exception as e:
                errors.append(f"{messages['processing_error']} {os.path.basename(pdf_path)}: {str(e)}")

        current_data = {
            'gas_records': all_gas_records,
            'ahu_data': all_ahu_data,
            'warnings': errors,
        }
        if is_batched:
            existing_data = {}
            if batch_index > 0:
                if not os.path.exists(state_path):
                    return jsonify({'error': 'Batch state not found. Restart upload.'}), 400
                with open(state_path, 'r', encoding='utf-8') as state_file:
                    existing_data = json.load(state_file)
            merged_data = _merge_batch_data(existing_data, current_data, test_type)
            if batch_index < batch_total - 1:
                with open(state_path, 'w', encoding='utf-8') as state_file:
                    json.dump(merged_data, state_file, ensure_ascii=False)
                for path in saved_paths:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                return jsonify({
                    'success': True,
                    'batch_complete': True,
                    'batch_index': batch_index,
                    'batch_total': batch_total,
                    'warnings': errors,
                })
            current_data = merged_data
            try:
                os.remove(state_path)
            except FileNotFoundError:
                pass

        all_gas_records = current_data['gas_records']
        all_ahu_data = current_data['ahu_data']
        errors = current_data['warnings']
        collected_data = all_gas_records if is_gas_airborne else all_ahu_data
        if not collected_data:
            error_msg = messages['extract_failed']
            if errors:
                error_msg += "\n" + "\n".join(errors)
            return jsonify({'error': error_msg}), 400

        # Generate Excel
        generator = GENERATORS[test_type]
        test_config = TEST_TYPES[test_type]
        output_filename = test_config['excel_filename']
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        generator(collected_data, output_path)

        # Clean up uploaded files
        for p in saved_paths:
            try:
                os.remove(p)
            except:
                pass

        result = {
            'success': True,
            'filename': output_filename,
            'download_url': f'/download/{output_filename}',
        }
        if is_gas_airborne:
            result['record_count'] = len(all_gas_records)
        else:
            result['ahu_count'] = len(all_ahu_data)
            result['ahu_list'] = sorted(all_ahu_data.keys(), key=ahu_sort_key)

        if errors:
            result['warnings'] = errors

        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        language = request.form.get('language', 'ko').strip()
        messages = ERROR_MESSAGES.get(language, ERROR_MESSAGES['ko'])
        return jsonify({'error': f"{messages['server_error']} {str(e)}"}), 500


@app.route('/download/<filename>')
def download(filename):
    """Download generated Excel file."""
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    return jsonify({'error': ERROR_MESSAGES['ko']['file_not_found']}), 404


if __name__ == '__main__':
    print("=" * 60)
    print("  GMP Automation System")
    print("  Open your browser and go to: http://localhost:5001/online")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5001, debug=False)
