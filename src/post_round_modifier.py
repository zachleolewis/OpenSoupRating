def apply_post_round_modifier(impact: float, time_since_round_start: int) -> float:
    # Apply post-round modifier.
    # If kill after round end (~100s), lessen impact.
    if time_since_round_start > 100000:
        return impact * 0.5
    return impact
