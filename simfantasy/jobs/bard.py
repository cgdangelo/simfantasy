from datetime import timedelta
from math import floor
from typing import Dict

import numpy

from simfantasy.enums import Attribute, Job
from simfantasy.events import ApplyAuraEvent, CastEvent, ExpireAuraEvent
from simfantasy.simulator import Actor, Aura


class Bard(Actor):
    job = Job.BARD

    def calculate_base_stats(self) -> Dict[Attribute, int]:
        base_stats = super().calculate_base_stats()

        if self.level >= 20:
            base_stats[Attribute.DEXTERITY] += 8

        if self.level >= 40:
            base_stats[Attribute.DEXTERITY] += 16

        if self.level >= 60:
            base_stats[Attribute.DEXTERITY] += 24

        return base_stats

    def decide(self):
        if not self.has_aura(StraightShotBuff) or self.has_aura(StraighterShotBuff):
            return self.cast(StraightShotCast)

        if not self.target.has_aura(WindbiteDebuff):
            return self.cast(WindbiteCast)

        if not self.target.has_aura(VenomousBiteDebuff):
            return self.cast(VenomousBiteCast)

        if not self.on_cooldown(RagingStrikesCast):
            return self.cast(RagingStrikesCast, target=self)

        return self.cast(HeavyShotCast)


class BardCastEvent(CastEvent):
    affected_by = Attribute.ATTACK_POWER
    hastened_by = Attribute.SKILL_SPEED

    @property
    def direct_damage(self) -> int:
        direct_damage = super().direct_damage

        if self.source.level >= 20:
            direct_damage = floor(direct_damage * 1.1)

        if self.source.level >= 40:
            direct_damage = floor(direct_damage * 1.2)

        if self.source.has_aura(RagingStrikesBuff):
            direct_damage = floor(direct_damage * 1.1)

        return direct_damage


class StraighterShotBuff(Aura):
    duration = timedelta(seconds=10)


class StraightShotBuff(Aura):
    duration = timedelta(seconds=30)

    def apply(self, target: Actor):
        target.stats[Attribute.CRITICAL_HIT] *= 1.1

    def expire(self, target: Actor):
        target.stats[Attribute.CRITICAL_HIT] /= 1.1


class StraightShotCast(BardCastEvent):
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
                self.source.auras.remove(straighter_shot)


class WindbiteDebuff(Aura):
    def __init__(self, source: Actor):
        super().__init__()

        self.source = source

    @property
    def duration(self):
        return timedelta(seconds=15 if self.source.level < 64 else 30)


class WindbiteCast(BardCastEvent):
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


class VenomousBiteCast(BardCastEvent):
    @property
    def potency(self):
        return 100 if self.source.level < 64 else 120

    def execute(self):
        super().execute()

        aura = VenomousBiteDebuff(source=self.source)

        self.sim.schedule_in(ApplyAuraEvent(sim=self.sim, target=self.target, aura=aura))
        self.sim.schedule_in(ExpireAuraEvent(sim=self.sim, target=self.target, aura=aura), delta=aura.duration)


class HeavyShotCast(BardCastEvent):
    potency = 150

    def execute(self):
        super().execute()

        if numpy.random.uniform() <= 0.2:
            aura = StraighterShotBuff()

            self.sim.schedule_in(ApplyAuraEvent(sim=self.sim, target=self.source, aura=aura))
            self.sim.schedule_in(ExpireAuraEvent(sim=self.sim, target=self.source, aura=aura), delta=aura.duration)


class RagingStrikesBuff(Aura):
    duration = timedelta(seconds=20)


class RagingStrikesCast(BardCastEvent):
    is_off_gcd = True
    recast_time = timedelta(seconds=80)

    @property
    def critical_hit_chance(self):
        return 0.0

    @property
    def direct_hit_chance(self):
        return 0.0

    def execute(self):
        super().execute()

        aura = RagingStrikesBuff()

        self.sim.schedule_in(ApplyAuraEvent(sim=self.sim, target=self.source, aura=aura))
        self.sim.schedule_in(ExpireAuraEvent(sim=self.sim, target=self.source, aura=aura), delta=aura.duration)
