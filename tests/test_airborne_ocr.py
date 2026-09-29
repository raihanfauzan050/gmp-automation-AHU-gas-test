import unittest
import base64
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from ocr_engine import PROMPT_AIRBORNE_PARTICLE, extract_airborne_particle, image_to_base64


class AirborneParticleOcrTest(unittest.TestCase):
    def test_requests_unrounded_measurement_values(self):
        self.assertIn('Preserve every printed decimal digit', PROMPT_AIRBORNE_PARTICLE)
        self.assertIn('211281.8', PROMPT_AIRBORNE_PARTICLE)

    def test_large_images_fit_anthropic_multi_image_limit_without_changing_source(self):
        source = Image.new('RGB', (2200, 2600), 'white')

        encoded = image_to_base64(source)
        with Image.open(BytesIO(base64.b64decode(encoded))) as sent:
            self.assertLessEqual(max(sent.size), 2000)
            self.assertEqual(sent.size, (1692, 2000))
        self.assertEqual(source.size, (2200, 2600))

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

    @patch('ocr_engine.call_claude_api')
    @patch('ocr_engine.pdf_to_images')
    def test_checks_grade_b_against_clearer_image_before_writing_excel(self, pdf_to_images, call_claude_api):
        pdf_to_images.side_effect = [
            [Image.new('RGB', (1000, 700), 'white')],
            [Image.new('RGB', (1600, 1120), 'white')],
        ]
        call_claude_api.side_effect = [
            {'ahu': '2', 'rooms': [
                {'grade': 'B', 'room_number': '2401', 'room_name': '혼합', 'measurements': []},
                {'grade': 'B', 'room_number': '2402', 'room_name': '포장', 'measurements': []},
            ]},
            {'grades': [{'room_number': '2401', 'grade': 'D'}, {'room_number': '2402', 'grade': 'B'}]},
            {'date': '2025.08.12'},
        ]

        result = extract_airborne_particle('/tmp/ahu-2.pdf', api_key='test-key')

        self.assertEqual([room['grade'] for room in result['rooms']], ['D', 'B'])
        pdf_to_images.assert_any_call('/tmp/ahu-2.pdf', dpi=250)
        self.assertIn('2401', call_claude_api.call_args_list[1].args[1])

    @patch('ocr_engine.call_claude_api')
    @patch('ocr_engine.pdf_to_images')
    def test_does_not_guess_unclear_grade(self, pdf_to_images, call_claude_api):
        pdf_to_images.side_effect = [
            [Image.new('RGB', (1000, 700), 'white')],
            [Image.new('RGB', (1600, 1120), 'white')],
        ]
        call_claude_api.side_effect = [
            {'ahu': '2', 'rooms': [{'grade': 'B', 'room_number': '2401', 'room_name': '혼합'}]},
            {'grades': [{'room_number': '2401', 'grade': 'unknown'}]},
        ]

        with self.assertRaisesRegex(ValueError, 'cleanroom grade'):
            extract_airborne_particle('/tmp/ahu-2.pdf', api_key='test-key')


if __name__ == '__main__':
    unittest.main()
