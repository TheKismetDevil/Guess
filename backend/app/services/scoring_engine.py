"""Pure-function scoring engine — zero external dependencies.

Supports 4 race-grade rule types:
- G1: G1 positive scores + tiered end-position penalties
- G2_JPN1: G2 positive scores, no penalties
- YOUNG_G1: G1 positive scores, no penalties
- CUSTOM: user-defined positive scores + optional penalties

This module MUST remain pure — no FastAPI, no SQLAlchemy, no DB imports.
"""

from typing import Any

# Positive score tables (1-indexed: position -> points)
_G1_POSITIVE: dict[int, int] = {1: 10, 2: 5, 3: 3, 4: 2, 5: 1}
_G2_POSITIVE: dict[int, int] = {1: 5, 2: 3, 3: 1}

# G1 penalty configuration per horse-count tier
# key: min_horses → list of (offset_from_end, penalty_points)
_G1_PENALTY_TIERS: list[tuple[int, list[tuple[int, int]]]] = [
    (8, [(-1, -10), (-2, -5), (-3, -1)]),  # ≥8: last 3
    (7, [(-1, -5), (-2, -1)]),             # 7: last 2
    (6, [(-1, -1)]),                       # 6: last only
    (0, []),                               # ≤5: no penalty
]


def _get_g1_penalty_rules(total_horses: int) -> list[tuple[int, int]]:
    """Get G1 penalty rules for the given horse count tier.

    Args:
        total_horses: Number of active (non-DNF) horses in the race.

    Returns:
        List of (offset_from_end, penalty_points) tuples.
        offset_from_end is negative (e.g., -1 = last, -2 = 2nd-to-last).
    """
    for min_horses, rules in _G1_PENALTY_TIERS:
        if total_horses >= min_horses:
            return rules
    return []


def _get_positive_score(
    grade: str, position: int, custom_scores: list[int] | None
) -> int:
    """Get the positive score for a position in the given grade.

    Args:
        grade: "G1", "G2_JPN1", "YOUNG_G1", or "CUSTOM".
        position: 1-indexed final position.
        custom_scores: Custom positive scores list (used only for CUSTOM grade).

    Returns:
        Positive score for the position, or 0 if position earns no positive points.
    """
    if grade == "CUSTOM":
        if not custom_scores:
            return 0
        idx = position - 1  # convert to 0-indexed
        if 0 <= idx < len(custom_scores):
            return custom_scores[idx]
        return 0

    if grade == "G2_JPN1":
        return _G2_POSITIVE.get(position, 0)

    # G1 and YOUNG_G1 share the same positive table
    return _G1_POSITIVE.get(position, 0)


def _get_penalty_score(
    grade: str, total_horses: int, position: int, custom_penalty_rules: list[dict[str, Any]] | None
) -> int:
    """Get the penalty deduction for a position in the given grade.

    Args:
        grade: "G1", "G2_JPN1", "YOUNG_G1", or "CUSTOM".
        total_horses: Total active (non-DNF) horses.
        position: 1-indexed final position.
        custom_penalty_rules: Custom penalty rules (used only for CUSTOM grade).

    Returns:
        Penalty deduction (negative or zero).
    """
    if grade == "CUSTOM" and custom_penalty_rules:
        # Custom penalty rules: position is relative to end (negative: -1 = last)
        total_penalty = 0
        for rule in custom_penalty_rules:
            rel_pos = rule["position"]  # negative, e.g., -1 = last
            points = rule["points"]
            # Convert relative position to absolute
            # rel_pos=-1 → last position = total_horses
            # rel_pos=-2 → total_horses - 1, etc.
            abs_position = total_horses + rel_pos + 1
            if position == abs_position:
                total_penalty += points
        return total_penalty

    if grade == "G1":
        rules = _get_g1_penalty_rules(total_horses)
        for offset, points in rules:
            # offset is negative (e.g., -1 = last place = position total_horses)
            penalty_position = total_horses + offset + 1
            if position == penalty_position:
                return points

    # G2_JPN1 and YOUNG_G1 have no penalties; custom without rules also none
    return 0


def derive_scoring_grade(age_range: str, race_grade: str) -> str:
    """Derive the scoring grade from race tags.

    Maps the new 5-tag system to the original 4 scoring modes.

    Args:
        age_range: Age range tag ("2岁", "2+岁", "3岁", "3+岁", "4+岁", "其他").
        race_grade: Race grade tag ("G1", "G2", "JPN1", "其他", "自定义").

    Returns:
        One of "G1", "G2_JPN1", "YOUNG_G1", "CUSTOM".
    """
    if race_grade == "自定义":
        return "CUSTOM"
    if age_range == "2岁" and race_grade == "G1":
        return "YOUNG_G1"
    if race_grade not in ("G1", "自定义"):
        return "G2_JPN1"
    return "G1"


def calculate_score(
    grade: str,
    total_horses: int,
    position: int,
    custom_scoring: dict[str, Any] | None = None,
) -> int:
    """Calculate points for a user's vote.

    Pure function. No side effects, no external dependencies.

    Args:
        grade: Race grade — "G1", "G2_JPN1", "YOUNG_G1", or "CUSTOM".
        total_horses: Total number of ACTIVE (non-DNF) horses in the race.
            DNF/scratched horses must be excluded by the caller.
        position: Final position of the horse the user voted for (1-indexed).
            Use 0 or negative for DNF/scratched horses.
        custom_scoring: Required when grade == "CUSTOM", otherwise ignored.
            Shape: {"positive_scores": [int, ...], "penalty_rules": [{"position": int, "points": int}]}

    Returns:
        Net points for the user's vote (may be negative for G1 penalties).
    """
    # DNF / scratched: score 0
    if position <= 0:
        return 0

    # Extract custom scoring data (only used for CUSTOM grade)
    custom_scores: list[int] | None = None
    custom_penalty: list[dict[str, Any]] | None = None
    if grade == "CUSTOM" and custom_scoring is not None:
        custom_scores = custom_scoring.get("positive_scores", [])
        custom_penalty = custom_scoring.get("penalty_rules", None)

    # Calculate positive score
    positive = _get_positive_score(grade, position, custom_scores)

    # Calculate penalty (negative deduction)
    penalty = _get_penalty_score(grade, total_horses, position, custom_penalty)

    # Same principle as G1: a position never gets both positive score and penalty.
    # If both apply, positive score wins (penalty is waived).
    if positive > 0 and penalty < 0:
        return positive

    return positive + penalty
