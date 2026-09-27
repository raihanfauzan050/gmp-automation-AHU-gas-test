from io import BytesIO
import tempfile
import unittest
from unittest.mock import patch

import app as app_module
from ahu_utils import ahu_sort_key, extract_ahu_number


class AhuNumberTest(unittest.TestCase):
    def test_returns_unknown_without_a_valid_ahu_identity(self):
        self.assertEqual(extract_ahu_number('unknown', '/tmp/airborne.pdf'), 'unknown')
        self.assertEqual(extract_ahu_number('0', '/tmp/airborne.pdf'), 'unknown')
        self.assertEqual(extract_ahu_number('-33', '/tmp/airborne.pdf'), 'unknown')
        self.assertEqual(extract_ahu_number('33.0', '/tmp/airborne.pdf'), 'unknown')
        self.assertEqual(extract_ahu_number('33.5', '/tmp/airborne.pdf'), 'unknown')
        self.assertEqual(extract_ahu_number('AHU-33.5', '/tmp/airborne.pdf'), 'unknown')
        self.assertEqual(extract_ahu_number('unknown', '/tmp/AHU-33.5.pdf'), 'unknown')

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

    def test_ocr_ahu_overrides_filename_ahu(self):
        filename = '/tmp/uuid_AHU-33_hepa_filter.pdf'
        self.assertEqual(extract_ahu_number('42', filename), '42')


class AhuProcessTest(unittest.TestCase):
    TEST_CASES = {
        'airborne_particle': ('rooms', [{'room': 'test'}]),
        'air_velocity': ('machines', [{'machine': 'test'}]),
        'air_change_rate': ('rooms', [{'room': 'test'}]),
        'hepa_filter': ('items', [{'item': 'test'}]),
    }

    def test_processes_valid_pdfs_and_warns_about_missing_ahu_identity(self):
        for test_type, (data_key, measurements) in self.TEST_CASES.items():
            with self.subTest(test_type=test_type):
                generated = {}

                def extractor(path, api_key=None):
                    ahu = 'unknown' if 'missing-ahu' in path else '42'
                    return {'ahu': ahu, 'date': '2025.08.01', data_key: measurements}

                def generator(records, output_path):
                    generated['records'] = records

                with tempfile.TemporaryDirectory() as temp_dir:
                    with (
                        patch.object(app_module, 'ANTHROPIC_API_KEY', 'test-key'),
                        patch.object(app_module, 'UPLOAD_FOLDER', temp_dir),
                        patch.object(app_module, 'OUTPUT_FOLDER', temp_dir),
                        patch.dict(app_module.CLAUDE_EXTRACTORS, {test_type: extractor}),
                        patch.dict(app_module.GENERATORS, {test_type: generator}),
                    ):
                        response = app_module.app.test_client().post(
                            '/process',
                            data={
                                'test_type': test_type,
                                'language': 'en',
                                'pdf_files': [
                                    (BytesIO(b'%PDF-1.4'), 'AHU-33-valid.pdf'),
                                    (BytesIO(b'%PDF-1.4'), 'missing-ahu.pdf'),
                                ],
                            },
                            content_type='multipart/form-data',
                        )

                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertEqual(payload['ahu_list'], ['42'])
                self.assertEqual(list(generated['records']), ['42'])
                self.assertEqual(len(payload['warnings']), 1)
                self.assertIn('missing-ahu.pdf', payload['warnings'][0])
                self.assertIn('No valid AHU number', payload['warnings'][0])

    def test_fails_when_every_pdf_lacks_an_ahu_identity(self):
        def extractor(_path, api_key=None):
            return {
                'ahu': 'unknown',
                'date': '2025.08.01',
                'rooms': [{'room': 'test'}],
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(app_module, 'ANTHROPIC_API_KEY', 'test-key'),
                patch.object(app_module, 'UPLOAD_FOLDER', temp_dir),
                patch.object(app_module, 'OUTPUT_FOLDER', temp_dir),
                patch.dict(
                    app_module.CLAUDE_EXTRACTORS,
                    {'airborne_particle': extractor},
                ),
            ):
                response = app_module.app.test_client().post(
                    '/process',
                    data={
                        'test_type': 'airborne_particle',
                        'language': 'en',
                        'pdf_files': (BytesIO(b'%PDF-1.4'), 'missing-ahu.pdf'),
                    },
                    content_type='multipart/form-data',
                )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIn('Failed to extract data from all PDFs', payload['error'])
        self.assertIn('No valid AHU number', payload['error'])

    def test_merges_multiple_batches_before_generating_excel(self):
        generated = {}

        def extractor(path, api_key=None):
            ahu = '42' if 'first' in path else '43'
            return {
                'ahu': ahu,
                'date': '2025.08.01',
                'rooms': [{'room': ahu}],
            }

        def generator(records, output_path):
            generated['records'] = records

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(app_module, 'ANTHROPIC_API_KEY', 'test-key'),
                patch.object(app_module, 'UPLOAD_FOLDER', temp_dir),
                patch.object(app_module, 'OUTPUT_FOLDER', temp_dir),
                patch.dict(app_module.CLAUDE_EXTRACTORS, {'airborne_particle': extractor}),
                patch.dict(app_module.GENERATORS, {'airborne_particle': generator}),
            ):
                client = app_module.app.test_client()
                first = client.post(
                    '/process',
                    data={
                        'test_type': 'airborne_particle',
                        'language': 'en',
                        'batch_id': 'test-batch',
                        'batch_index': '0',
                        'batch_total': '2',
                        'pdf_files': (BytesIO(b'%PDF-1.4'), 'first.pdf'),
                    },
                    content_type='multipart/form-data',
                )
                second = client.post(
                    '/process',
                    data={
                        'test_type': 'airborne_particle',
                        'language': 'en',
                        'batch_id': 'test-batch',
                        'batch_index': '1',
                        'batch_total': '2',
                        'pdf_files': (BytesIO(b'%PDF-1.4'), 'second.pdf'),
                    },
                    content_type='multipart/form-data',
                )

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.get_json()['batch_complete'])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(sorted(generated['records']), ['42', '43'])
        self.assertEqual(second.get_json()['ahu_count'], 2)


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
