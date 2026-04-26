from datetime import datetime, timedelta

from core.models import TrackedGame
from core.updater import IOPUpdater


class TestIOPUpdater:
    def test_needs_deep_check_when_date_unknown(self):
        updater = IOPUpdater(channel_id=123)
        game = TrackedGame(title='Unknown Game', date='N/A', image_url='N/A', last_scanned='')
        assert updater._needs_deep_check(game, datetime.now()) is True

    def test_needs_deep_check_when_last_scanned_old(self):
        updater = IOPUpdater(channel_id=123)
        last_scanned = (datetime.now() - timedelta(days=8)).isoformat()
        game = TrackedGame(title='Old Game', date='01.01.2025', image_url='N/A', last_scanned=last_scanned)
        assert updater._needs_deep_check(game, datetime.now()) is True

    def test_needs_deep_check_when_recently_scanned(self):
        updater = IOPUpdater(channel_id=123)
        last_scanned = (datetime.now() - timedelta(days=2)).isoformat()
        game = TrackedGame(title='Recent Game', date='01.01.2025', image_url='N/A', last_scanned=last_scanned)
        assert updater._needs_deep_check(game, datetime.now()) is False

    def test_find_deep_check_candidates_respects_interval(self):
        updater = IOPUpdater(channel_id=123)
        now = datetime.now()
        game = TrackedGame(title='Recent Game', date='01.01.2025', image_url='N/A', last_scanned=(now - timedelta(days=8)).isoformat())
        tracked_games = {'https://island-of-pleasure.site/games/test.html': game}

        candidate_urls = updater._find_deep_check_candidates(tracked_games, now)
        assert candidate_urls == ['https://island-of-pleasure.site/games/test.html']

        updater.last_deep_check_time[candidate_urls[0]] = now
        candidate_urls_after = updater._find_deep_check_candidates(tracked_games, now)
        assert candidate_urls_after == []
