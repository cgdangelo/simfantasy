from datetime import timedelta

from simfantasy.bard import Bard
from simfantasy.enums import Job, Race
from simfantasy.simulator import Simulation

if __name__ == '__main__':
    sim = Simulation(combat_length=timedelta(seconds=60))

    bard = Bard(sim=sim, race=Race.HIGHLANDER, job=Job.BARD)

    sim.run()
