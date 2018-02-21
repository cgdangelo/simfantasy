from datetime import timedelta

import numpy

from simfantasy.enums import Attribute
from simfantasy.events import ApplyAuraEvent, CastEvent, ExpireAuraEvent
from simfantasy.simulator import Actor, Aura


class BardEvent(CastEvent):
    affected_by = Attribute.ATTACK_POWER
    hastened_by = Attribute.SKILL_SPEED

    @property
    def direct_damage(self) -> int:
        direct_damage = super().direct_damage

        if self.source.level >= 20:
            direct_damage *= 1.1

        if self.source.level >= 40:
            direct_damage *= 1.2

        return direct_damage


class StraighterShotBuff(Aura):
    duration = timedelta(seconds=10)


class StraightShotBuff(Aura):
    duration = timedelta(seconds=30)

    def apply(self, target: Actor):
        target.stats[Attribute.CRITICAL_HIT] *= 1.1

    def expire(self, target: Actor):
        target.stats[Attribute.CRITICAL_HIT] /= 1.1


class StraightShotCast(BardEvent):
    potency = 140

    @property
    def critical_hit_chance(self):
        return 100.0 if self.source.has_aura(StraighterShotBuff) else super().critical_hit_chance

    def execute(self):
        super().execute()

        aura = StraightShotBuff()

        self.sim.schedule_in(ApplyAuraEvent(sim=self.sim, target=self.source, aura=aura))
        self.sim.schedule_in(ExpireAuraEvent(sim=self.sim, target=self.source, aura=aura), delta=aura.duration)

        straighter_shots = [aura for aura in self.source.auras if isinstance(aura, StraighterShotBuff)]

        if len(straighter_shots) > 0:
            for straighter_shot in straighter_shots:
                print('Removing %s', straighter_shot)
                self.source.auras.remove(straighter_shot)


class WindbiteDebuff(Aura):
    def __init__(self, source: Actor):
        super().__init__()

        self.source = source

    @property
    def duration(self):
        return timedelta(seconds=15 if self.source.level < 64 else 30)


class WindbiteCast(BardEvent):
    @property
    def potency(self):
        return 60 if self.source.level < 64 else 120

    def execute(self):
        super().execute()

        aura = WindbiteDebuff(source=self.source)

        self.sim.schedule_in(ApplyAuraEvent(sim=self.sim, target=self.target, aura=aura))
        self.sim.schedule_in(ExpireAuraEvent(sim=self.sim, target=self.target, aura=aura), delta=aura.duration)


class VenomousBiteDebuff(Aura):
    def __init__(self, source: Actor):
        super().__init__()

        self.source = source

    @property
    def duration(self):
        return timedelta(seconds=15 if self.source.level < 64 else 30)


class VenomousBiteCast(BardEvent):
    @property
    def potency(self):
        return 100 if self.source.level < 64 else 120

    def execute(self):
        super().execute()

        aura = VenomousBiteDebuff(source=self.source)

        self.sim.schedule_in(ApplyAuraEvent(sim=self.sim, target=self.target, aura=aura))
        self.sim.schedule_in(ExpireAuraEvent(sim=self.sim, target=self.target, aura=aura), delta=aura.duration)


class HeavyShotCast(BardEvent):
    potency = 150

    def execute(self):
        super().execute()

        if numpy.random.uniform() <= 0.2:
            aura = StraighterShotBuff()

            self.sim.schedule_in(ApplyAuraEvent(sim=self.sim, target=self.source, aura=aura))
            self.sim.schedule_in(ExpireAuraEvent(sim=self.sim, target=self.source, aura=aura), delta=aura.duration)
