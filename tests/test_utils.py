import pytest
from core.utils import normalize_game_url


class TestNormalizeGameUrl:
    def test_normalize_https_url(self):
        """Test normalizing a full HTTPS URL."""
        url = "https://island-of-pleasure.site/games/game1.html"
        expected = "https://island-of-pleasure.site/games/game1.html"
        assert normalize_game_url(url) == expected

    def test_add_https_scheme(self):
        """Test adding HTTPS scheme if missing."""
        url = "island-of-pleasure.site/games/game1.html"
        expected = "https://island-of-pleasure.site/games/game1.html"
        assert normalize_game_url(url) == expected

    def test_remove_www(self):
        """Test removing www from netloc."""
        url = "https://www.island-of-pleasure.site/games/game1.html"
        expected = "https://island-of-pleasure.site/games/game1.html"
        assert normalize_game_url(url) == expected

    def test_normalize_path_trailing_slash(self):
        """Test normalizing path by removing trailing slash."""
        url = "https://island-of-pleasure.site/games/game1.html/"
        expected = "https://island-of-pleasure.site/games/game1.html"
        assert normalize_game_url(url) == expected

    def test_empty_path_to_root(self):
        """Test converting empty path to root."""
        url = "https://island-of-pleasure.site"
        expected = "https://island-of-pleasure.site/"
        assert normalize_game_url(url) == expected

    def test_strip_whitespace(self):
        """Test stripping leading/trailing whitespace."""
        url = "  https://island-of-pleasure.site/games/game1.html  "
        expected = "https://island-of-pleasure.site/games/game1.html"
        assert normalize_game_url(url) == expected

    def test_empty_string(self):
        """Test handling empty string."""
        url = ""
        expected = ""
        assert normalize_game_url(url) == expected