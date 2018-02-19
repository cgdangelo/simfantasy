import logging
from datetime import timedelta
from heapq import heappop, heapify, heappush

from simfantasy.common_math import calculate_base_stats
from simfantasy.enums import Race, Job, Attribute

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

logstream = logging.StreamHandler()
logstream.setFormatter(logging.Formatter('%(relativeCreated)s [%(levelname)s] %(message)s\n'))

logger.addHandler(logstream)


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
        from simfantasy.events import CombatEndEvent

        logger.info('Running!')

        self.schedule_in(CombatEndEvent(sim=self), self.combat_length)

        while self.current_time <= self.combat_length and len(self.events) > 0:
            for actor in self.actors:
                if actor.ready:
                    actor.decide()

            time, event = heappop(self.events)

            logger.debug('%s %s', time, event)

            event.execute()

            self.current_time = time


class Aura:
    duration: timedelta


class Actor:
    def __init__(self,
                 sim: Simulation,
                 race: Race,
                 # TODO Need a better way to assign this.
                 job: Job,
                 level: int = None,
                 physical_damage: int = None,
                 magic_damage: int = None,
                 target=None):
        self.sim = sim
        self.race = race
        self.job = job
        self.level = level or 70
        self.physical_damage = physical_damage
        self.magic_damage = magic_damage
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
