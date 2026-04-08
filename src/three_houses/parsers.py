"""HTML parsers for Three Houses data."""

import re
import time
from datetime import UTC, date, datetime
from typing import cast

import httpx
from selectolax.lexbor import LexborHTMLParser, LexborNode

from three_houses.models import (
    Ability,
    AbilityArt,
    AdvancedDrill,
    AgesAndHeights,
    Art,
    AvailableInstructor,
    BuddingTalent,
    Character,
    ClassesAndCrests,
    CookingTogether,
    CrestActivationRate,
    CrestGeneralInfo,
    DislikedGift,
    DislikedMeal,
    FinalComment,
    FullMenu,
    GenderedHeight,
    Height,
    Image,
    Ingredient,
    LearnedDependentAbilities,
    LearnedDependentArts,
    LearnedSpells,
    LearnedUniversal,
    LearnedUniversalAbility,
    LikedGift,
    LikedMeal,
    LostItem,
    Recruitment,
    Seminar,
    SkillInitialLevel,
    SkillInitialLevels,
    SkillProficiencies,
    SkillProficiency,
    Spell,
    Stats,
    Support,
    TeaParty,
    VoiceActor,
    VoiceActors,
)


def _clean_voice_actor(text: str) -> str:
    text = re.sub(r"^[A-Z]{3}:\s*", "", text)  # ENG:, JPN:, etc.
    text = re.sub(r"\s*\((male|female)\)\s*$", "", text, flags=re.I)
    text = text.replace("*", "")
    return text.strip()


def _extract_image(node: LexborNode) -> Image | None:
    images = [x.attrs.get("href") for x in node.css("a") if x is not None]
    if len(images) == 2:
        return Image(male=images[0], female=images[1])
    return None


def _extract_age(node: LexborNode) -> int | None:
    age_cell_divs = node.css("div")
    if age_cell_divs:
        if age_cell_divs[0].text(strip=True) == "Unknown":
            return None
        return int(age_cell_divs[1].text(strip=True))
    age_text = node.text(strip=True)
    return int(age_text) if age_text.isdigit() else None


def _extract_height(node: LexborNode) -> int | GenderedHeight:
    heights = [x.split(" ")[0] for x in node.text(strip=True).split(", ")]
    if len(heights) == 2:
        return GenderedHeight(male=int(heights[0]), female=int(heights[1]))
    return int(heights[0])


def _extract_birthday(node: LexborNode) -> date | None:
    birthday_text = node.text(strip=True)
    try:
        clean_birthday_text = re.sub(r"(?<=\d)\D+(?=\s)", "", birthday_text)
        return (
            datetime.strptime(clean_birthday_text, "%d %B").replace(tzinfo=UTC).date()
        )
    except ValueError:
        return None


def _extract_crests(node: LexborNode) -> list[str]:
    crest_cell_divs = node.css("div")
    if crest_cell_divs:
        crests = [x.text(strip=True) for x in crest_cell_divs]
        return [x for x in crests if "Mystery" not in x]
    crests = node.text(strip=True).split(", ")
    return [x for x in crests if "None" not in x]


def _extract_voice_actors(node: LexborNode) -> VoiceActors | VoiceActor:
    voice_actor_text = node.text()  # do not strip; need to preserve newlines
    voice_actor_split = [x.strip() for x in voice_actor_text.split("\n")]
    if "," in voice_actor_text:
        # Corresponds to Protagonist
        va_split_english = voice_actor_split[0].split(", ")
        va_english = [_clean_voice_actor(x) for x in va_split_english]
        va_split_jpnese = voice_actor_split[1].split(", ")
        va_japanese = [_clean_voice_actor(x) for x in va_split_jpnese]
        return VoiceActor(
            male=VoiceActors(english=va_english[0], japanese=va_japanese[0]),
            female=VoiceActors(english=va_english[1], japanese=va_japanese[1]),
        )
    return VoiceActors(
        english=_clean_voice_actor(voice_actor_split[0]),
        japanese=_clean_voice_actor(voice_actor_split[1]),
    )


def _extract_parentheses(text: str) -> tuple[str, str]:
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", text)
    outside, inside = (m.group(1), m.group(2)) if m else (text, text)
    return outside, inside


def _extract_text_with_dash(text: str) -> str | None:
    return text.strip() if text.strip() != "–" else None


def _extract_text_from_table(
    table: LexborNode, *, skip_header: bool = True
) -> list[str]:
    starting_idx = 1 if skip_header else 0
    result: list[str] = []

    for row in table.css("tr")[starting_idx:]:
        for cell in row.css("td"):
            cell_text = cell.text(strip=True)
            if cell_text and cell_text != "–":
                result.append(cell_text)

    return result


def parse_stats(parser: LexborHTMLParser) -> list[Stats]:
    """Parse the growth rates HTML into a list of GrowthRate models."""
    growth_rates: list[Stats] = []

    headers = parser.css("h4")
    tables = parser.css("tbody")

    for header, table in zip(headers, tables, strict=True):
        header_text = header.text(strip=True)
        table_rows = table.css("tr")
        stat_headers = [x.text(strip=True) for x in table_rows[0].css("th")]
        for row in table_rows[1:]:
            stat_cells = [x.text(strip=True) for x in row.css("td")]
            stats_dict = dict(zip(stat_headers, stat_cells, strict=True))
            growth_rates.append(
                Stats(
                    Name=stats_dict["Name"],
                    house=header_text,
                    HP=int(stats_dict["HP"]),
                    Str=int(stats_dict["Str"]),
                    Mag=int(stats_dict["Mag"]),
                    Dex=int(stats_dict["Dex"]),
                    Spd=int(stats_dict["Spd"]),
                    Lck=int(stats_dict["Lck"]),
                    Def=int(stats_dict["Def"]),
                    Res=int(stats_dict["Res"]),
                    Cha=int(stats_dict["Cha"]),
                )
            )

    return growth_rates


def parse_characters(parser: LexborHTMLParser) -> list[Character]:
    """Parse the characters HTML into a list of Character models."""
    characters: list[Character] = []

    # We crawl this page sequentially in order to connect certain data
    if isinstance(parser.root, LexborNode):
        node_list = parser.root.css("*")
        last_house = None
        table_counter = 0
        for node in node_list:
            if node.tag == "h4":
                h4_text = node.text(strip=True)
                if last_house == "Church of Seiros":
                    # Once we get to this part of the page, names go from h5 to h4 tags
                    name = h4_text
                    continue
                last_house = node.text(strip=True)
            if node.tag == "h5":
                name = node.text(strip=True)
            if node.tag == "tbody":
                if table_counter % 2 == 0:
                    # This first table contains player images and bio
                    image = _extract_image(node)
                    bio = node.text(strip=True)
                else:
                    # The second contains biographical data
                    cells = node.css("tr")[1].css("td")
                    age = _extract_age(cells[0])
                    height = _extract_height(cells[1])
                    birthday = _extract_birthday(cells[2])
                    crests = _extract_crests(cells[3])
                    voice_actor = _extract_voice_actors(cells[4])
                    characters.append(
                        Character(
                            name=name,
                            house=last_house,
                            age=age,
                            height=height,
                            birthday=birthday,
                            crests=crests,
                            image=image,
                            bio=bio,
                            voice_actors=voice_actor,
                        )
                    )
                table_counter += 1
    return characters


def parse_recruitment(parser: LexborHTMLParser) -> list[Recruitment]:
    """Parse the recruitment HTML into a list of Recruitment models."""
    recruitments: list[Recruitment] = []

    houses = [x.text(strip=True) for x in parser.css("h4")]
    tables = parser.css("tbody")

    # The first two tables describe lowering requirements for recruitment
    for house, table in zip(houses, tables[2:], strict=True):
        table_rows = table.css("tr")
        for row in table_rows[1:]:
            cells = row.css("td")
            name = cells[0].text(strip=True)
            class_ = cells[1].text(strip=True)
            from_chapter_text = cells[2].text(strip=True)
            from_chapter = (
                int(from_chapter_text) if from_chapter_text.isdigit() else None
            )
            recruitment_text = cells[3].text()  # don't strip
            recruitment = (
                re.sub(r"\[spoiler\]", "", recruitment_text).replace("\n", " ").strip()
            )
            recruitments.append(
                Recruitment(
                    name=name,
                    house=house,
                    class_=class_,  # type: ignore
                    from_chapter=from_chapter,
                    recruitment=recruitment,
                )  # type: ignore
            )

    return recruitments


def parse_supports(parser: LexborHTMLParser) -> list[Support]:
    """Parse the supports HTML into a list of Support models."""
    supports: list[Support] = []

    table = parser.css_first("tbody")
    for row in table.css("tr"):
        cells = row.css("td")
        supports.append(
            Support(
                name=cells[0].text(strip=True),
                supports=[x.strip() for x in cells[1].text().split(",")],
            )
        )

    return supports


def parse_budding_talents(parser: LexborHTMLParser) -> list[BuddingTalent]:
    budding_talents: list[BuddingTalent] = []

    table = parser.css_first("tbody")
    rows = table.css("tr")
    headers = [x.text(strip=True) for x in rows[0].css("th")]

    for row in table.css("tr")[1:]:  # skip header
        cells = [x.text(strip=True) for x in row.css("td")]
        budding_talent_dict = dict(zip(headers, cells, strict=True))
        budding_talents.append(BuddingTalent(**budding_talent_dict))

    return budding_talents


def parse_learned_spells(parser: LexborHTMLParser) -> list[LearnedSpells]:
    learned_spells: list[LearnedSpells] = []

    tabs = parser.css("div.tabcontent")
    for tab in tabs:
        magic_type = tab.css_first("h4").text(strip=True)
        houses = [x.text(strip=True) for x in tab.css("h5")]
        tbody_list = tab.css("tbody")
        for tbody, house in zip(tbody_list, houses, strict=True):
            rows = tbody.css("tr")
            for row in rows[1:]:  # skip header
                cells = row.css("td")
                learned_spells.append(
                    LearnedSpells(
                        name=cells[0].text(strip=True),
                        house=house,
                        magic_type=magic_type,
                        spell_list=[
                            Spell(name=name, level=level)
                            for name, level in (
                                _extract_parentheses(x.text(strip=True))
                                for x in cells[1:]
                                if x.text(strip=True) != "–"
                            )
                        ],
                    )
                )
    return learned_spells


def parse_crests(
    parser: LexborHTMLParser,
) -> tuple[list[CrestGeneralInfo], list[CrestActivationRate]]:
    tabs = parser.css("div.tabcontent")
    # Returning in this order because that's how it looks on the site
    return parse_crests_general_info(tabs[1]), parse_crests_activation_rates(tabs[0])


def parse_crests_general_info(tab: LexborNode) -> list[CrestGeneralInfo]:
    crests_general_info: list[CrestGeneralInfo] = []

    tbody = tab.css_first("tbody")
    for row in tbody.css("tr")[1:]:  # skip header
        cells = row.css("td")
        crest_img = cells[0].css_first("img")
        crest_src = None
        if crest_img is not None:
            crest_src = crest_img.attrs.get("src")
        name = cells[1].text(strip=True).replace("[Mystery Crest]", "").strip()
        description_cell = cells[2]
        span_spoilers = description_cell.css_first("span.spoilerC[style]")
        if span_spoilers:
            description = span_spoilers.text(strip=True)
        else:
            description = description_cell.text(strip=True)
        major_bearers_text = cells[3].text(strip=True)
        minor_bearers_text = cells[4].text(strip=True)
        crests_general_info.append(
            CrestGeneralInfo(
                name=name,
                image=crest_src,
                description=description,
                major_bearers=[
                    x.replace("(Spoiler)", "").strip()
                    for x in major_bearers_text.split(",")
                ]
                if major_bearers_text
                else [],
                minor_bearers=[
                    x.replace("(Spoiler)", "").strip()
                    for x in minor_bearers_text.split(",")
                ]
                if minor_bearers_text
                else [],
            )
        )

    return crests_general_info


def parse_crests_activation_rates(tab: LexborNode) -> list[CrestActivationRate]:
    crests_activation_rates: list[CrestActivationRate] = []

    tbody = tab.css_first("tbody")
    for row in tbody.css("tr")[1:]:  # skip header
        cells = row.css("td")
        crest_img = cells[0].css_first("img")
        crest_src = None
        if crest_img is not None:
            crest_src = crest_img.attrs.get("src")
        name = cells[1].text(strip=True).replace("[Mystery Crest]", "").strip()
        effect = cells[2].text(strip=True)
        major_activation_rate = cells[3].text(strip=True)
        minor_activation_rate = cells[4].text(strip=True)
        item_activation_rate = cells[5].text(strip=True)
        crests_activation_rates.append(
            CrestActivationRate(
                name=name,
                image=crest_src,
                effect=effect,
                major_activation_rate=int(major_activation_rate),
                minor_activation_rate=int(minor_activation_rate),
                item_activation_rate=int(item_activation_rate),
            )
        )

    return crests_activation_rates


def parse_skill_levels(
    parser: LexborHTMLParser,
) -> tuple[list[SkillProficiencies], list[SkillInitialLevels]]:
    tabs = parser.css("div.tabcontent")
    # Returning in this order because that's how it looks on the site
    return parse_skill_proficiencies(tabs[1]), parse_skill_initial_levels(tabs[0])


def parse_skill_initial_levels(tab: LexborNode) -> list[SkillInitialLevels]:
    skill_initial_levels: list[SkillInitialLevels] = []

    headers = tab.css("h5")
    tables = tab.css("tbody")
    for header, table in zip(headers, tables, strict=True):
        rows = table.css("tr")
        header_cells = rows[0].css("th")
        header_names: list[str | None] = []
        header_img: list[str | None] = []
        for cell in header_cells[1:]:  # skip name header
            img = cell.css_first("img")
            if img is not None:
                header_img.append(img.attrs.get("src"))
                header_names.append(img.attrs.get("title"))
            else:
                header_img.append(None)
                header_names.append(cell.text(strip=True))
        for row in rows[1:]:  # skip header
            cells = row.css("td")
            character_text = cells[0].text(strip=True)
            skill_initial_levels.append(
                SkillInitialLevels(
                    name=character_text.replace(" (NPC)", "").strip(),
                    house=header.text(strip=True),
                    initial_levels=[
                        SkillInitialLevel(
                            name=header_name,
                            image=header_image,
                            level=cell.text(strip=True)
                            if cell.text(strip=True)
                            else "E",
                        )
                        for header_name, header_image, cell in zip(
                            header_names, header_img, cells[1:], strict=True
                        )
                    ],
                )
            )

    return skill_initial_levels


def parse_skill_proficiencies(tab: LexborNode) -> list[SkillProficiencies]:
    skill_proficiencies: list[SkillProficiencies] = []

    headers = tab.css("h5")
    tables = tab.css("tbody")
    for header, table in zip(headers, tables, strict=True):
        rows = table.css("tr")
        header_cells = rows[0].css("th")
        header_names: list[str | None] = []
        header_img: list[str | None] = []
        for cell in header_cells[1:]:  # skip name header
            img = cell.css_first("img")
            if img is not None:
                header_img.append(img.attrs.get("src"))
                header_names.append(img.attrs.get("title"))
            else:
                header_img.append(None)
                header_names.append(cell.text(strip=True))
        for row in rows[1:]:  # skip header
            cells = row.css("td")
            character_text = cells[0].text(strip=True)
            proficiencies: list[SkillProficiency] = []
            for cell, header_name, header_image in zip(
                cells[1:], header_names, header_img, strict=True
            ):
                boon, bane, budding_talent = False, False, False
                cell_img = cell.css_first("img")
                if cell_img is not None:
                    cell_img_title = cast(str, cell_img.attrs.get("title", "")).lower()
                    boon = "strong" in cell_img_title
                    bane = "weak" in cell_img_title
                    budding_talent = "budding" in cell_img_title
                proficiencies.append(
                    SkillProficiency(
                        name=header_name,
                        image=header_image,
                        boon=boon,
                        bane=bane,
                        budding_talent=budding_talent,
                    )
                )
            skill_proficiencies.append(
                SkillProficiencies(
                    name=character_text.replace(" (NPC)", "").strip(),
                    house=header.text(strip=True),
                    proficiencies=proficiencies,
                )
            )

    return skill_proficiencies


def parse_learned_abilities(parser: LexborHTMLParser) -> tuple[list, list, list]:
    tabs = parser.css("div.tabcontent")
    return (
        parse_learned_universal(tabs[0]),
        parse_learned_dependent_abilities(tabs[1]),
        parse_learned_dependent_arts(tabs[2]),
    )


def parse_learned_universal(tab: LexborNode) -> list[LearnedUniversal]:
    learned_universal: list[LearnedUniversal] = []

    tbody = tab.css_first("tbody")
    rows = tbody.css("tr")
    for row in rows[1:]:  # skip header
        cells = row.css("td")
        learned_universal.append(
            LearnedUniversal(
                skill=cells[0].text(strip=True),
                abilities=[
                    LearnedUniversalAbility(name=name, level=level)
                    for name, level in (
                        _extract_parentheses(x.text(strip=True))
                        for x in cells[1:]
                        if x.text(strip=True) != "–"
                    )
                ],
            )
        )

    return learned_universal


def parse_learned_dependent[T](
    tab: LexborNode,
    item_cls: type[AbilityArt],
    learned_dependent_cls: type[T],
) -> list[T]:
    learned_dependents: list[T] = []

    headers = tab.css("h5")
    tables = tab.css("tbody")
    items: list[AbilityArt] = []
    character_text = None
    for header, table in zip(headers, tables, strict=True):
        rows = table.css("tr")
        for row in rows[1:]:  # skip header
            # Multiple "rows" comprise a single row in certain cases
            # We can tell by seeing if the first cell has no image attached to it
            cells = row.css("td")
            if cells[0].css_first("img") is not None:
                # We need to include the first cell in this case
                rest_of_cells = cells
            else:
                # We have hit a new character
                rest_of_cells = cells[1:]
                if character_text is not None:
                    learned_dependents.append(
                        learned_dependent_cls(
                            name=character_text.replace(" (NPC)", "").strip(),
                            house=header.text(strip=True),
                            items=items,
                        )
                    )
                # Reset for next character
                character_text = cells[0].text(strip=True)
                items: list[Ability] = []
            for cell in rest_of_cells:
                cell_text = cell.text(strip=True)
                if cell_text != "–":
                    name, level = _extract_parentheses(cell_text)
                    skill, image = None, None
                    cell_img = cell.css_first("img")
                    if cell_img is not None:
                        skill = cell_img.attrs.get("title")
                        image = cell_img.attrs.get("src")
                    items.append(
                        item_cls(
                            name=name,
                            skill=skill
                            if cell_img is not None
                            else header.text(strip=True),
                            level=level,
                            image=image,
                        )
                    )

    return learned_dependents


def parse_learned_dependent_arts(tab: LexborNode) -> list[LearnedDependentArts]:
    return parse_learned_dependent(
        tab=tab,
        item_cls=Art,
        learned_dependent_cls=LearnedDependentArts,
    )


def parse_learned_dependent_abilities(
    tab: LexborNode,
) -> list[LearnedDependentAbilities]:
    return parse_learned_dependent(
        tab=tab,
        item_cls=Ability,
        learned_dependent_cls=LearnedDependentAbilities,
    )


def parse_other_data(parser: LexborHTMLParser) -> tuple[list, list]:
    tabs = parser.css("div.tabcontent")
    return parse_classes_and_crests(tabs[0]), parse_ages_and_heights(tabs[1])


def parse_classes_and_crests(tab: LexborNode) -> list[ClassesAndCrests]:
    classes_and_crests: list[ClassesAndCrests] = []

    headers = tab.css("h5")
    tables = tab.css("tbody")
    for header, table in zip(headers, tables, strict=True):
        rows = table.css("tr")
        for row in rows[1:]:  # skip header
            cells = row.css("td")
            crest_cell = cells[4]
            if span_spoiler3 := crest_cell.css("span.spoiler3"):
                crest_text = span_spoiler3[-1].text(strip=True)
            elif span_spoiler := crest_cell.css("span[class^='spoiler']"):
                crest_text = span_spoiler[-1].text(strip=True)
            elif div_spoiler := crest_cell.css("div[class^='spoiler']"):
                crest_text = div_spoiler[-1].text(strip=True)
            elif div_c := crest_cell.css("div[class^='c']"):
                crest_text = div_c[-1].text(strip=True)
            else:
                crest_text = crest_cell.text(strip=True)
            classes_and_crests.append(
                ClassesAndCrests(
                    name=cells[0].text(strip=True).replace(" (NPC)", "").strip(),
                    house=header.text(strip=True),
                    starting_class=_extract_text_with_dash(cells[1].text(strip=True)),
                    beginner_class=_extract_text_with_dash(cells[2].text(strip=True)),
                    intermediate_class=_extract_text_with_dash(
                        cells[3].text(strip=True)
                    ),
                    crests=[x.strip() for x in crest_text.split(",")]
                    if crest_text and crest_text != "–"
                    else None,
                )
            )

    return classes_and_crests


def parse_ages_and_heights(tab: LexborNode) -> list[AgesAndHeights]:
    ages_and_heights: list[AgesAndHeights] = []

    headers = tab.css("h5")
    tables = tab.css("tbody")
    for header, table in zip(headers, tables, strict=True):
        rows = table.css("tr")
        table_header_text = rows[0].text(strip=True)
        for row in rows[1:]:  # skip header
            cells = row.css("td")

            # Extract age
            if div_spoiler := cells[1].css("div[class^='spoiler']"):
                age_text = div_spoiler[-1].text(strip=True)
                if "(" in age_text:
                    age_text = age_text.split("(")[0].strip()
            else:
                age_text = cells[1].text(strip=True)
            age = int(age_text) if age_text.isdigit() else None

            # Extract height
            height_male, height_female = None, None
            height_part_one, height_part_two = None, None
            height_text_first = cells[3].text(strip=True)
            height_first = height_text_first.replace("cm", "").strip()

            height_second = None
            if len(cells) > 4:
                height_text_second = cells[4].text(strip=True)
                height_second = height_text_second.replace("cm", "").strip()
                if "same" in height_second.lower():
                    height_second = height_first
                if "Male" in table_header_text:
                    height_male = height_first
                    height_female = height_second
                else:
                    height_part_one = height_first
                    height_part_two = height_second
            else:
                height_part_one = height_first

            ages_and_heights.append(
                AgesAndHeights(
                    name=cells[0].text(strip=True).replace(" (NPC)", "").strip(),
                    house=header.text(strip=True),
                    age=age,
                    birthday=_extract_birthday(cells[2]),
                    height=Height(
                        male=int(height_male)
                        if height_male and height_male.isdigit()
                        else None,
                        female=int(height_female)
                        if height_female and height_female.isdigit()
                        else None,
                        part_one=int(height_part_one)
                        if height_part_one and height_part_one.isdigit()
                        else None,
                        part_two=int(height_part_two)
                        if height_part_two and height_part_two.isdigit()
                        else None,
                    ),
                )
            )

    return ages_and_heights


def parse_faculty_training(
    parser: LexborHTMLParser,
) -> tuple[list[AvailableInstructor], list[AdvancedDrill]]:
    tables = parser.css("tbody")
    return parse_available_instructors(tables[0]), parse_advanced_drills(tables[1])


def parse_available_instructors(table: LexborNode) -> list[AvailableInstructor]:
    available_instructors: list[AvailableInstructor] = []

    for row in table.css("tr")[1:]:  # skip header
        cells = row.css("td")
        skill_level_text = cells[1].text(strip=True).replace("and", ",")
        notes_text = cells[2].text(strip=True)
        available_instructors.append(
            AvailableInstructor(
                name=cells[0].text(strip=True),
                skill_levels=[x.strip() for x in skill_level_text.split(",")],
                notes=notes_text if notes_text and notes_text != "–" else None,
            )
        )
    return available_instructors


def parse_advanced_drills(table: LexborNode) -> list[AdvancedDrill]:
    advanced_drills: list[AdvancedDrill] = []

    for row in table.css("tr")[1:]:  # skip header
        cells = row.css("td")
        for i in range(0, len(cells), 2):
            half = cells[i : i + 2]
            skill_level_text = half[1].text(strip=True).replace("and", ",")
            advanced_drills.append(
                AdvancedDrill(
                    name=half[0].text(strip=True),
                    skill_levels=[x.strip() for x in skill_level_text.split(",")],
                )
            )

    return advanced_drills


def parse_gifts(
    parser: LexborHTMLParser,
) -> tuple[list[LikedGift], list[DislikedGift], list[LostItem]]:
    tabs = parser.css("div.tabcontent")
    # Returning in this order because that's how it looks on the site
    return (
        parse_liked_gifts(tabs[1]),
        parse_disliked_gifts(tabs[2]),
        parse_lost_items(tabs[0]),
    )


def parse_gift_items[T](tab: LexborNode, gift_cls: type[T]) -> list[T]:
    gifts: list[T] = []

    table = tab.css_first("tbody")
    items: list[str] = []
    name = None

    for row in table.css("tr")[1:]:  # skip header
        cells = row.css("td")

        num_cells = len(cells)
        if gift_cls == LikedGift:
            # 5 cells indicate a new character
            is_char_row = num_cells == 5
        else:
            # 4 cells indicate a new character
            is_char_row = num_cells == 4

        if name and is_char_row:
            gifts.append(
                gift_cls(
                    name=name,
                    items=items,
                )
            )
            items = []  # Reset items for the new character

        if is_char_row:
            name = cells[0].text(strip=True).replace(" (NPC)", "").strip()
            item_cells = cells[1:]
        else:
            item_cells = cells
        items_text = [x.text(strip=True) for x in item_cells]
        items.extend([x for x in items_text if x and x != "–"])

    # Handle the last character after the loop
    gifts.append(
        gift_cls(
            name=name,
            items=items,
        )
    )

    return gifts


def parse_liked_gifts(tab: LexborNode) -> list[LikedGift]:
    return parse_gift_items(tab=tab, gift_cls=LikedGift)


def parse_disliked_gifts(tab: LexborNode) -> list[DislikedGift]:
    return parse_gift_items(tab=tab, gift_cls=DislikedGift)


def parse_lost_items(tab: LexborNode) -> list[LostItem]:
    lost_items: list[LostItem] = []

    table = tab.css_first("tbody")
    for row in table.css("tr")[1:]:  # skip header
        cells = row.css("td")
        items = [x.text(strip=True) for x in cells[1:]]
        lost_items.append(
            LostItem(
                name=cells[0].text(strip=True).replace(" (NPC)", "").strip(),
                items=[x for x in items if x and x != "–"],
            )
        )

    return lost_items


def parse_dining_hall(
    parser: LexborHTMLParser,
) -> tuple[list[FullMenu], list[CookingTogether], list[LikedMeal], list[DislikedMeal]]:
    tables = parser.css("tbody")
    tabs = parser.css("div.tabcontent")
    # Returning in this order because that's how it looks on the site
    return (
        parse_full_menu(tabs[0], effect_table=tables[-1]),
        parse_cooking_together(tables[-2]),
        parse_liked_meals(tabs[1]),
        parse_disliked_meals(tabs[2]),
    )


def parse_full_menu(tab: LexborNode, effect_table: LexborNode) -> list[FullMenu]:
    full_menu: list[FullMenu] = []

    full_menu_table = tab.css("tbody")[1]
    category = None
    for table in [full_menu_table, effect_table]:
        for row in table.css("tr")[1:]:  # skip header
            cells = row.css("td")
            if len(cells) == 5:
                # This row contains a category
                category_text = cells[-1].text(strip=True)
                category = category_text if category_text not in ["N/A", "–"] else None
                ingredient_cells = cells[1:-1]
            else:
                ingredient_cells = cells[1:]

            if "Effect" in table.text():
                effect = category
                category = None
            else:
                effect = None

            ingredients: list[Ingredient] = []
            for cell in ingredient_cells:
                ingredient_text = cell.text(strip=True)
                if ingredient_text and ingredient_text != "–":
                    result = re.match(r"^\s*(.+?)\s*[xX]\s*(\d+)\s*$", ingredient_text)
                    if result:
                        name, quantity = result.groups()
                        ingredients.append(
                            Ingredient(
                                name=name,
                                quantity=int(quantity),
                            )
                        )

            full_menu.append(
                FullMenu(
                    name=cells[0].text(strip=True),
                    ingredients=ingredients,
                    category=category,
                    effect=effect,
                )
            )

    return full_menu


def parse_cooking_together(table: LexborNode) -> list[CookingTogether]:
    cooking_together: list[CookingTogether] = []

    for row in table.css("tr")[1:]:  # skip header
        cells = row.css("td")
        cooking_together.append(
            CookingTogether(
                good=cells[0].text(strip=True).split(", "),
                bad=cells[1].text(strip=True).split(", "),
            )
        )

    return cooking_together


def parse_meals[T](tab: LexborNode, meal_cls: type[T]) -> list[T]:
    meals: list[T] = []

    table = tab.css_first("tbody")

    for row in table.css("tr")[1:]:  # skip header
        cells = row.css("td")
        meal = meal_cls(
            name=cells[0].text(strip=True),
            characters=cells[1].text(strip=True).split(", "),
        )
        meals.append(meal)

    return meals


def parse_liked_meals(tab: LexborNode) -> list[LikedMeal]:
    return parse_meals(tab=tab, meal_cls=LikedMeal)


def parse_disliked_meals(tab: LexborNode) -> list[DislikedMeal]:
    return parse_meals(tab=tab, meal_cls=DislikedMeal)


def parse_tea_party(parser: LexborHTMLParser) -> list[TeaParty]:
    tea_parties: list[TeaParty] = []

    tables = parser.css("tbody")
    for table in tables:
        header_th = table.css_first("tr").css("th")
        headers = [x.text(strip=True) for x in header_th]
        for row in table.css("tr")[1:]:  # skip header
            cells = row.css("td")
            if len(cells) != len(headers):
                headers *= len(cells) // len(headers)  # repeat headers as needed
            for header, cell in zip(headers, cells, strict=True):
                a = cell.css_first("a")
                if a is not None:
                    href = a.attrs.get("href", "")
                    name = cell.text(strip=True)
                    if href and "tea-party" in href:
                        response = httpx.get(href)
                        if response.status_code == 200:
                            tea_party_parser = LexborHTMLParser(response.text)
                            tea_party = parse_tea_party_page(
                                tea_party_parser,
                                name=name,
                                house=header,
                            )
                            tea_parties.append(tea_party)
                            time.sleep(1)  # Be polite and avoid overwhelming the server

    return tea_parties


def parse_tea_party_page(parser: LexborHTMLParser, name: str, house: str) -> TeaParty:
    tables = parser.css("tbody")

    # The first table contains favorite teas
    favorite_teas = _extract_text_from_table(tables[0])

    # The second table contains interested topics
    interested_topics = _extract_text_from_table(tables[1])

    # The third table contains final comments and their valid answers
    final_comments: list[FinalComment] = []
    for row in tables[2].css("tr")[1:]:  # skip header
        cells = row.css("td")
        valid_answers_text = [x.text(strip=True) for x in cells[1:]]
        final_comments.append(
            FinalComment(
                comment=cells[0].text(strip=True),
                valid_answers=[x for x in valid_answers_text if x and x != "–"],
            )
        )

    return TeaParty(
        name=name,
        house=house,
        favorite_teas=favorite_teas,
        interested_topics=interested_topics,
        final_comments=final_comments,
    )


def parse_seminars(parser: LexborHTMLParser) -> list[Seminar]:
    seminars: list[Seminar] = []

    tables = parser.css("tbody")
    for idx, table in enumerate(tables[:2], start=1):
        for row in table.css("tr")[1:]:  # skip header
            cells = row.css("td")
            for i in range(0, len(cells), 2):
                half = cells[i : i + 2]
                name = half[0].text(strip=True)
                if name and name != "–":
                    seminars.append(
                        Seminar(
                            name=half[0].text(strip=True),
                            skill_levels=half[1].text(strip=True).split(" and "),
                            part=idx,
                        )
                    )

    return seminars
