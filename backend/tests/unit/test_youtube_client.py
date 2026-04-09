"""Unit tests for YouTube client utility functions.

Pure function tests — no DB, no async, no fixtures needed.
"""

from app.services.youtube_client import parse_chapters, parse_duration_to_seconds


class TestParseDuration:
    def test_hours_minutes_seconds(self):
        # ACT
        result = parse_duration_to_seconds("PT1H23M45S")

        # ASSERT
        assert result == 5025

    def test_minutes_seconds(self):
        # ACT
        result = parse_duration_to_seconds("PT45M30S")

        # ASSERT
        assert result == 2730

    def test_hours_only(self):
        # ACT
        result = parse_duration_to_seconds("PT2H")

        # ASSERT
        assert result == 7200

    def test_seconds_only(self):
        # ACT
        result = parse_duration_to_seconds("PT30S")

        # ASSERT
        assert result == 30

    def test_invalid_format(self):
        # ACT
        result = parse_duration_to_seconds("not-a-duration")

        # ASSERT
        assert result == 0

    def test_empty_string(self):
        # ACT
        result = parse_duration_to_seconds("")

        # ASSERT
        assert result == 0


class TestParseChapters:
    def test_standard_timestamps(self):
        # ARRANGE
        description = "0:00 First Song\n3:45 Second Song\n7:20 Third Song"

        # ACT
        chapters = parse_chapters(description)

        # ASSERT
        assert chapters is not None
        assert len(chapters) == 3
        assert chapters[0].time == 0
        assert chapters[0].title == "First Song"
        assert chapters[1].time == 225
        assert chapters[2].time == 440

    def test_hour_format(self):
        # ARRANGE
        description = "0:00 Intro\n1:00:00 Middle\n2:30:00 End"

        # ACT
        chapters = parse_chapters(description)

        # ASSERT
        assert chapters is not None
        assert chapters[1].time == 3600
        assert chapters[2].time == 9000

    def test_fewer_than_three_returns_none(self):
        # ARRANGE
        description = "0:00 Only One\n3:00 Only Two"

        # ACT & ASSERT
        assert parse_chapters(description) is None

    def test_none_input(self):
        # ACT & ASSERT
        assert parse_chapters(None) is None

    def test_no_timestamps(self):
        # ACT & ASSERT
        assert parse_chapters("Just a regular description with no timestamps") is None
