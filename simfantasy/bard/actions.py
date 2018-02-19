from datetime import timedelta

from simfantasy.enums import Attribute
from simfantasy.simulator import Actor, ApplyAuraEvent, Aura, CastEvent, ExpireAuraEvent


class StraightShotBuff(Aura):
    duration = timedelta(seconds=30)


class StraightShotCast(CastEvent):
    affected_by = Attribute.ATTACK_POWER
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


class WindbiteCast(CastEvent):
    def execute(self):
        super().execute()

        aura = WindbiteDebuff(source=self.source)

        self.sim.schedule_in(ApplyAuraEvent(sim=self.sim, target=self.target, aura=aura))
        self.sim.schedule_in(ExpireAuraEvent(sim=self.sim, target=self.target, aura=aura), delta=aura.duration)
