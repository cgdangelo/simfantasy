from datetime import timedelta

from simfantasy.enums import Attribute
from simfantasy.events import ApplyAuraEvent, CastEvent, ExpireAuraEvent
from simfantasy.simulator import Actor, Aura


class BardEvent(CastEvent):
    affected_by = Attribute.ATTACK_POWER
    hastened_by = Attribute.SKILL_SPEED


class StraightShotBuff(Aura):
    duration = timedelta(seconds=30)

    def apply(self, target: Actor):
        target.stats[Attribute.CRITICAL_HIT] *= 1.1

    def expire(self, target: Actor):
        target.stats[Attribute.CRITICAL_HIT] /= 1.1


class StraightShotCast(BardEvent):
    potency = 140

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


class WindbiteCast(BardEvent):
    @property
    def potency(self):
        return 50 if self.source.level < 64 else 55

    def execute(self):
        super().execute()

        aura = WindbiteDebuff(source=self.source)

        self.sim.schedule_in(ApplyAuraEvent(sim=self.sim, target=self.target, aura=aura))
        self.sim.schedule_in(ExpireAuraEvent(sim=self.sim, target=self.target, aura=aura), delta=aura.duration)
