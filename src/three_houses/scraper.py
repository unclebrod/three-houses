"""Scraper class for Three Houses data."""

import json
import time
from collections.abc import Callable
from typing import Literal, TypeVar, get_args

from pydantic import BaseModel
from selectolax.lexbor import LexborHTMLParser

from three_houses import parsers
from three_houses.client import Client
from three_houses.log import logger
from three_houses.settings import DATA_DIR

ENDPOINTS = Literal[
    "base_stats",
    "budding_talents",
    "characters",
    "crests",
    "dining_hall",
    "faculty_training",
    "gifts",
    "growth_rates",
    "learned_abilities",
    "learned_spells",
    "maximum_stats",
    "other_data",
    "recruitment",
    "skill_levels",
    "seminars",
    "supports",
    "tea_party",
]

T = TypeVar("T", bound=BaseModel)
ParserReturn = list[T] | tuple[list[T], ...]


class ScraperConfig(BaseModel):
    """Configuration for a scraping task."""

    url: str
    endpoints: list[str]
    parser: Callable[[LexborHTMLParser], ParserReturn]


BASE_STATS_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/characters/base-stats/",
    endpoints=["base_stats"],
    parser=parsers.parse_stats,
)
BUDDING_TALENTS_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/characters/budding-talents/",
    endpoints=["budding_talents"],
    parser=parsers.parse_budding_talents,
)
CHARACTERS_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/characters/",
    endpoints=["characters"],
    parser=parsers.parse_characters,
)
CRESTS_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/characters/crests/",
    endpoints=["crests_general_info", "crests_activation_rates"],
    parser=parsers.parse_crests,
)
DINING_HALL_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/monastery/dining-hall/",
    endpoints=["full_menu", "cooking_together", "liked_meals", "disliked_meals"],
    parser=parsers.parse_dining_hall,
)
FAULTY_TRAINING_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/monastery/faculty-training/",
    endpoints=["available_instructors", "advanced_drills"],
    parser=parsers.parse_faculty_training,
)
GIFTS_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/monastery/gifts-lost-items/",
    endpoints=["liked_gifts", "disliked_gifts", "lost_items"],
    parser=parsers.parse_gifts,
)
GROWTH_RATES_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/characters/growth-rates/",
    endpoints=["growth_rates"],
    parser=parsers.parse_stats,
)
LEARNED_ABILITIES_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/characters/learned-abilities-arts/",
    endpoints=[
        "learned_universal",
        "learned_dependent_abilities",
        "learned_dependent_arts",
    ],
    parser=parsers.parse_learned_abilities,
)
LEARNED_SPELLS_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/characters/learned-spells/",
    endpoints=["learned_spells"],
    parser=parsers.parse_learned_spells,
)
MAXIMUM_STATS_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/characters/maximum-stats/",
    endpoints=["maximum_stats"],
    parser=parsers.parse_stats,
)
OTHER_DATA_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/characters/other-data/",
    endpoints=["classes_and_crests", "ages_and_heights"],
    parser=parsers.parse_other_data,
)
RECRUITMENT_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/characters/recruitment/",
    endpoints=["recruitment"],
    parser=parsers.parse_recruitment,
)
SEMINARS_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/monastery/seminars/",
    endpoints=["seminars"],
    parser=parsers.parse_seminars,
)
SKILL_LEVELS_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/characters/skill-levels/",
    endpoints=["skill_proficiencies", "skill_initial_levels"],
    parser=parsers.parse_skill_levels,
)
SUPPORT_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses-support-conversations/",
    endpoints=["supports"],
    parser=parsers.parse_supports,
)
TEA_PARTY_CONFIG = ScraperConfig(
    url="https://serenesforest.net/three-houses/monastery/tea-party/",
    endpoints=["tea_party"],
    parser=parsers.parse_tea_party,
)


ENDPOINT_SCRAPER_MAP: dict[ENDPOINTS, ScraperConfig] = {
    "base_stats": BASE_STATS_CONFIG,
    "budding_talents": BUDDING_TALENTS_CONFIG,
    "characters": CHARACTERS_CONFIG,
    "crests": CRESTS_CONFIG,
    "dining_hall": DINING_HALL_CONFIG,
    "faculty_training": FAULTY_TRAINING_CONFIG,
    "gifts": GIFTS_CONFIG,
    "growth_rates": GROWTH_RATES_CONFIG,
    "learned_abilities": LEARNED_ABILITIES_CONFIG,
    "learned_spells": LEARNED_SPELLS_CONFIG,
    "maximum_stats": MAXIMUM_STATS_CONFIG,
    "other_data": OTHER_DATA_CONFIG,
    "recruitment": RECRUITMENT_CONFIG,
    "seminars": SEMINARS_CONFIG,
    "skill_levels": SKILL_LEVELS_CONFIG,
    "supports": SUPPORT_CONFIG,
    "tea_party": TEA_PARTY_CONFIG,
}


class Scraper:
    """Scraper class."""

    def __init__(
        self,
        endpoints: list[ENDPOINTS] | None = None,
        client: Client | None = None,
    ) -> None:
        """Initialize the Scraper."""
        self.endpoints = endpoints or list(get_args(ENDPOINTS))
        self.client = client or Client()
        self.mapper = ENDPOINT_SCRAPER_MAP

    def scrape(self, *, save: bool = True) -> None:
        for endpoint in self.endpoints:
            config = self.mapper.get(endpoint)
            if config is None:
                logger.warning(f"No scraper config found for endpoint: {endpoint}")
                continue
            response = self.client.get(config.url)
            html_parser = LexborHTMLParser(response.text)
            models = config.parser(html_parser)
            if not isinstance(models, tuple):
                models = (models,)
            if save:
                for m, e in zip(models, config.endpoints, strict=True):
                    output_path = DATA_DIR / f"{e}.json"
                    DATA_DIR.mkdir(parents=True, exist_ok=True)
                    with output_path.open("w", encoding="utf-8") as f:
                        json.dump([x.model_dump(mode="json") for x in m], f, indent=4)
                    logger.info(f"Saved data for endpoint '{e}' to {output_path}")
            time.sleep(1)  # be polite and avoid overwhelming the server
