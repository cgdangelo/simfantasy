from datetime import timedelta

from simfantasy.bard import Bard
from simfantasy.enums import Race, Job
from simfantasy.simulator import Simulation, Actor

if __name__ == '__main__':
    sim = Simulation(combat_length=timedelta(seconds=60))

    enemy = Actor(sim=sim, race=Race.ENEMY)
    bard = Bard(sim=sim, race=Race.HIGHLANDER, target=enemy)

    sim.run()
