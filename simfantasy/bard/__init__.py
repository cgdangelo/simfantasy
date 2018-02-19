from simfantasy.bard.actions import StraightShotBuff, StraightShotCast, WindbiteCast, WindbiteDebuff
from simfantasy.simulator import Actor


class Bard(Actor):
    def decide(self):
        if not self.has_aura(StraightShotBuff):
            return self.cast(StraightShotCast)

        if not self.target.has_aura(WindbiteDebuff):
            return self.cast(WindbiteCast)
