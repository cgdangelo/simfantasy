from math import floor

import numpy

from simfantasy.enums import Race, Job, Attribute

main_stat_per_level = [
    20, 21, 22, 24, 26, 27, 29, 31, 33, 35, 36, 38, 41, 44, 46, 49, 52, 54, 57, 60, 63, 67, 71, 74, 78, 81, 85, 89, 92,
    97, 101, 106, 110, 115, 119, 124, 128, 134, 139, 144, 150, 155, 161, 166, 171, 177, 183, 189, 196, 202, 204, 205,
    207, 209, 210, 212, 214, 215, 217, 218, 224, 228, 236, 244, 252, 260, 268, 276, 284, 292
]

sub_stat_per_level = [
    56, 57, 60, 62, 65, 68, 70, 73, 76, 78, 82, 85, 89, 93, 96, 100, 104, 109, 113, 116, 122, 127, 133, 138, 144, 150,
    155, 162, 168, 173, 181, 188, 194, 202, 209, 215, 223, 229, 236, 244, 253, 263, 272, 283, 292, 302, 311, 322, 331,
    341, 342, 344, 345, 346, 347, 349, 350, 351, 352, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363, 364,
]

divisor_per_level = [
    56, 57, 60, 62, 65, 68, 70, 73, 76, 78, 82, 85, 89, 93, 96, 100, 104, 109, 113, 116, 122, 127, 133, 138, 144, 150,
    155, 162, 168, 173, 181, 188, 194, 202, 209, 215, 223, 229, 236, 244, 253, 263, 272, 283, 292, 302, 311, 322, 331,
    341, 393, 444, 496, 548, 600, 651, 703, 755, 806, 858, 941, 1032, 1133, 1243, 1364, 1497, 1643, 1802, 1978, 2170,
]


def get_racial_attribute_bonuses(race: Race):
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


def get_base_stats_by_job(job: Job):
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


def calculate_base_stats(level: int, job: Job, race: Race):
    base_main_stat = main_stat_per_level[level - 1]
    base_sub_stat = sub_stat_per_level[level - 1]

    base_stats = {
        Attribute.STRENGTH: 0,
        Attribute.DEXTERITY: 0,
        Attribute.VITALITY: 0,
        Attribute.INTELLIGENCE: 0,
        Attribute.MIND: 0,
        Attribute.CRITICAL_HIT: base_sub_stat,
        Attribute.DETERMINATION: base_main_stat,
        Attribute.DIRECT_HIT: base_sub_stat,
        Attribute.SKILL_SPEED: base_sub_stat,
    }

    job_stats = get_base_stats_by_job(job)
    race_stats = get_racial_attribute_bonuses(race)

    for stat, bonus in job_stats.items():
        base_stats[stat] += floor(base_main_stat * (bonus / 100)) + race_stats[stat]

    return base_stats


def calculate_action_damage(source, action):
    base_stats = get_base_stats_by_job(source.job)

    if action.affected_by is Attribute.ATTACK_POWER:
        if source.job in [Job.BARD, Job.MACHINIST, Job.NINJA]:
            job_attribute_modifier = base_stats[Attribute.DEXTERITY]
            attack_rating = source.stats[Attribute.DEXTERITY]
        else:
            job_attribute_modifier = base_stats[Attribute.STRENGTH]
            attack_rating = source.stats[Attribute.STRENGTH]

        weapon_damage = source.physical_damage
    elif action.affected_by is Attribute.ATTACK_MAGIC_POTENCY:
        if source.job in [Job.ASTROLOGIAN, Job.SCHOLAR, Job.WHITE_MAGE]:
            job_attribute_modifier = base_stats[Attribute.MIND]
            attack_rating = source.stats[Attribute.MIND]
        else:
            job_attribute_modifier = base_stats[Attribute.INTELLIGENCE]
            attack_rating = source.stats[Attribute.INTELLIGENCE]

        weapon_damage = source.magic_damage
    elif action.affected_by is Attribute.HEALING_MAGIC_POTENCY:
        job_attribute_modifier = base_stats[Attribute.MIND]
        weapon_damage = source.magic_damage
        attack_rating = source.stats[Attribute.MIND]
    else:
        raise Exception('Action affected by unexpected attribute.')

    main_stat = main_stat_per_level[source.level - 1]
    sub_stat = sub_stat_per_level[source.level - 1]
    divisor = divisor_per_level[source.level - 1]

    f_ptc = action.potency / 100
    f_wd = floor((main_stat * job_attribute_modifier / 100) + weapon_damage)
    f_atk = floor((125 * (attack_rating - 292) / 292) + 100) / 100
    f_det = floor(130 * (source.stats[Attribute.DETERMINATION] - main_stat) / divisor + 1000) / 1000
    f_tnc = floor(100 * (source.stats[Attribute.TENACITY] - sub_stat) / divisor + 1000) / 1000
    f_chr = floor(200 * (source.stats[Attribute.CRITICAL_HIT] - sub_stat) / divisor + 1400) / 1000

    p_dhr = floor(550 * (source.stats[Attribute.DIRECT_HIT] - sub_stat) / divisor) / 10
    p_chr = floor(200 * (source.stats[Attribute.CRITICAL_HIT] - sub_stat) / divisor + 50) / 10

    is_direct_hit = numpy.random.uniform() > p_dhr
    is_critical_hit = numpy.random.uniform() > p_chr

    damage_randomization = numpy.random.uniform(0.95, 1.05)

    damage = floor(
        (f_ptc * f_wd * f_atk * f_det * f_tnc) *
        (f_chr if is_critical_hit else 1) *
        (1.25 if is_direct_hit else 1) *
        damage_randomization
    )

    return damage
