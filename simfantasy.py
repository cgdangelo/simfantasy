import logging
from datetime import timedelta
from heapq import heapify, heappop, heappush

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

logstream = logging.StreamHandler()
logstream.setFormatter(logging.Formatter('%(asctime)s - %(pathname)s @ %(lineno)d - %(levelname)s - %(message)s'))

logger.addHandler(logstream)


class Simulation:
    def __init__(self, combat_length: timedelta = None):
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
        while self.current_time < self.combat_length:
            # self.schedule_in(event=ServerTickEvent(sim=self), delta=timedelta(seconds=3))

            for actor in self.actors:
                if actor.ready:
                    actor.decide(sim=self)

            time, event = heappop(self.events)

            print(time, event)

            event.execute()

            self.current_time = time


class Actor:
    def __init__(self, target=None, level: int = None):
        self.animation_lock = timedelta()
        self.gcd_lock = timedelta()
        self.target = target
        self.ready = True
        self.level = level or 70

        self.auras = []

    def decide(self, sim: Simulation):
        pass


class Bard(Actor):
    def decide(self, sim: Simulation):
        if self.target is None:
            self.target = Actor()

        if not any(isinstance(aura, StraightShotBuff) for aura in self.auras):
            return sim.schedule_in(StraightShotCast(sim=sim, source=self))

        if not any(isinstance(aura, WindbiteDebuff) for aura in self.target.auras):
            return sim.schedule_in(WindbiteCast(sim=sim, source=self, target=self.target))


class Aura:
    duration: timedelta


class Event:
    def __init__(self, sim: Simulation):
        self.sim = sim

    def __lt__(self, other):
        return False


class ServerTickEvent(Event):
    def execute(self):
        pass


class AuraEvent(Event):
    def __init__(self, sim: Simulation, target: Actor, aura: Aura):
        super().__init__(sim=sim)

        self.target = target
        self.aura = aura


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

    bard = Bard()

    sim.add_actor(bard)
    sim.run()
