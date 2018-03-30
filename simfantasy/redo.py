import queue
from datetime import datetime, timedelta


class Simulation:
    def __init__(self, combat_length):
        self.combat_length = combat_length
        self.start_time = None
        self.current_time = None
        self.actors = []
        self.server_ticked = None
        self.combat_ended = None
        self.events = queue.PriorityQueue()

    def add_actor(self, actor):
        self.actors.append(actor)

    def push_event(self, event):
        # print('=>', event.timestamp, event.__class__.__name__)
        self.events.put((event.timestamp, datetime.now(), event))

    def pop_event(self):
        _, _, event = self.events.get()
        # print('<=', event.timestamp, event.__class__.__name__)
        return event

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
            if actor.name == 'Boss':
                continue

            actor.readied.schedule()

        while self.events.qsize() > 0:
            event = self.pop_event()

            if event.unscheduled is True:
                self.events.task_done()
                continue

            self.current_time = event.timestamp
            event.execute()
            self.events.task_done()

        print('Finished in {runtime}'.format(runtime=datetime.now() - self.start_time))


class Event:
    def __init__(self, sim):
        self.sim = sim
        self.timestamp = None
        self.unscheduled = False
        self.entry_time = None

    def schedule(self, delta=None):
        # self.entry_time = datetime.now()

        if delta is None:
            self.timestamp = self.sim.current_time
        else:
            self.timestamp = self.sim.current_time + delta

        self.sim.push_event(self)

    def unschedule(self):
        self.unscheduled = True

    def execute(self):
        print('>> {time} Executing {event}'.format(time=self.timestamp, event=self.__class__.__name__))

        self.unscheduled = False

    def __lt__(self, other):
        return self.timestamp < other.timestamp


class CombatEnded(Event):
    def execute(self):
        super().execute()

        while not self.sim.events.empty():
            try:
                self.sim.events.get(False)
            except queue.Empty:
                continue

            self.sim.events.task_done()


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
                self.schedule(action.execute_time)
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
        print('@@ {time} {actor} performs {action}'.format(time=self.source.sim.current_time, actor=self.source.name,
                                                           action=self.__class__.__name__))

        self.source.animation_unlock_at = self.source.sim.current_time + self.animation

        if not self.off_gcd:
            self.source.gcd_unlock_at = self.source.sim.current_time + timedelta(seconds=2.5)

        self.usable_at = self.source.sim.current_time + self.recast_time

        if self.potency > 0:
            self.damage.schedule(self.execute_time)

        # self.source.readied.schedule(self.execute_time)

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


class Stormbite(Action):
    def __init__(self, source):
        super().__init__(source)

        self.potency = 120

    def perform(self):
        super().perform()

        self.schedule_aura_events(self.source.target_data.stormbite)


class AuraEvent(Event):
    def __init__(self, sim, aura):
        super().__init__(sim)

        self.aura = aura


class AuraApplied(AuraEvent):
    def execute(self):
        super().execute()

        self.aura.apply()

        print('   {time} {target} gains {aura}'.format(
            time=self.timestamp,
            target=self.aura.target.name,
            aura=self.aura.__class__.__name__)
        )


class AuraExpired(AuraEvent):
    def execute(self):
        super().execute()

        self.aura.expire()

        print('   {time} {target} loses {aura}'.format(
            time=self.timestamp,
            target=self.aura.target.name,
            aura=self.aura.__class__.__name__)
        )


class Aura:
    def __init__(self, source, target=None):
        self.source = source
        self.target = target or source
        self.duration = None
        self.applied = AuraApplied(source.sim, self)
        self.expired = AuraExpired(source.sim, self)

    def apply(self):
        pass

    def expire(self):
        pass

    @property
    def remains(self):
        if self.expired.timestamp is None or self.expired.timestamp < self.source.sim.current_time:
            return timedelta()

        return self.expired.timestamp - self.applied.timestamp

    @property
    def up(self):
        return self.remains > timedelta()

    @property
    def down(self):
        return not self.up


class RagingStrikesAura(Aura):
    def __init__(self, source, target=None):
        super().__init__(source, target)

        self.duration = timedelta(seconds=20)


class DotTick(DamageDealt):
    def __init__(self, sim, aura):
        super().__init__(sim)

        self.aura = aura
        self.ticks_remain = None

    def execute(self):
        super().execute()

        if self.ticks_remain > 0:
            self.ticks_remain -= 1
            self.schedule(timedelta(seconds=3))


class DotAura(Aura):
    def __init__(self, source, target=None):
        super().__init__(source, target)

        self.dot = DotTick(source.sim, self)

    def apply(self):
        super().apply()

        self.dot.ticks_remain = self.duration.total_seconds() / 3
        self.dot.schedule(timedelta(seconds=3))


class StormbiteAura(DotAura):
    def __init__(self, source, target=None):
        super().__init__(source, target)

        self.duration = timedelta(seconds=30)


class Actor:
    class Actions:
        def __init__(self, source):
            self.heavy_shot = HeavyShot(source)
            self.raging_strikes = RagingStrikes(source)
            self.stormbite = Stormbite(source)

    class Buffs:
        def __init__(self, source):
            self.raging_strikes = RagingStrikesAura(source)

    class TargetData:
        def __init__(self, source, target):
            self.stormbite = StormbiteAura(source, target)

    def __init__(self, sim, name, target):
        self.sim = sim
        self.name = name
        self.target = target

        self.actions = Actor.Actions(self)
        self.buffs = Actor.Buffs(self)
        self._target_data = {}

        self.animation_unlock_at = None
        self.gcd_unlock_at = None
        self.readied = ActorReadied(sim, self)

        self.sim.add_actor(self)

    @property
    def target_data(self):
        try:
            return self._target_data[self.target]
        except KeyError:
            self._target_data[self.target] = Actor.TargetData(self, self.target)
            return self._target_data[self.target]

    def decide(self):
        yield self.actions.stormbite, lambda: self.target_data.stormbite.down
        yield self.actions.raging_strikes
        yield self.actions.heavy_shot


if __name__ == '__main__':
    s = Simulation(combat_length=timedelta(minutes=5))
    enemy = Actor(s, name='Boss', target=None)
    bard = Actor(s, name='Dikembe', target=enemy)
    s.run()
