import logging
from datetime import timedelta
from enum import Enum, auto
from heapq import heapify, heappop, heappush
from math import floor

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

logstream = logging.StreamHandler()
logstream.setFormatter(logging.Formatter('%(asctime)s - %(pathname)s @ %(lineno)d - %(levelname)s - %(message)s'))

logger.addHandler(logstream)

main_stat_per_level = [
    20, 21, 22, 24, 26, 27, 29, 31, 33, 35, 36, 38, 41, 44, 46, 49, 52, 54, 57, 60, 63, 67, 71, 74, 78, 81, 85, 89, 92,
    97, 101, 106, 110, 115, 119, 124, 128, 134, 139, 144, 150, 155, 161, 166, 171, 177, 183, 189, 196, 202, 204, 205,
    207, 209, 210, 212, 214, 215, 217, 218, 224, 228, 236, 244, 252, 260, 268, 276, 284, 292
]

sub_per_level = [
    56, 57, 60, 62, 65, 68, 70, 73, 76, 78, 82, 85, 89, 93, 96, 100, 104, 109, 113, 116, 122, 127, 133, 138, 144, 150,
    155, 162, 168, 173, 181, 188, 194, 202, 209, 215, 223, 229, 236, 244, 253, 263, 272, 283, 292, 302, 311, 322, 331,
    341, 342, 344, 345, 346, 347, 349, 350, 351, 352, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363, 364,
]

divisor_per_level = [
    56, 57, 60, 62, 65, 68, 70, 73, 76, 78, 82, 85, 89, 93, 96, 100, 104, 109, 113, 116, 122, 127, 133, 138, 144, 150,
    155, 162, 168, 173, 181, 188, 194, 202, 209, 215, 223, 229, 236, 244, 253, 263, 272, 283, 292, 302, 311, 322, 331,
    341, 393, 444, 496, 548, 600, 651, 703, 755, 806, 858, 941, 1032, 1133, 1243, 1364, 1497, 1643, 1802, 1978, 2170,
]


class Attribute(Enum):
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


class Race(Enum):
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


def get_racial_attribute_bonuses(race: Race):
    if race == Race.WILDWOOD:
        return 0, 3, -1, 2, -1
    elif race == Race.DUSKWIGHT:
        return 0, 0, -1, 3, 1
    elif race == Race.MIDLANDER:
        return 2, -1, 0, 3, -1
    elif race == Race.HIGHLANDER:
        return 3, 0, 2, -2, 0
    elif race == Race.PLAINSFOLK:
        return -1, 3, -1, 2, 0
    elif race == Race.DUNESFOLK:
        return -1, 1, -2, 2, 3
    elif race == Race.SEEKER_OF_THE_SUN:
        return 2, 3, 0, -1, -1
    elif race == Race.KEEPER_OF_THE_MOON:
        return -1, 2, -2, 1, 3
    elif race == Race.SEA_WOLF:
        return 2, -1, 3, -2, 1
    elif race == Race.HELLSGUARD:
        return 0, -2, 3, 0, 2
    elif race == Race.RAEN:
        return -1, 2, -1, 0, 3
    elif race == Race.XAELA:
        return 3, 0, 2, 0, -2
    else:
        return 0, 0, 0, 0, 0


def get_base_stat_by_job(job: Job):
    if job == Job.GLADIATOR:
        return 95, 90, 100, 50, 95
    elif job == Job.PUGILIST:
        return 100, 100, 95, 45, 85
    elif job == Job.MARAUDER:
        return 100, 90, 100, 30, 50
    elif job == Job.LANCER:
        return 105, 95, 100, 40, 60
    elif job == Job.ARCHER:
        return 85, 105, 95, 80, 75
    elif job == Job.CONJURER:
        return 50, 100, 95, 100, 105
    elif job == Job.THAUMATURGE:
        return 40, 95, 95, 105, 70
    elif job == Job.PALADIN:
        return 100, 95, 110, 60, 100
    elif job == Job.MONK:
        return 110, 105, 100, 50, 90
    elif job == Job.WARRIOR:
        return 105, 95, 110, 40, 55
    elif job == Job.DRAGOON:
        return 115, 100, 105, 45, 65
    elif job == Job.BARD:
        return 90, 115, 100, 85, 80
    elif job == Job.WHITE_MAGE:
        return 55, 105, 100, 105, 115
    elif job == Job.BLACK_MAGE:
        return 45, 100, 100, 115, 75
    elif job == Job.ARCANIST:
        return 85, 95, 95, 105, 75
    elif job == Job.SUMMONER:
        return 90, 100, 100, 115, 80
    elif job == Job.SCHOLAR:
        return 90, 100, 100, 105, 115
    elif job == Job.ROGUE:
        return 80, 100, 95, 60, 70
    elif job == Job.NINJA:
        return 85, 110, 100, 65, 75
    elif job == Job.MACHINIST:
        return 85, 115, 100, 80, 85
    elif job == Job.DARK_KNIGHT:
        return 105, 95, 110, 60, 40
    elif job == Job.ASTROLOGIAN:
        return 50, 100, 100, 105, 115
    elif job == Job.SAMURAI:
        return 112, 108, 100, 60, 50
    elif job == Job.RED_MAGE:
        return 55, 105, 100, 115, 110
    else:
        return 0, 0, 0, 0, 0


def calculate_base_stats(level: int, job: Job, race: Race):
    base_main_stat = main_stat_per_level[level - 1]

    race_stats = get_racial_attribute_bonuses(race)
    job_stats = get_base_stat_by_job(job)

    return tuple(
        floor(base_main_stat * (job_stat / 100)) + race_stats[index] for index, job_stat in enumerate(job_stats)
    )


class Simulation:
    def __init__(self, combat_length: timedelta = timedelta(minutes=5)):
        self.combat_length = combat_length

        self.actors = []
        self.current_time = timedelta()
        self.events = []

        heapify(self.events)

    def add_actor(self, actor):
        actor not in self.actors and self.actors.append(actor)

    def schedule_in(self, event, delta: timedelta = None):
        delta = delta or timedelta()

        heappush(self.events, (self.current_time + delta, event))

    def run(self):
        self.schedule_in(CombatEndEvent(sim=self), self.combat_length)

        while self.current_time <= self.combat_length and len(self.events) > 0:
            for actor in self.actors:
                if actor.ready:
                    actor.decide()

            time, event = heappop(self.events)

            print(time, event)

            event.execute()

            self.current_time = time


class Aura:
    duration: timedelta


class Event:
    def __init__(self, sim: Simulation):
        self.sim = sim

    def __lt__(self, other):
        return False

    def __str__(self):
        return '<{0}>'.format(self.__class__.__name__)


class Actor:
    def __init__(self,
                 sim: Simulation,
                 race: Race,
                 # TODO Need a better way to assign this.
                 job: Job,
                 level: int = None,
                 target=None):
        self.sim = sim
        self.race = race
        self.job = job
        self.level = level or 70
        self.target = target

        self.animation_lock = timedelta()
        self.gcd_lock = timedelta()
        self.ready = True
        self.auras = []

        self.sim.add_actor(self)
        self.stats = dict(zip(
            (Attribute.STRENGTH, Attribute.DEXTERITY, Attribute.VITALITY, Attribute.INTELLIGENCE, Attribute.MIND),
            calculate_base_stats(self.level, self.job, race)
        ))

    def decide(self):
        pass

    def has_aura(self, aura_class):
        return any(isinstance(aura, aura_class) for aura in self.auras)

    def cast(self, cast_class, target=None):
        self.sim.schedule_in(cast_class(sim=self.sim, source=self, target=target or self.target))


class Bard(Actor):
    job = Job.BARD

    def decide(self):
        if self.target is None:
            self.target = Actor(sim=self.sim, race=Race.ENEMY, job=Job.ENEMY)

        if not self.has_aura(StraightShotBuff):
            return self.cast(StraightShotCast)

        if not self.target.has_aura(WindbiteDebuff):
            return self.cast(WindbiteCast)


class CombatEndEvent(Event):
    def execute(self):
        self.sim.events.clear()


class AuraEvent(Event):
    def __init__(self, sim: Simulation, target: Actor, aura: Aura):
        super().__init__(sim=sim)

        self.target = target
        self.aura = aura

    def __str__(self):
        return '<{0} aura={1}>'.format(self.__class__.__name__, self.aura.__class__.__name__)


class ApplyAuraEvent(AuraEvent):
    def execute(self):
        self.target.auras.append(self.aura)


class ExpireAuraEvent(AuraEvent):
    def execute(self):
        self.target.auras.remove(self.aura)


class PlayerReadyEvent(Event):
    def __init__(self, sim: Simulation, actor: Actor):
        super().__init__(sim=sim)

        self.actor = actor

    def execute(self):
        self.actor.ready = True


class CastEvent(Event):
    def __init__(self, sim: Simulation, source: Actor, target: Actor = None, off_gcd: bool = None):
        super().__init__(sim=sim)

        self.animation = timedelta(seconds=0.75)
        self.gcd = timedelta(seconds=3) if not off_gcd else timedelta()

        self.source = source
        self.target = target

    def execute(self):
        self.source.ready = False
        self.sim.schedule_in(PlayerReadyEvent(sim=self.sim, actor=self.source), delta=max(self.animation, self.gcd))


class StraightShotBuff(Aura):
    duration = timedelta(seconds=30)


class StraightShotCast(CastEvent):
    def execute(self):
        super().execute()

        aura = StraightShotBuff()

        self.sim.schedule_in(ApplyAuraEvent(sim=self.sim, target=self.source, aura=aura))
        self.sim.schedule_in(ExpireAuraEvent(sim=self.sim, target=self.source, aura=aura), delta=aura.duration)


class WindbiteDebuff(Aura):
    def __init__(self, source: Actor):
        super().__init__()

        self.source = source

    @property
    def duration(self):
        return timedelta(seconds=15) if self.source.level < 64 else timedelta(seconds=30)


class WindbiteCast(CastEvent):
    def execute(self):
        super().execute()

        aura = WindbiteDebuff(source=self.source)

        self.sim.schedule_in(ApplyAuraEvent(sim=self.sim, target=self.target, aura=aura))
        self.sim.schedule_in(ExpireAuraEvent(sim=self.sim, target=self.target, aura=aura), delta=aura.duration)


if __name__ == '__main__':
    sim = Simulation(combat_length=timedelta(seconds=60))

    bard = Bard(sim=sim, race=Race.HIGHLANDER, job=Job.BARD)

    sim.run()
