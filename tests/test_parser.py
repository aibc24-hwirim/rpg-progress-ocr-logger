from __future__ import annotations

import unittest

from rpg_progress_ocr_logger.models import OcrBlock
from rpg_progress_ocr_logger.parser import parse_progress_records


class ParserTest(unittest.TestCase):
    def test_parse_multiple_character_records(self) -> None:
        records = parse_progress_records(
            "2026-06-27T02:00:00+09:00",
            [
                OcrBlock("Character: Aria", 0.98),
                OcrBlock("Activity: Elder Rift", 0.95),
                OcrBlock("Reward: Legendary Gem", 0.93),
                OcrBlock("Progress: 3/5", 0.91),
                OcrBlock("Character: Noah", 0.96),
                OcrBlock("Activity: Bounty", 0.90),
                OcrBlock("Reward: Gold 12000", 0.83),
                OcrBlock("Progress: 4/8", 0.84),
            ],
        )

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].character, "Aria")
        self.assertEqual(records[0].status, "ok")
        self.assertEqual(records[1].activity, "Bounty")

    def test_missing_reward_needs_review(self) -> None:
        records = parse_progress_records(
            "2026-06-27T02:00:00+09:00",
            [
                OcrBlock("Character: Luna", 0.78),
                OcrBlock("Activity: Hidden Lair", 0.70),
                OcrBlock("Progress: 1/3", 0.36),
            ],
        )

        self.assertEqual(records[0].status, "needs_review")
        self.assertIn("missing reward", records[0].notes)


if __name__ == "__main__":
    unittest.main()
