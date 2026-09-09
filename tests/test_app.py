from io import BytesIO
import tempfile
import unittest
from unittest.mock import patch

import app as app_module
from ahu_utils import ahu_sort_key, default_ahu_for_test, extract_ahu_number


class AhuNumberTest(unittest.TestCase):
    def test_airborne_defaults_to_ahu_33(self):
        self.assertEqual(default_ahu_for_test('airborne_particle'), '33')
        self.assertEqual(default_ahu_for_test('air_velocity'), 'unknown')
        self.assertEqual(
            extract_ahu_number(
                'unknown',
                '/tmp/airborne.pdf',
                default=default_ahu_for_test('airborne_particle'),
            ),
            '33',
        )

    def test_sorts_numeric_and_text_ahu_values(self):
        self.assertEqual(
            sorted(['unknown', '37', '5'], key=ahu_sort_key),
            ['5', '37', 'unknown'],
        )

    def test_normalizes_ocr_value(self):
        self.assertEqual(extract_ahu_number('공 조 기 - 37'), '37')
        self.assertEqual(extract_ahu_number('AHU-42'), '42')
        self.assertEqual(extract_ahu_number('공조기 번호 33'), '33')
        self.assertEqual(extract_ahu_number('AHU No. 34'), '34')

    def test_falls_back_to_filename(self):
        filename = '/tmp/uuid_AHU-37_air_change_rate.pdf'
        self.assertEqual(extract_ahu_number('unknown', filename), '37')

    def test_rejects_zero_and_falls_back_to_filename(self):
        filename = '/tmp/uuid_AHU-33_airborne_particle.pdf'
        self.assertEqual(extract_ahu_number('0', filename), '33')
        self.assertEqual(extract_ahu_number('AHU-0'), 'unknown')

    def test_filename_ahu_overrides_an_incorrect_ocr_number(self):
        filename = '/tmp/uuid_AHU-33_hepa_filter.pdf'
        self.assertEqual(extract_ahu_number('1', filename), '33')


class GasAirborneProcessTest(unittest.TestCase):
    def test_processes_gas_airborne_in_one_request(self):
        extracted_records = [{
            'no': '1',
            'management_number': 'CA-01',
            'location': '충전 3실 (2505)',
            'grade': 'B',
            'particle_05': 13,
            'particle_50': 0,
            'judgement': '적합',
            'criteria_text': '허용기준',
            'performed_date': '2025.08.28',
        }]
        generated = {}

        def extractor(_path, api_key=None):
            self.assertEqual(api_key, 'test-key')
            return {'records': extracted_records}

        def generator(records, output_path):
            generated['records'] = records
            generated['output_path'] = output_path

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(app_module, 'ANTHROPIC_API_KEY', 'test-key'),
                patch.object(app_module, 'UPLOAD_FOLDER', temp_dir),
                patch.object(app_module, 'OUTPUT_FOLDER', temp_dir),
                patch.dict(
                    app_module.CLAUDE_EXTRACTORS,
                    {'gas_airborne_particle': extractor},
                ),
                patch.dict(
                    app_module.GENERATORS,
                    {'gas_airborne_particle': generator},
                ),
            ):
                response = app_module.app.test_client().post(
                    '/process',
                    data={
                        'test_type': 'gas_airborne_particle',
                        'language': 'en',
                        'pdf_files': (BytesIO(b'%PDF-1.4'), 'gas-test.pdf'),
                    },
                    content_type='multipart/form-data',
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['record_count'], 1)
        self.assertNotIn('ahu_count', payload)
        self.assertEqual(generated['records'], extracted_records)
        self.assertTrue(generated['output_path'].endswith('.xlsx'))


if __name__ == '__main__':
    unittest.main()
