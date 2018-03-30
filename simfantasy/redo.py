from datetime import datetime, timedelta
from heapq import heapify, heappop, heappush


class Simulation:
    def __init__(self, combat_length):
        self.combat_length = combat_length
        self.start_time = None
        self.current_time = None
        self.actors = []
        self.events = []
        heapify(self.events)
        self.server_ticked = None
        self.combat_ended = None

    def add_actor(self, actor):
        self.actors.append(actor)

    def push_event(self, event):
        heappush(self.events, event)

    def pop_event(self):
        return heappop(self.events)

    def clear_events(self):
        self.events.clear()

    @property
    def relative_timestamp(self):
        return format((self.current_time - self.start_time).total_seconds(), '.3f')

    def run(self):
        self.start_time = self.current_time = datetime.now()

        self.server_ticked = ServerTicked(self)
        self.server_ticked.schedule()

        self.combat_ended = CombatEnded(self)
        self.combat_ended.schedule(self.combat_length)

        for actor in self.actors:
            actor.readied.schedule()

        while len(self.events) > 0:
            event = self.pop_event()

            if event.unscheduled is True:
                continue

            self.current_time = event.timestamp
            event.execute()

        print('Finished in {runtime}'.format(runtime=datetime.now() - self.start_time))


class Event:
    def __init__(self, sim):
        self.sim = sim
        self.timestamp = None
        self.unscheduled = False

    def schedule(self, delta=None):
        if delta is None:
            delta = timedelta()

        self.timestamp = self.sim.current_time + delta

        self.sim.push_event(self)

    def unschedule(self):
        self.unscheduled = True

    def execute(self):
        print('{time} Executing {event}'.format(time=self.sim.relative_timestamp, event=self.__class__.__name__))

        self.unscheduled = False

    def __lt__(self, other):
        return self.timestamp < other.timestamp


class CombatEnded(Event):
    def execute(self):
        self.sim.clear_events()


class ServerTicked(Event):
    def execute(self):
        super().execute()

        self.schedule(timedelta(seconds=3))


class ActorReadied(Event):
    def __init__(self, sim, actor):
        super().__init__(sim)

        self.actor = actor

    def execute(self):
        self.unscheduled = False

        for decision in self.actor.decide():
            try:
                action, conditions = decision
            except TypeError:
                action, conditions = decision, None

            if not action.ready:
                continue

            if conditions is None or conditions() is True:
                action.perform()
                return

        self.schedule(timedelta(milliseconds=100))


class DamageDealt(Event):
    pass


class Action:
    def __init__(self, source):
        self.source = source

        self.animation = timedelta(seconds=0.75)
        self.base_cast_time = timedelta()
        self.off_gcd = False
        self.potency = 0
        self.recast_time = timedelta()
        self.usable_at = None

        self.damage = DamageDealt(self.source.sim)

    @property
    def execute_time(self):
        return max(self.animation, self.cast_time)

    @property
    def cast_time(self):
        return self.base_cast_time

    def perform(self):
        print('{time} {actor} performs {action}'.format(time=self.source.sim.relative_timestamp, actor=self.source.name,
                                                        action=self.__class__.__name__))

        self.source.animation_unlock_at = self.source.sim.current_time + self.animation

        if not self.off_gcd:
            self.source.gcd_unlock_at = self.source.sim.current_time + timedelta(seconds=2.5)

        self.source.readied.schedule(self.animation)

        self.usable_at = self.source.sim.current_time + self.recast_time

        if self.potency > 0:
            self.damage.schedule(self.execute_time)

    @property
    def ready(self):
        if self.source.animation_unlock_at is not None \
                and self.source.animation_unlock_at > self.source.sim.current_time:
            return False

        if not self.off_gcd \
                and self.source.gcd_unlock_at is not None \
                and self.source.gcd_unlock_at > self.source.sim.current_time:
            return False

        if self.usable_at is not None \
                and self.usable_at > self.source.sim.current_time:
            return False

        return True

    def schedule_aura_events(self, aura):
        aura.applied.schedule(self.execute_time)
        aura.expired.schedule(self.execute_time + aura.duration)


class HeavyShot(Action):
    def __init__(self, source):
        super().__init__(source)

        self.potency = 150


class RagingStrikes(Action):
    def __init__(self, source):
        super().__init__(source)

        self.off_gcd = True
        self.recast_time = timedelta(seconds=90)

    def perform(self):
        super().perform()

        self.schedule_aura_events(self.source.buffs.raging_strikes)


class AuraEvent(Event):
    def __init__(self, sim, aura):
        super().__init__(sim)

        self.aura = aura


class AuraApplied(AuraEvent):
    def execute(self):
        super().execute()

        print('{time} {actor} gains {aura}'.format(
            time=self.aura.source.sim.relative_timestamp,
            actor=self.aura.source.name,
            aura=self.aura.__class__.__name__)
        )


class AuraExpired(AuraEvent):
    def execute(self):
        super().execute()

        print('{time} {actor} loses {aura}'.format(
            time=self.aura.source.sim.relative_timestamp,
            actor=self.aura.source.name,
            aura=self.aura.__class__.__name__)
        )


class Aura:
    def __init__(self, source):
        self.source = source
        self.duration = None
        self.applied = AuraApplied(source.sim, self)
        self.expired = AuraExpired(source.sim, self)


class RagingStrikesAura(Aura):
    def __init__(self, source):
        super().__init__(source)

        self.duration = timedelta(seconds=20)


class Actor:
    class Actions:
        def __init__(self, source):
            self.heavy_shot = HeavyShot(source)
            self.raging_strikes = RagingStrikes(source)

    class Buffs:
        def __init__(self, source):
            self.raging_strikes = RagingStrikesAura(source)

    def __init__(self, sim, name):
        self.sim = sim
        self.name = name

        self.actions = Actor.Actions(self)
        self.buffs = Actor.Buffs(self)

        self.animation_unlock_at = None
        self.gcd_unlock_at = None
        self.readied = ActorReadied(sim, self)

        self.sim.add_actor(self)

    def decide(self):
        yield self.actions.raging_strikes
        yield self.actions.heavy_shot


if __name__ == '__main__':
    s = Simulation(combat_length=timedelta(minutes=5))
    bard = Actor(s, name='Dikembe')
    s.run()
