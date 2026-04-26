import pytest
from core.models import TrackedGame


class TestTrackedGame:
    def test_from_raw_dict(self):
        """Test creating TrackedGame from dict."""
        raw = {
            "title": "Test Game",
            "date": "01.01.2023",
            "image_url": "https://example.com/image.jpg",
            "last_scanned": "2023-01-01T00:00:00"
        }
        game = TrackedGame.from_raw(raw)
        assert game.title == "Test Game"
        assert game.date == "01.01.2023"
        assert game.image_url == "https://example.com/image.jpg"
        assert game.last_scanned == "2023-01-01T00:00:00"

    def test_from_raw_tracked_game(self):
        """Test from_raw with existing TrackedGame."""
        original = TrackedGame("Test", "01.01.2023", "img", "scan")
        game = TrackedGame.from_raw(original)
        assert game is original

    def test_from_raw_string(self):
        """Test from_raw with string (date)."""
        raw = "01.01.2023"
        game = TrackedGame.from_raw(raw)
        assert game.title == "Unknown"
        assert game.date == "01.01.2023"
        assert game.image_url == "N/A"
        assert game.last_scanned == ""

    def test_from_raw_invalid_string(self):
        """Test from_raw with invalid string."""
        raw = "not a date"
        game = TrackedGame.from_raw(raw)
        assert game.title == "Unknown"
        assert game.date == "N/A"

    def test_to_dict(self):
        """Test converting to dict."""
        game = TrackedGame("Test", "01.01.2023", "img", "scan")
        expected = {
            "title": "Test",
            "date": "01.01.2023",
            "image_url": "img",
            "last_scanned": "scan"
        }
        assert game.to_dict() == expected

    def test_looks_like_date_valid(self):
        """Test _looks_like_date with valid date."""
        assert TrackedGame._looks_like_date("01.01.2023") is True

    def test_looks_like_date_invalid(self):
        """Test _looks_like_date with invalid date."""
        assert TrackedGame._looks_like_date("not a date") is False

    def test_from_raw_invalid_type(self):
        """Test from_raw with invalid type."""
        with pytest.raises(TypeError):
            TrackedGame.from_raw(123)