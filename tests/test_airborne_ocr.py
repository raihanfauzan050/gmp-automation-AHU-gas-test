import unittest
from unittest.mock import patch

from PIL import Image

from ocr_engine import extract_airborne_particle


class AirborneParticleOcrTest(unittest.TestCase):
    @patch('ocr_engine.call_claude_api')
    @patch('ocr_engine.pdf_to_images')
    def test_uses_printed_measurement_date_instead_of_wrong_full_page_date(
        self, pdf_to_images, call_claude_api,
    ):
        pdf_to_images.return_value = [Image.new('RGB', (1000, 700), 'white')]
        call_claude_api.side_effect = [
            {'ahu': '2', 'date': '2024.08.27', 'rooms': [{'room_number': '2404'}]},
            {'date': '2025.08.12'},
        ]

        result = extract_airborne_particle('/tmp/ahu-2.pdf', api_key='test-key')

        self.assertEqual(result['date'], '2025.08.12')
        self.assertEqual(len(result['rooms']), 1)
        self.assertEqual(call_claude_api.call_count, 2)
        self.assertEqual(len(call_claude_api.call_args.args[0]), 1)
        self.assertIn('측정일자', call_claude_api.call_args.args[1])

    @patch('ocr_engine.call_claude_api')
    @patch('ocr_engine.pdf_to_images')
    def test_rejects_unreadable_printed_date(self, pdf_to_images, call_claude_api):
        pdf_to_images.return_value = [Image.new('RGB', (1000, 700), 'white')]
        call_claude_api.side_effect = [
            {'ahu': '2', 'date': '2024.08.27', 'rooms': [{'room_number': '2404'}]},
            {'date': ''},
        ]

        with self.assertRaisesRegex(ValueError, 'measurement date'):
            extract_airborne_particle('/tmp/ahu-2.pdf', api_key='test-key')


if __name__ == '__main__':
    unittest.main()
