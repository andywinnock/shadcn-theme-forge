import unittest

from oklch import css_color_to_hex, oklch_to_hex


class OklchConversionTests(unittest.TestCase):
    def test_converts_neutral_black(self):
        self.assertEqual(oklch_to_hex(0, 0, 0), "#000000")

    def test_converts_neutral_white(self):
        self.assertEqual(oklch_to_hex(1, 0, 0), "#ffffff")

    def test_parses_percentage_lightness_and_alpha(self):
        self.assertEqual(css_color_to_hex("oklch(100% 0 0 / 50%)"), "#ffffff80")

    def test_preserves_hex_colors_in_lowercase(self):
        self.assertEqual(css_color_to_hex("  #AbCdEf80 "), "#abcdef80")

    def test_returns_none_for_unsupported_hsl(self):
        self.assertIsNone(css_color_to_hex("hsl(0 0% 0% / 10%)"))


if __name__ == "__main__":
    unittest.main()
