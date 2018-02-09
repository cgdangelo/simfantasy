import heapq
from datetime import timedelta, datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

logstream = logging.StreamHandler()
logstream.setFormatter(logging.Formatter('%(asctime)s - %(pathname)s @ %(lineno)d - %(levelname)s - %(message)s'))

logger.addHandler(logstream)


class Event:
    def __init__(self, simulation):
        self.simulation = simulation
        self.scheduled_at = simulation.event_manager.current_time + self.scheduled_in()

    def scheduled_in(self):
        return timedelta()

    def execute(self):
        logger.debug(Event.execute.__qualname__)

    def __lt__(self, other):
        return self.scheduled_at < other.scheduled_at

    def __repr__(self):
        return '{0} {1}'.format(self.__class__.__name__, self.scheduled_at)


class CastEvent(Event):
    def __init__(self, simulation, source):
        self.source = source

        super().__init__(simulation)

    def scheduled_in(self):
        return max(self.source.gcd_lock, self.source.animation_lock, timedelta())


class ExpireAuraEvent(Event):
    def __init__(self, simulation, actor, aura, expire_in=None):
        self.actor = actor
        self.aura = aura

        self.expire_in = expire_in or aura.duration

        super().__init__(simulation)

    def scheduled_in(self):
        return self.expire_in

    def execute(self):
        logger.debug("Expire!")

        self.actor.auras.remove(self.aura)


class StraightShotCastEvent(CastEvent):
    def execute(self):
        logger.debug("Buff!")

        buff = StraightShotBuff()

        self.source.auras.append(buff)

        self.simulation.event_manager.add_event(
            ExpireAuraEvent(self.simulation,
                            actor=self.source,
                            aura=buff)
        )


class StraightShotBuff:
    duration = timedelta(seconds=30)


class EventManager:
    def __init__(self):
        self.events = []
        self.current_time = datetime.now()
        self.events_handled = 0

    def add_event(self, event: Event):
        heapq.heappush(self.events, event)

    def __next__(self):
        try:
            event = heapq.heappop(self.events)

            self.events_handled += 1
            self.current_time += event.scheduled_in()

            event.execute()

            return event
        except IndexError:
            return None


class ServerTickEvent(Event):
    def execute(self):
        logger.debug('Tick!')

    def scheduled_in(self):
        return timedelta(milliseconds=333)


class SimulationEndEvent(Event):
    def execute(self):
        logger.debug('Finished!')
        logger.debug('Events handled = {0}'.format(self.simulation.event_manager.events_handled))

        exit(0)


class Actor:
    def __init__(self):
        self.auras = []
        self.gcd_lock = timedelta()
        self.animation_lock = timedelta()

    def decide_action(self, simulation):
        pass

    def has_buff(self, buff_class):
        return any([isinstance(aura, buff_class) for aura in self.auras])


class Bard(Actor):
    def decide_action(self, simulation):
        if not self.has_buff(StraightShotBuff):
            return StraightShotCastEvent(simulation, source=self)


class Simulation:
    def __init__(self, max_length=None):
        self.event_manager = EventManager()
        self.actors = []
        self.max_length = max_length or 300
        self.start_time = None

    def run(self):
        self.start_time = datetime.now()

        while True:
            next(self.event_manager)

            for actor in self.actors:
                action = actor.decide_action(self)

                if action is not None:
                    self.event_manager.add_event(action)

            if self.event_manager.current_time - self.start_time >= timedelta(seconds=self.max_length):
                self.event_manager.add_event(SimulationEndEvent(simulation=self))


if __name__ == '__main__':
    sim = Simulation()
    sim.actors.append(Bard())
    sim.run()
