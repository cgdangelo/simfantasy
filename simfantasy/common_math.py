from typing import Dict, List

from simfantasy.enum import Attribute, Job, Race, Resource

main_stat_per_level: List[int] = [
    None, 20, 21, 22, 24, 26, 27, 29, 31, 33, 35, 36, 38, 41, 44, 46, 49, 52, 54, 57, 60, 63, 67, 71, 74, 78, 81, 85,
    89, 92, 97, 101, 106, 110, 115, 119, 124, 128, 134, 139, 144, 150, 155, 161, 166, 171, 177, 183, 189, 196, 202, 204,
    205, 207, 209, 210, 212, 214, 215, 217, 218, 224, 228, 236, 244, 252, 260, 268, 276, 284, 292
]
"""Base amount for primary stats per level."""

sub_stat_per_level: List[int] = [
    None, 56, 57, 60, 62, 65, 68, 70, 73, 76, 78, 82, 85, 89, 93, 96, 100, 104, 109, 113, 116, 122, 127, 133, 138, 144,
    150, 155, 162, 168, 173, 181, 188, 194, 202, 209, 215, 223, 229, 236, 244, 253, 263, 272, 283, 292, 302, 311, 322,
    331, 341, 342, 344, 345, 346, 347, 349, 350, 351, 352, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363, 364,
]
"""Base amount for secondary stats per level."""

divisor_per_level: List[int] = [
    None, 56, 57, 60, 62, 65, 68, 70, 73, 76, 78, 82, 85, 89, 93, 96, 100, 104, 109, 113, 116, 122, 127, 133, 138, 144,
    150, 155, 162, 168, 173, 181, 188, 194, 202, 209, 215, 223, 229, 236, 244, 253, 263, 272, 283, 292, 302, 311, 322,
    331, 341, 393, 444, 496, 548, 600, 651, 703, 755, 806, 858, 941, 1032, 1133, 1243, 1364, 1497, 1643, 1802, 1978,
    2170,
]
"""Divisor for multiple calculations per level."""

piety_per_level: List[int] = [
    None, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160, 165,
    170, 175, 180, 185, 190, 195, 200, 205, 210, 215, 220, 225, 230, 235, 240, 245, 250, 255, 260, 265, 270, 275, 280,
    285, 290, 300, 315, 330, 360, 390, 420, 450, 480, 510, 540, 620, 650, 680, 710, 740, 770, 800, 830, 860, 890, 890
]

mp_per_level: List[int] = [
    None, 104, 114, 123, 133, 142, 152, 161, 171, 180, 190, 209, 228, 247, 266, 285, 304, 323, 342, 361, 380, 418, 456,
    494, 532, 570, 608, 646, 684, 722, 760, 826, 893, 959, 1026, 1092, 1159, 1225, 1292, 1358, 1425, 1548, 1672, 1795,
    1919, 2042, 2166, 2289, 2413, 2536, 2660, 3000, 3380, 3810, 4300, 4850, 5470, 6170, 6950, 7840, 8840, 8980, 9150,
    9350, 9590, 9870, 10190, 10560, 10980, 11450, 12000
]


def get_racial_attribute_bonuses(race: Race) -> Dict[Attribute, int]:
    """
    Get main stat bonuses by clan.

    :param race: Clan.
    :return: Dictionary mapping :class:`~simfantasy.enums.Attribute` to integer bonus values.
    """
    if race is Race.WILDWOOD:
        return {
            Attribute.STRENGTH: 0,
            Attribute.DEXTERITY: 3,
            Attribute.VITALITY: -1,
            Attribute.INTELLIGENCE: 2,
            Attribute.MIND: -1
        }
    elif race is Race.DUSKWIGHT:
        return {
            Attribute.STRENGTH: 0,
            Attribute.DEXTERITY: 0,
            Attribute.VITALITY: -1,
            Attribute.INTELLIGENCE: 3,
            Attribute.MIND: 1
        }
    elif race is Race.MIDLANDER:
        return {
            Attribute.STRENGTH: 2,
            Attribute.DEXTERITY: -1,
            Attribute.VITALITY: 0,
            Attribute.INTELLIGENCE: 3,
            Attribute.MIND: -1
        }
    elif race is Race.HIGHLANDER:
        return {
            Attribute.STRENGTH: 3,
            Attribute.DEXTERITY: 0,
            Attribute.VITALITY: 2,
            Attribute.INTELLIGENCE: -2,
            Attribute.MIND: 0
        }
    elif race is Race.PLAINSFOLK:
        return {
            Attribute.STRENGTH: -1,
            Attribute.DEXTERITY: 3,
            Attribute.VITALITY: -1,
            Attribute.INTELLIGENCE: 2,
            Attribute.MIND: 0
        }
    elif race is Race.DUNESFOLK:
        return {
            Attribute.STRENGTH: -1,
            Attribute.DEXTERITY: 1,
            Attribute.VITALITY: -2,
            Attribute.INTELLIGENCE: 2,
            Attribute.MIND: 3
        }
    elif race is Race.SEEKER_OF_THE_SUN:
        return {
            Attribute.STRENGTH: 2,
            Attribute.DEXTERITY: 3,
            Attribute.VITALITY: 0,
            Attribute.INTELLIGENCE: -1,
            Attribute.MIND: -1
        }
    elif race is Race.KEEPER_OF_THE_MOON:
        return {
            Attribute.STRENGTH: -1,
            Attribute.DEXTERITY: 2,
            Attribute.VITALITY: -2,
            Attribute.INTELLIGENCE: 1,
            Attribute.MIND: 3
        }
    elif race is Race.SEA_WOLF:
        return {
            Attribute.STRENGTH: 2,
            Attribute.DEXTERITY: -1,
            Attribute.VITALITY: 3,
            Attribute.INTELLIGENCE: -2,
            Attribute.MIND: 1
        }
    elif race is Race.HELLSGUARD:
        return {
            Attribute.STRENGTH: 0,
            Attribute.DEXTERITY: -3,
            Attribute.VITALITY: 3,
            Attribute.INTELLIGENCE: 0,
            Attribute.MIND: 2
        }
    elif race is Race.RAEN:
        return {
            Attribute.STRENGTH: -1,
            Attribute.DEXTERITY: -2,
            Attribute.VITALITY: -1,
            Attribute.INTELLIGENCE: 0,
            Attribute.MIND: 3
        }
    elif race is Race.XAELA:
        return {
            Attribute.STRENGTH: 3,
            Attribute.DEXTERITY: 0,
            Attribute.VITALITY: 2,
            Attribute.INTELLIGENCE: 0,
            Attribute.MIND: -2
        }
    else:
        return {
            Attribute.STRENGTH: 0,
            Attribute.DEXTERITY: 0,
            Attribute.VITALITY: 0,
            Attribute.INTELLIGENCE: 0,
            Attribute.MIND: 0
        }


def get_base_stats_by_job(job: Job) -> Dict[Attribute, int]:
    """
    Get base main stats by job.

    :param job: Job.
    :return: Dictionary mapping :class:`~simfantasy.enums.Attribute` to integer bonus values.
    """
    if job is Job.GLADIATOR:
        return {
            Attribute.STRENGTH: 95,
            Attribute.DEXTERITY: 90,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 50,
            Attribute.MIND: 95
        }
    elif job is Job.PUGILIST:
        return {
            Attribute.STRENGTH: 100,
            Attribute.DEXTERITY: 100,
            Attribute.VITALITY: 95,
            Attribute.INTELLIGENCE: 45,
            Attribute.MIND: 85
        }
    elif job is Job.MARAUDER:
        return {
            Attribute.STRENGTH: 100,
            Attribute.DEXTERITY: 90,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 30,
            Attribute.MIND: 50
        }
    elif job is Job.LANCER:
        return {
            Attribute.STRENGTH: 105,
            Attribute.DEXTERITY: 95,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 40,
            Attribute.MIND: 60
        }
    elif job is Job.ARCHER:
        return {
            Attribute.STRENGTH: 85,
            Attribute.DEXTERITY: 105,
            Attribute.VITALITY: 95,
            Attribute.INTELLIGENCE: 80,
            Attribute.MIND: 75
        }
    elif job is Job.CONJURER:
        return {
            Attribute.STRENGTH: 50,
            Attribute.DEXTERITY: 100,
            Attribute.VITALITY: 95,
            Attribute.INTELLIGENCE: 100,
            Attribute.MIND: 105
        }
    elif job is Job.THAUMATURGE:
        return {
            Attribute.STRENGTH: 40,
            Attribute.DEXTERITY: 95,
            Attribute.VITALITY: 95,
            Attribute.INTELLIGENCE: 105,
            Attribute.MIND: 70
        }
    elif job is Job.PALADIN:
        return {
            Attribute.STRENGTH: 100,
            Attribute.DEXTERITY: 95,
            Attribute.VITALITY: 110,
            Attribute.INTELLIGENCE: 60,
            Attribute.MIND: 100
        }
    elif job is Job.MONK:
        return {
            Attribute.STRENGTH: 110,
            Attribute.DEXTERITY: 105,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 50,
            Attribute.MIND: 90
        }
    elif job is Job.WARRIOR:
        return {
            Attribute.STRENGTH: 105,
            Attribute.DEXTERITY: 95,
            Attribute.VITALITY: 110,
            Attribute.INTELLIGENCE: 40,
            Attribute.MIND: 55
        }
    elif job is Job.DRAGOON:
        return {
            Attribute.STRENGTH: 115,
            Attribute.DEXTERITY: 100,
            Attribute.VITALITY: 105,
            Attribute.INTELLIGENCE: 45,
            Attribute.MIND: 65
        }
    elif job is Job.BARD:
        return {
            Attribute.STRENGTH: 90,
            Attribute.DEXTERITY: 115,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 85,
            Attribute.MIND: 80
        }
    elif job is Job.WHITE_MAGE:
        return {
            Attribute.STRENGTH: 55,
            Attribute.DEXTERITY: 105,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 105,
            Attribute.MIND: 115
        }
    elif job is Job.BLACK_MAGE:
        return {
            Attribute.STRENGTH: 45,
            Attribute.DEXTERITY: 100,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 115,
            Attribute.MIND: 75
        }
    elif job is Job.ARCANIST:
        return {
            Attribute.STRENGTH: 85,
            Attribute.DEXTERITY: 95,
            Attribute.VITALITY: 95,
            Attribute.INTELLIGENCE: 105,
            Attribute.MIND: 75
        }
    elif job is Job.SUMMONER:
        return {
            Attribute.STRENGTH: 90,
            Attribute.DEXTERITY: 100,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 115,
            Attribute.MIND: 80
        }
    elif job is Job.SCHOLAR:
        return {
            Attribute.STRENGTH: 90,
            Attribute.DEXTERITY: 100,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 105,
            Attribute.MIND: 115
        }
    elif job is Job.ROGUE:
        return {
            Attribute.STRENGTH: 80,
            Attribute.DEXTERITY: 100,
            Attribute.VITALITY: 95,
            Attribute.INTELLIGENCE: 60,
            Attribute.MIND: 70
        }
    elif job is Job.NINJA:
        return {
            Attribute.STRENGTH: 85,
            Attribute.DEXTERITY: 110,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 65,
            Attribute.MIND: 75
        }
    elif job is Job.MACHINIST:
        return {
            Attribute.STRENGTH: 85,
            Attribute.DEXTERITY: 115,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 80,
            Attribute.MIND: 85
        }
    elif job is Job.DARK_KNIGHT:
        return {
            Attribute.STRENGTH: 105,
            Attribute.DEXTERITY: 95,
            Attribute.VITALITY: 110,
            Attribute.INTELLIGENCE: 60,
            Attribute.MIND: 40
        }
    elif job is Job.ASTROLOGIAN:
        return {
            Attribute.STRENGTH: 50,
            Attribute.DEXTERITY: 100,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 105,
            Attribute.MIND: 115
        }
    elif job is Job.SAMURAI:
        return {
            Attribute.STRENGTH: 112,
            Attribute.DEXTERITY: 108,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 60,
            Attribute.MIND: 50
        }
    elif job is Job.RED_MAGE:
        return {
            Attribute.STRENGTH: 55,
            Attribute.DEXTERITY: 105,
            Attribute.VITALITY: 100,
            Attribute.INTELLIGENCE: 115,
            Attribute.MIND: 110
        }
    else:
        return {
            Attribute.STRENGTH: 0,
            Attribute.DEXTERITY: 0,
            Attribute.VITALITY: 0,
            Attribute.INTELLIGENCE: 0,
            Attribute.MIND: 0
        }


def get_base_resources_by_job(job: Job) -> Dict[Resource, int]:
    """
    Get base main stats by job.

    :param job: Job.
    :return: Dictionary mapping :class:`~simfantasy.enums.Attribute` to integer bonus values.
    """
    if job is Job.GLADIATOR:
        return {
            Resource.HP: 110,
            Resource.MP: 49,
        }
    elif job is Job.PUGILIST:
        return {
            Resource.HP: 105,
            Resource.MP: 34,
        }
    elif job is Job.MARAUDER:
        return {
            Resource.HP: 115,
            Resource.MP: 28,
        }
    elif job is Job.LANCER:
        return {
            Resource.HP: 110,
            Resource.MP: 39,
        }
    elif job is Job.ARCHER:
        return {
            Resource.HP: 100,
            Resource.MP: 69,
        }
    elif job is Job.CONJURER:
        return {
            Resource.HP: 100,
            Resource.MP: 117,
        }
    elif job is Job.THAUMATURGE:
        return {
            Resource.HP: 100,
            Resource.MP: 123,
        }
    elif job is Job.PALADIN:
        return {
            Resource.HP: 120,
            Resource.MP: 59,
        }
    elif job is Job.MONK:
        return {
            Resource.HP: 110,
            Resource.MP: 43,
        }
    elif job is Job.WARRIOR:
        return {
            Resource.HP: 125,
            Resource.MP: 38,
        }
    elif job is Job.DRAGOON:
        return {
            Resource.HP: 115,
            Resource.MP: 49,
        }
    elif job is Job.BARD:
        return {
            Resource.HP: 105,
            Resource.MP: 79,
        }
    elif job is Job.WHITE_MAGE:
        return {
            Resource.HP: 105,
            Resource.MP: 124,
        }
    elif job is Job.BLACK_MAGE:
        return {
            Resource.HP: 105,
            Resource.MP: 129,
        }
    elif job is Job.ARCANIST:
        return {
            Resource.HP: 100,
            Resource.MP: 110,
        }
    elif job is Job.SUMMONER:
        return {
            Resource.HP: 105,
            Resource.MP: 111,
        }
    elif job is Job.SCHOLAR:
        return {
            Resource.HP: 105,
            Resource.MP: 119,
        }
    elif job is Job.ROGUE:
        return {
            Resource.HP: 103,
            Resource.MP: 38,
        }
    elif job is Job.NINJA:
        return {
            Resource.HP: 108,
            Resource.MP: 48,
        }
    elif job is Job.MACHINIST:
        return {
            Resource.HP: 105,
            Resource.MP: 79,
        }
    elif job is Job.DARK_KNIGHT:
        return {
            Resource.HP: 120,
            Resource.MP: 79,
        }
    elif job is Job.ASTROLOGIAN:
        return {
            Resource.HP: 105,
            Resource.MP: 124,
        }
    elif job is Job.SAMURAI:
        return {
            Resource.HP: 109,
            Resource.MP: 40,
        }
    elif job is Job.RED_MAGE:
        return {
            Resource.HP: 105,
            Resource.MP: 120,
        }
    else:
        return {
            Resource.HP: 0,
            Resource.MP: 0,
        }
