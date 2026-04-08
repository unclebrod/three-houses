"""Data models for Three Houses."""

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_parentheses(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*", "", text).strip()


class Stats(BaseModel):
    """Stats for a character in Three Houses."""

    name: str = Field(alias="Name")
    house: str
    hp: int = Field(alias="HP")
    strength: int = Field(alias="Str")
    magic: int = Field(alias="Mag")
    dexterity: int = Field(alias="Dex")
    speed: int = Field(alias="Spd")
    luck: int = Field(alias="Lck")
    defense: int = Field(alias="Def")
    resistance: int = Field(alias="Res")
    charm: int = Field(alias="Cha")

    @field_validator("name", mode="after")
    @classmethod
    def clean_name(cls, name: str) -> str:
        """Remove any parenthetical information from the name."""
        return _strip_parentheses(name)


class VoiceActors(BaseModel):
    english: str
    japanese: str


class Gendered[T](BaseModel):
    male: T | None
    female: T | None


class Image(Gendered[str]): ...


class GenderedHeight(Gendered[int]): ...


class VoiceActor(Gendered[VoiceActors]): ...


class Character(BaseModel):
    name: str
    house: str | None
    age: int | None
    height: int | GenderedHeight
    birthday: date | None
    crests: list[str]
    image: Image | None
    bio: str
    voice_actors: VoiceActors | VoiceActor

    @field_validator("name", mode="after")
    @classmethod
    def clean_name(cls, name: str) -> str:
        """Remove any parenthetical information from the name."""
        return _strip_parentheses(name)


class Recruitment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    house: str
    class_: str = Field(alias="class")
    from_chapter: int | None
    recruitment: str


class Support(BaseModel):
    name: str
    supports: list[str]


class BuddingTalent(BaseModel):
    name: str = Field(alias="Character")
    skill_level: str = Field(alias="Skill Level")
    unlock: str = Field(alias="Unlock")
    description: str = Field(alias="Description")


class Spell(BaseModel):
    name: str
    level: str


class LearnedSpells(BaseModel):
    name: str
    house: str
    magic_type: str
    spell_list: list[Spell]


class CrestGeneralInfo(BaseModel):
    name: str
    image: str | None
    description: str
    major_bearers: list[str]
    minor_bearers: list[str]


class CrestActivationRate(BaseModel):
    name: str
    image: str | None
    effect: str
    major_activation_rate: int
    minor_activation_rate: int
    item_activation_rate: int


class SkillInitialLevel(BaseModel):
    name: str | None
    image: str | None
    level: str


class SkillInitialLevels(BaseModel):
    name: str
    house: str
    initial_levels: list[SkillInitialLevel]


class SkillProficiency(BaseModel):
    name: str | None
    image: str | None
    boon: bool
    bane: bool
    budding_talent: bool


class SkillProficiencies(BaseModel):
    name: str
    house: str
    proficiencies: list[SkillProficiency]


class LearnedUniversalAbility(BaseModel):
    name: str
    level: str


class LearnedUniversal(BaseModel):
    skill: str
    abilities: list[LearnedUniversalAbility]


class AbilityArt(BaseModel):
    name: str
    skill: str | None
    level: str
    image: str | None


class Ability(AbilityArt): ...


class Art(AbilityArt): ...


class LearnedDependent[T](BaseModel):
    name: str
    house: str
    items: list[T]


class LearnedDependentAbilities(LearnedDependent[Ability]): ...


class LearnedDependentArts(LearnedDependent[Art]): ...


class ClassesAndCrests(BaseModel):
    name: str
    house: str
    starting_class: str | None
    beginner_class: str | None
    intermediate_class: str | None
    crests: list[str] | None


class Height(BaseModel):
    male: int | None
    female: int | None
    part_one: int | None
    part_two: int | None


class AgesAndHeights(BaseModel):
    name: str
    house: str
    age: int | None
    birthday: date | None
    height: Height | None


class AvailableInstructor(BaseModel):
    name: str
    skill_levels: list[str]
    notes: str | None


class AdvancedDrill(BaseModel):
    name: str
    skill_levels: list[str]


class Gift(BaseModel):
    name: str
    items: list[str]


class LikedGift(Gift): ...


class DislikedGift(Gift): ...


class LostItem(Gift): ...


class Ingredient(BaseModel):
    name: str
    quantity: int


class FullMenu(BaseModel):
    name: str
    ingredients: list[Ingredient]
    category: str | None = None
    effect: str | None = None


class Meal(BaseModel):
    name: str
    characters: list[str]


class LikedMeal(Meal): ...


class DislikedMeal(Meal): ...


class CookingTogether(BaseModel):
    good: list[str]
    bad: list[str]


class FinalComment(BaseModel):
    comment: str
    valid_answers: list[str]


class TeaParty(BaseModel):
    name: str
    house: str
    favorite_teas: list[str]
    interested_topics: list[str]
    final_comments: list[FinalComment]


class Seminar(BaseModel):
    name: str
    skill_levels: list[str]
    part: int
