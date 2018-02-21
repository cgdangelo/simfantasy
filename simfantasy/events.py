from datetime import timedelta

from simfantasy.common_math import calculate_direct_damage, calculate_gcd
from simfantasy.enums import Attribute
from simfantasy.simulator import Actor, Aura, Simulation


class Event:
    def __init__(self, sim: Simulation):
        self.sim = sim

    def __lt__(self, other):
        return False

    def __str__(self):
        return '<{cls}>'.format(cls=self.__class__.__name__)


class CombatEndEvent(Event):
    def execute(self):
        self.sim.events.clear()


class AuraEvent(Event):
    def __init__(self, sim: Simulation, target: Actor, aura: Aura):
        super().__init__(sim=sim)

        self.target = target
        self.aura = aura

    def __str__(self):
        return '<{cls} aura={aura} target={target}>'.format(cls=self.__class__.__name__,
                                                            aura=self.aura.__class__.__name__,
                                                            target=self.target.name)


class ApplyAuraEvent(AuraEvent):
    def execute(self):
        self.target.auras.append(self.aura)
        self.aura.apply(target=self.target)


class ExpireAuraEvent(AuraEvent):
    def execute(self):
        self.target.auras.remove(self.aura)
        self.aura.expire(target=self.target)


class PlayerReadyEvent(Event):
    def __init__(self, sim: Simulation, actor: Actor):
        super().__init__(sim=sim)

        self.actor = actor

    def execute(self):
        self.actor.ready = True

    def __str__(self):
        return '<{cls} actor={actor}>'.format(cls=self.__class__.__name__,
                                              actor=self.actor.name)


class CastEvent(Event):
    affected_by: Attribute
    hastened_by: Attribute
    potency: int

    def __init__(self, sim: Simulation, source: Actor, target: Actor = None, off_gcd: bool = None):
        super().__init__(sim=sim)

        self.animation = timedelta(seconds=0.75)
        self.gcd = timedelta(seconds=2.5) if not off_gcd else timedelta()

        self.source = source
        self.target = target

    def execute(self):
        self.source.ready = False
        self.sim.schedule_in(PlayerReadyEvent(sim=self.sim, actor=self.source),
                             delta=max(self.animation, calculate_gcd(self.source, self)))

        if self.__class__ not in self.source.statistics:
            self.source.statistics[self.__class__] = {
                'casts': [],
                'damage': [],
            }

        self.source.statistics[self.__class__]['casts'].append(self.sim.current_time)
        self.source.statistics[self.__class__]['damage'].append(
            (self.sim.current_time, calculate_direct_damage(self.source, self)))

    def __str__(self):
        return '<{cls} source={source} target={target}>'.format(
            cls=self.__class__.__name__,
            source=self.source.name,
            target=self.target.name,
        )
