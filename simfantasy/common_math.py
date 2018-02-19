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
        return 0, 3, -1, 2, -1
    elif race is Race.DUSKWIGHT:
        return 0, 0, -1, 3, 1
    elif race is Race.MIDLANDER:
        return 2, -1, 0, 3, -1
    elif race is Race.HIGHLANDER:
        return 3, 0, 2, -2, 0
    elif race is Race.PLAINSFOLK:
        return -1, 3, -1, 2, 0
    elif race is Race.DUNESFOLK:
        return -1, 1, -2, 2, 3
    elif race is Race.SEEKER_OF_THE_SUN:
        return 2, 3, 0, -1, -1
    elif race is Race.KEEPER_OF_THE_MOON:
        return -1, 2, -2, 1, 3
    elif race is Race.SEA_WOLF:
        return 2, -1, 3, -2, 1
    elif race is Race.HELLSGUARD:
        return 0, -2, 3, 0, 2
    elif race is Race.RAEN:
        return -1, 2, -1, 0, 3
    elif race is Race.XAELA:
        return 3, 0, 2, 0, -2
    else:
        return 0, 0, 0, 0, 0


def get_base_stats_by_job(job: Job):
    if job is Job.GLADIATOR:
        return 95, 90, 100, 50, 95
    elif job is Job.PUGILIST:
        return 100, 100, 95, 45, 85
    elif job is Job.MARAUDER:
        return 100, 90, 100, 30, 50
    elif job is Job.LANCER:
        return 105, 95, 100, 40, 60
    elif job is Job.ARCHER:
        return 85, 105, 95, 80, 75
    elif job is Job.CONJURER:
        return 50, 100, 95, 100, 105
    elif job is Job.THAUMATURGE:
        return 40, 95, 95, 105, 70
    elif job is Job.PALADIN:
        return 100, 95, 110, 60, 100
    elif job is Job.MONK:
        return 110, 105, 100, 50, 90
    elif job is Job.WARRIOR:
        return 105, 95, 110, 40, 55
    elif job is Job.DRAGOON:
        return 115, 100, 105, 45, 65
    elif job is Job.BARD:
        return 90, 115, 100, 85, 80
    elif job is Job.WHITE_MAGE:
        return 55, 105, 100, 105, 115
    elif job is Job.BLACK_MAGE:
        return 45, 100, 100, 115, 75
    elif job is Job.ARCANIST:
        return 85, 95, 95, 105, 75
    elif job is Job.SUMMONER:
        return 90, 100, 100, 115, 80
    elif job is Job.SCHOLAR:
        return 90, 100, 100, 105, 115
    elif job is Job.ROGUE:
        return 80, 100, 95, 60, 70
    elif job is Job.NINJA:
        return 85, 110, 100, 65, 75
    elif job is Job.MACHINIST:
        return 85, 115, 100, 80, 85
    elif job is Job.DARK_KNIGHT:
        return 105, 95, 110, 60, 40
    elif job is Job.ASTROLOGIAN:
        return 50, 100, 100, 105, 115
    elif job is Job.SAMURAI:
        return 112, 108, 100, 60, 50
    elif job is Job.RED_MAGE:
        return 55, 105, 100, 115, 110
    else:
        return 0, 0, 0, 0, 0


def calculate_base_stats(level: int, job: Job, race: Race):
    base_main_stat = main_stat_per_level[level - 1]

    race_stats = get_racial_attribute_bonuses(race)
    job_stats = get_base_stats_by_job(job)

    return tuple(
        floor(base_main_stat * (job_stat / 100)) + race_stats[index] for index, job_stat in enumerate(job_stats)
    )


def calculate_action_damage(source, action):
    strength, dexterity, vitality, intelligence, mind = get_base_stats_by_job(source.job)

    if action.affected_by is Attribute.ATTACK_POWER:
        if source.job in [Job.BARD, Job.MACHINIST, Job.NINJA]:
            job_attribute_modifier = dexterity
            attack_rating = source.stats[Attribute.DEXTERITY]
        else:
            job_attribute_modifier = strength
            attack_rating = source.stats[Attribute.STRENGTH]

        weapon_damage = source.physical_damage
    elif action.affected_by is Attribute.ATTACK_MAGIC_POTENCY:
        if source.job in [Job.ASTROLOGIAN, Job.SCHOLAR, Job.WHITE_MAGE]:
            job_attribute_modifier = mind
            attack_rating = source.stats[Attribute.MIND]
        else:
            job_attribute_modifier = intelligence
            attack_rating = source.stats[Attribute.INTELLIGENCE]

        weapon_damage = source.magic_damage
    elif action.affected_by is Attribute.HEALING_MAGIC_POTENCY:
        job_attribute_modifier = mind
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
