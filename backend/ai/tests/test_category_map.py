import pytest

from ai.category_map import QUEUE_TO_CATEGORY, map_queue_to_category
from tickets.management.commands.seed import TEAMS_AND_CATEGORIES

SEEDED_CATEGORY_NAMES = {name for categories in TEAMS_AND_CATEGORIES.values() for name, _ in categories}


def test_every_mapped_category_exists_in_seed_data():
    for category in QUEUE_TO_CATEGORY.values():
        assert category in SEEDED_CATEGORY_NAMES


@pytest.mark.parametrize("queue", list(QUEUE_TO_CATEGORY))
def test_known_queue_maps_to_a_category(queue):
    assert map_queue_to_category(queue) is not None


def test_unknown_queue_returns_none():
    assert map_queue_to_category("Some Unmapped Queue") is None
