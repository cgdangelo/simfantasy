from datetime import timedelta

from simfantasy.enums import Attribute
from simfantasy.simulator import Actor, Aura, Simulation


class Event:
    def __init__(self, sim: Simulation):
        self.sim = sim

    def __lt__(self, other):
        return False

    def __str__(self):
        return '<{0}>'.format(self.__class__.__name__)


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
    affected_by: Attribute
    potency: int

    def __init__(self, sim: Simulation, source: Actor, target: Actor = None, off_gcd: bool = None):
        super().__init__(sim=sim)

        self.animation = timedelta(seconds=0.75)
        self.gcd = timedelta(seconds=3) if not off_gcd else timedelta()

        self.source = source
        self.target = target

    def execute(self):
        self.source.ready = False
        self.sim.schedule_in(PlayerReadyEvent(sim=self.sim, actor=self.source), delta=max(self.animation, self.gcd))
