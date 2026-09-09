import unittest
from unittest.mock import patch

from PIL import Image

from ocr_engine import extract_gas_airborne_particle


class GasAirborneParticleOcrTest(unittest.TestCase):
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
