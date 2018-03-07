from enum import Enum, Flag, auto


class Attribute(Enum):
    """Primary and secondary attributes."""

    STRENGTH = auto()
    DEXTERITY = auto()
    VITALITY = auto()
    INTELLIGENCE = auto()
    MIND = auto()

    CRITICAL_HIT = auto()
    DETERMINATION = auto()
    DIRECT_HIT = auto()

    DEFENSE = auto()
    MAGIC_DEFENSE = auto()

    ATTACK_POWER = auto()
    SKILL_SPEED = auto()

    ATTACK_MAGIC_POTENCY = auto()
    HEALING_MAGIC_POTENCY = auto()
    SPELL_SPEED = auto()

    TENACITY = auto()
    PIETY = auto()


class Race(Flag):
    """Races and clans."""

    WILDWOOD = auto()
    DUSKWIGHT = auto()
    ELEZEN = WILDWOOD | DUSKWIGHT

    MIDLANDER = auto()
    HIGHLANDER = auto()
    HYUR = MIDLANDER | HIGHLANDER

    PLAINSFOLK = auto()
    DUNESFOLK = auto()
    LALAFELL = PLAINSFOLK | DUNESFOLK

    SEEKER_OF_THE_SUN = auto()
    KEEPER_OF_THE_MOON = auto()
    MIQOTE = SEEKER_OF_THE_SUN | KEEPER_OF_THE_MOON

    SEA_WOLF = auto()
    HELLSGUARD = auto()
    ROEGADYN = SEA_WOLF | HELLSGUARD

    RAEN = auto()
    XAELA = auto()
    AU_RA = RAEN | XAELA

    ENEMY = auto()


class Job(Enum):
    """Base classes and job specializations."""

    PALADIN = auto()
    GLADIATOR = auto()

    WARRIOR = auto()
    MARAUDER = auto()

    MONK = auto()
    PUGILIST = auto()

    DRAGOON = auto()
    LANCER = auto()

    BARD = auto()
    ARCHER = auto()

    WHITE_MAGE = auto()
    CONJURER = auto()

    BLACK_MAGE = auto()
    THAUMATURGE = auto()

    SUMMONER = auto()
    SCHOLAR = auto()
    ARCANIST = auto()

    NINJA = auto()
    ROGUE = auto()

    DARK_KNIGHT = auto()

    ASTROLOGIAN = auto()

    MACHINIST = auto()

    SAMURAI = auto()

    RED_MAGE = auto()

    ENEMY = auto()


class Slot(Flag):
    """Slots where an item an be equipped."""

    WEAPON = auto()
    HEAD = auto()
    BODY = auto()
    HANDS = auto()
    WAIST = auto()
    LEGS = auto()
    FEET = auto()
    OFF_HAND = auto()
    EARRINGS = auto()
    NECKLACE = auto()
    BRACELET = auto()
    LEFT_RING = auto()
    RIGHT_RING = auto()
    RING = LEFT_RING | RIGHT_RING
    MATERIA = auto()


class Role(Enum):
    """Class archetypes."""

    DPS = auto()
    HEALER = auto()
    TANK = auto()


class RefreshBehavior(Enum):
    EXTEND_TO_MAX = auto()
    RESET = auto()


class Resource(Enum):
    HP = auto()
    MP = auto()
    REPERTOIRE = auto()
    TP = auto()
