import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

import ocr_engine
from ocr_engine import extract_gas_airborne_particle


class GasAirborneParticleOcrTest(unittest.TestCase):
    @patch('ocr_engine.time.sleep')
    @patch('ocr_engine.requests.post')
    def test_retries_rate_limit_once(self, post, sleep):
        limited = SimpleNamespace(status_code=429, headers={'retry-after': '3'}, text='rate limit')
        valid = SimpleNamespace(
            status_code=200,
            json=lambda: {'content': [{'type': 'text', 'text': '{"records":[]}'}]},
        )
        post.side_effect = [limited, valid]

        result = ocr_engine.call_claude_api(['image'], 'Return JSON', api_key='test-key')

        self.assertEqual(result, {'records': []})
        sleep.assert_called_once_with(3.0)
        self.assertEqual(post.call_count, 2)

    def test_rejects_unreadable_measurement_instead_of_inventing_zero(self):
        row = {
            'no': '1', 'management_number': 'CA-01', 'location': '충전 3실',
            'grade': 'B', 'particle_05': 13, 'particle_50': None,
            'judgement': '적합', 'performed_date': '2025.08.28',
        }
        with self.assertRaisesRegex(ValueError, 'particle_50'):
            ocr_engine._normalize_gas_airborne_data({'records': [row]})

    def test_rejects_unreadable_judgement_instead_of_assuming_pass(self):
        row = {
            'no': '1', 'management_number': 'CA-01', 'location': '충전 3실',
            'grade': 'B', 'particle_05': 13, 'particle_50': 0,
            'judgement': '', 'performed_date': '2025.08.28',
        }
        with self.assertRaisesRegex(ValueError, 'judgement'):
            ocr_engine._normalize_gas_airborne_data({'records': [row]})

    @patch('ocr_engine.requests.post')
    def test_retries_when_claude_returns_invalid_json(self, post):
        invalid = SimpleNamespace(
            status_code=200,
            json=lambda: {'content': [{'type': 'text', 'text': '{ invalid'}]},
        )
        valid = SimpleNamespace(
            status_code=200,
            json=lambda: {'content': [{'type': 'text', 'text': '{"ahu":"1"}'}]},
        )
        post.side_effect = [invalid, valid]

        result = ocr_engine.call_claude_api(['image'], 'Return JSON', api_key='test-key')

        self.assertEqual(result, {'ahu': '1'})
        self.assertEqual(post.call_count, 2)
        retry_content = post.call_args.kwargs['json']['messages'][0]['content'][-1]['text']
        self.assertIn('previous JSON output was invalid', retry_content)

    @patch('ocr_engine.call_claude_api')
    @patch('ocr_engine.pdf_to_images')
    def test_uses_enhanced_table_and_date_crops(self, pdf_to_images, call_claude_api):
        pdf_to_images.return_value = [Image.new('RGB', (100, 200), 'white')]
        call_claude_api.return_value = {
            'records': [{
                'no': 1,
                'management_number': 'CA-01',
                'location': '충전 3실 (2505)',
                'grade': 'b',
                'particle_05': '13',
                'particle_50': '0',
                'judgement': '적합',
                'criteria_text': '허용기준',
                'performed_date': '2025-8-28',
            }],
        }

        result = extract_gas_airborne_particle('/tmp/gas.pdf', api_key='test-key')

        pdf_to_images.assert_called_once_with('/tmp/gas.pdf', dpi=200)
        images = call_claude_api.call_args.args[0]
        descriptions = call_claude_api.call_args.kwargs['image_descriptions']
        self.assertEqual(len(images), 3)
        self.assertEqual(len(descriptions), 3)
        self.assertEqual(result['records'][0]['grade'], 'B')
        self.assertEqual(result['records'][0]['particle_05'], 13)
        self.assertEqual(result['records'][0]['performed_date'], '2025.08.28')


if __name__ == '__main__':
    unittest.main()
