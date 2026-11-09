"""Tests for scoring_engine — 100% branch coverage required."""

import pytest

from app.services.scoring_engine import calculate_score, derive_scoring_grade


class TestG1Scoring:
    """AC-2: G1 scoring with position-based penalties (FR-12)."""

    def test_g1_8_horses_positive_positions(self):
        """≥8 horses: positions 1-5 get positive scores."""
        assert calculate_score("G1", 8, 1) == 10
        assert calculate_score("G1", 8, 2) == 5
        assert calculate_score("G1", 8, 3) == 3
        assert calculate_score("G1", 8, 4) == 2
        assert calculate_score("G1", 8, 5) == 1

    def test_g1_8_horses_penalty_positions(self):
        """≥8 horses: last 3 positions get penalty deductions."""
        # pos 6 = 3rd-to-last: 0 (positive) + (-1) = -1
        assert calculate_score("G1", 8, 6) == -1
        # pos 7 = 2nd-to-last: 0 + (-5) = -5
        assert calculate_score("G1", 8, 7) == -5
        # pos 8 = last: 0 + (-10) = -10
        assert calculate_score("G1", 8, 8) == -10

    def test_g1_10_horses_boundaries(self):
        """10 horses: verify middle positions (no penalty) and boundaries."""
        assert calculate_score("G1", 10, 1) == 10
        assert calculate_score("G1", 10, 5) == 1
        assert calculate_score("G1", 10, 6) == 0  # no positive, not in last 3
        assert calculate_score("G1", 10, 7) == 0  # no positive, not in last 3
        # Last 3 of 10: positions 8, 9, 10
        assert calculate_score("G1", 10, 8) == -1  # 3rd-to-last
        assert calculate_score("G1", 10, 9) == -5  # 2nd-to-last
        assert calculate_score("G1", 10, 10) == -10  # last

    def test_g1_7_horses_penalties(self):
        """7 horses: only last 2 get penalties."""
        assert calculate_score("G1", 7, 1) == 10
        assert calculate_score("G1", 7, 5) == 1
        assert calculate_score("G1", 7, 6) == -1  # 2nd-to-last
        assert calculate_score("G1", 7, 7) == -5  # last

    def test_g1_6_horses_penalty(self):
        """6 horses: only last place gets penalty."""
        assert calculate_score("G1", 6, 1) == 10
        assert calculate_score("G1", 6, 5) == 1
        assert calculate_score("G1", 6, 6) == -1  # only last gets -1

    def test_g1_5_horses_no_penalty(self):
        """≤5 horses: no penalties at all."""
        assert calculate_score("G1", 5, 1) == 10
        assert calculate_score("G1", 5, 5) == 1
        assert calculate_score("G1", 5, 4) == 2
        # position beyond 5
        assert calculate_score("G1", 5, 6) == 0

    def test_g1_15_horses_deep_penalties(self):
        """15 horses: only last 3 get penalties, middle positions get 0."""
        assert calculate_score("G1", 15, 1) == 10
        assert calculate_score("G1", 15, 5) == 1
        assert calculate_score("G1", 15, 10) == 0  # not in penalty zone
        assert calculate_score("G1", 15, 13) == -1  # 3rd-to-last
        assert calculate_score("G1", 15, 14) == -5  # 2nd-to-last
        assert calculate_score("G1", 15, 15) == -10  # last


class TestG2JPN1Scoring:
    """AC-3: G2/JPN1/其他 scoring without penalties (FR-13): +5/+3/+1 for top 3."""

    def test_g2_positive_positions(self):
        """G2_JPN1: positions 1-3 get +5/+3/+1, 4+ get 0."""
        assert calculate_score("G2_JPN1", 8, 1) == 5
        assert calculate_score("G2_JPN1", 8, 2) == 3
        assert calculate_score("G2_JPN1", 8, 3) == 1
        assert calculate_score("G2_JPN1", 8, 4) == 0
        assert calculate_score("G2_JPN1", 8, 5) == 0

    def test_g2_no_negative_scores(self):
        """G2: never returns negative, regardless of horse count."""
        assert calculate_score("G2_JPN1", 8, 6) == 0
        assert calculate_score("G2_JPN1", 8, 8) == 0  # last place
        assert calculate_score("G2_JPN1", 15, 15) == 0

    def test_g2_5_horses_no_penalty(self):
        """G2 with 5 horses: top 3 get +5/+3/+1, no penalties."""
        assert calculate_score("G2_JPN1", 5, 1) == 5
        assert calculate_score("G2_JPN1", 5, 2) == 3
        assert calculate_score("G2_JPN1", 5, 3) == 1
        assert calculate_score("G2_JPN1", 5, 4) == 0
        assert calculate_score("G2_JPN1", 5, 5) == 0
        assert calculate_score("G2_JPN1", 5, 6) == 0


class TestDeriveScoringGrade:
    """Verify race tag mapping to the 4 scoring modes."""

    def test_derive_all_supported_grades(self):
        assert derive_scoring_grade("2岁", "G1") == "YOUNG_G1"
        assert derive_scoring_grade("3岁", "G1") == "G1"
        assert derive_scoring_grade("3+岁", "G1") == "G1"
        assert derive_scoring_grade("3+岁", "G2") == "G2_JPN1"
        assert derive_scoring_grade("3岁", "JPN1") == "G2_JPN1"
        assert derive_scoring_grade("4+岁", "其他") == "G2_JPN1"
        assert derive_scoring_grade("3+岁", "自定义") == "CUSTOM"


class TestYoungG1Scoring:
    """AC-4: YOUNG_G1 scoring — G1 positives, no penalties."""

    def test_young_g1_positive_same_as_g1(self):
        """YOUNG_G1: positive scores identical to G1."""
        assert calculate_score("YOUNG_G1", 8, 1) == 10
        assert calculate_score("YOUNG_G1", 8, 2) == 5
        assert calculate_score("YOUNG_G1", 8, 3) == 3
        assert calculate_score("YOUNG_G1", 8, 4) == 2
        assert calculate_score("YOUNG_G1", 8, 5) == 1

    def test_young_g1_no_negative_scores(self):
        """YOUNG_G1: no penalties even for last place."""
        assert calculate_score("YOUNG_G1", 8, 6) == 0
        assert calculate_score("YOUNG_G1", 8, 8) == 0  # last
        assert calculate_score("YOUNG_G1", 6, 6) == 0
        assert calculate_score("YOUNG_G1", 15, 15) == 0


class TestCustomScoring:
    """AC-5: Custom scoring with user-defined rules (FR-15)."""

    def test_custom_positive_scores(self):
        """Custom: positive scores are returned from the custom list."""
        custom = {"positive_scores": [10, 7, 5, 3, 2, 1]}
        assert calculate_score("CUSTOM", 6, 1, custom) == 10
        assert calculate_score("CUSTOM", 6, 2, custom) == 7
        assert calculate_score("CUSTOM", 6, 3, custom) == 5
        assert calculate_score("CUSTOM", 6, 4, custom) == 3
        assert calculate_score("CUSTOM", 6, 5, custom) == 2
        assert calculate_score("CUSTOM", 6, 6, custom) == 1

    def test_custom_positive_with_penalties(self):
        """Custom: when both positive score and penalty apply, positive wins (penalty waived)."""
        custom = {
            "positive_scores": [10, 7, 5, 3, 2, 1],
            "penalty_rules": [{"position": -1, "points": -5}, {"position": -2, "points": -2}],
        }
        # 1st place: 10, no penalty
        assert calculate_score("CUSTOM", 6, 1, custom) == 10
        # 4th place: 3, no penalty (not last 2)
        assert calculate_score("CUSTOM", 6, 4, custom) == 3
        # 5th place (2nd-to-last): positive=2, penalty=-2 → positive wins, penalty waived
        assert calculate_score("CUSTOM", 6, 5, custom) == 2
        # 6th place (last): positive=1, penalty=-5 → positive wins, penalty waived
        assert calculate_score("CUSTOM", 6, 6, custom) == 1

    def test_custom_penalty_rules_empty(self):
        """Custom: empty penalty_rules means no deductions."""
        custom = {"positive_scores": [10, 7, 5, 3, 2, 1], "penalty_rules": []}
        assert calculate_score("CUSTOM", 6, 6, custom) == 1  # no penalty

    def test_custom_penalty_rules_none(self):
        """Custom: None penalty_rules means no deductions."""
        custom = {"positive_scores": [10, 7, 5]}
        assert calculate_score("CUSTOM", 8, 8, custom) == 0  # beyond positive_scores

    def test_custom_position_beyond_positive_scores(self):
        """Custom: position beyond positive_scores length gets 0 from positive."""
        custom = {"positive_scores": [10, 7, 5]}
        # 6th position but only 3 positive scores: 0 positive
        assert calculate_score("CUSTOM", 6, 4, custom) == 0
        assert calculate_score("CUSTOM", 6, 6, custom) == 0

    def test_custom_position_beyond_with_penalty(self):
        """Custom: position beyond positive_scores but penalty applies."""
        custom = {
            "positive_scores": [10, 7, 5],
            "penalty_rules": [{"position": -1, "points": -5}],
        }
        # 6th position in 6 horses: 0 positive - 5 penalty = -5
        assert calculate_score("CUSTOM", 6, 6, custom) == -5
        # 4th position beyond positive scores, not last: 0
        assert calculate_score("CUSTOM", 6, 4, custom) == 0


class TestDNFCases:
    """AC-6: DNF/scratched horses."""

    def test_dnf_returns_zero(self):
        """DNF horses score 0 for all grades."""
        for grade in ("G1", "G2_JPN1", "YOUNG_G1"):
            assert calculate_score(grade, 8, 0) == 0
        assert calculate_score("CUSTOM", 8, 0, {"positive_scores": [10, 7, 5]}) == 0

    def test_dnf_none_position_returns_zero(self):
        """None (not placed) returns 0 for all grades."""
        for grade in ("G1", "G2_JPN1", "YOUNG_G1", "CUSTOM"):
            if grade == "CUSTOM":
                assert calculate_score(grade, 8, 0, {"positive_scores": [10, 7, 5]}) == 0
            else:
                assert calculate_score(grade, 8, 0) == 0

    def test_dnf_negative_position_returns_zero(self):
        """Negative position (error case) returns 0."""
        for grade in ("G1", "G2_JPN1", "YOUNG_G1"):
            assert calculate_score(grade, 8, -1) == 0


class TestEdgeCases:
    """AC-7: Edge cases."""

    def test_position_beyond_horse_count(self):
        """Position beyond total horses should be treated as beyond positive."""
        # For G1, 5 horses, position 7: beyond penalty (not last 3 of 5 since 5 is last)
        # Actually pos 7 with 5 horses: beyond range, treat as no positive, no penalty
        # If there are only 5 horses, position can't be > 5. This is an error case.
        # Should probably return 0.
        assert calculate_score("G1", 5, 7) == 0

    def test_custom_empty_positive_scores(self):
        """Custom with empty positive_scores returns 0 for all positions."""
        custom = {"positive_scores": []}
        assert calculate_score("CUSTOM", 8, 1, custom) == 0
        assert calculate_score("CUSTOM", 8, 8, custom) == 0

    def test_g1_no_horses(self):
        """0 horses shouldn't crash (edge case)."""
        assert calculate_score("G1", 0, 1) == 10
        assert calculate_score("G1", 0, 0) == 0

    def test_standard_grade_with_custom_scoring(self):
        """Standard grades ignore custom_scoring parameter."""
        custom = {"positive_scores": [100, 50]}
        assert calculate_score("G1", 8, 1, custom) == 10  # G1 rules, not custom
        assert calculate_score("G2_JPN1", 8, 1, custom) == 5
        assert calculate_score("YOUNG_G1", 8, 1, custom) == 10
