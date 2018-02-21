from simfantasy.bard.actions import StraightShotBuff, StraightShotCast, WindbiteCast, WindbiteDebuff
from simfantasy.enums import Job
from simfantasy.simulator import Actor


class Bard(Actor):
    job = Job.BARD

    def decide(self):
        if not self.has_aura(StraightShotBuff):
            return self.cast(StraightShotCast)

        if not self.target.has_aura(WindbiteDebuff):
            return self.cast(WindbiteCast)
