"""
Permission Constants and Tier Hierarchy Specifications

Defines data structures for:
1. Base tier managing rules (which tiers can manage which subordinate tiers)
2. Dynamic authority bumping rules
"""

# Base tier managing rules: maps managing tier -> set of subordinate tiers it can manage
BASE_TIER_MANAGING_RULES: dict[int, set[int]] = {
    1: {1, 2, 3, 4},  # Tier 1 can manage all tiers
    2: {3, 4},        # Tier 2 can manage Tiers 3 and 4
    # Tier 3 and 4 removed - cannot manage anyone
}

# Dynamic authority bumping rules:
# Tier 3 and 4 never bump - always remain low-level
TIER_BUMPING_RULES: dict[int, int] = {
    2: 2,  # Tier 2 stays Tier 2 (no bumping needed)
}
