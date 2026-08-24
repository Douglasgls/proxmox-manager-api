import unittest
from app.core.hostname import normalize_hostname


class TestNormalizeHostname(unittest.TestCase):

    def test_basic_normalization(self):
        self.assertEqual(normalize_hostname("Meu App API"), "meu-app-api")

    def test_accented_characters(self):
        self.assertEqual(normalize_hostname("Aplicação Web São Paulo"), "aplicacao-web-sao-paulo")

    def test_special_characters_and_dashes(self):
        self.assertEqual(normalize_hostname("App!! -- Teste_1"), "app-teste-1")

    def test_leading_trailing_dashes(self):
        self.assertEqual(normalize_hostname("---meu-app---"), "meu-app")

    def test_max_length(self):
        long_name = "a" * 100
        normalized = normalize_hostname(long_name)
        self.assertEqual(len(normalized), 63)
        self.assertEqual(normalized, "a" * 63)

    def test_empty_or_none(self):
        self.assertEqual(normalize_hostname(""), "ct-node")
        self.assertEqual(normalize_hostname(None), "ct-node")
        self.assertEqual(normalize_hostname("!!!"), "ct-node")


if __name__ == "__main__":
    unittest.main()
