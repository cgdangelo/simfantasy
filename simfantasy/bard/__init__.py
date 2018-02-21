from typing import Dict

from simfantasy.bard.actions import HeavyShotCast, StraightShotBuff, StraightShotCast, StraighterShotBuff, \
    VenomousBiteCast, VenomousBiteDebuff, WindbiteCast, WindbiteDebuff
from simfantasy.enums import Attribute, Job
from simfantasy.simulator import Actor


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

        return self.cast(HeavyShotCast)
