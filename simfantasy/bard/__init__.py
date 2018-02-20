from simfantasy.bard.actions import StraightShotBuff, StraightShotCast, WindbiteCast, WindbiteDebuff
from simfantasy.enums import Job, Role
from simfantasy.simulator import Actor


class Bard(Actor):
    job = Job.BARD
    role = Role.DPS

    def decide(self):
        if not self.has_aura(StraightShotBuff):
            return self.cast(StraightShotCast)

        if not self.target.has_aura(WindbiteDebuff):
            return self.cast(WindbiteCast)
