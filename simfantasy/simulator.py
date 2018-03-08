import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from heapq import heapify, heappop, heappush
from math import floor
from typing import ClassVar, Dict, Iterable, List, NamedTuple, Pattern, Tuple, Union

import humanfriendly
import pandas as pd

from simfantasy.common_math import get_base_resources_by_job, get_base_stats_by_job, get_racial_attribute_bonuses, \
    main_stat_per_level, piety_per_level, sub_stat_per_level
from simfantasy.enums import Attribute, Job, Race, RefreshBehavior, Resource, Role, Slot
from simfantasy.reporting import TerminalReporter


class Materia(NamedTuple):
    """Provides a bonus to a specific stat.

    Arguments:
        attribute (simfantasy.enums.Attribute): The attribute that will be modified.
        bonus (int): Amount of the attribute added.
        name (Optional[str]): Name of the materia, for convenience.
    """
    attribute: Attribute
    bonus: int
    name: str = None


class Item(NamedTuple):
    """A piece of equipment that can be worn.

    Arguments:
        slot (simfantasy.enums.Slot): The slot where the item fits.
        stats (Tuple[Tuple[~simfantasy.enums.Attribute, int], ...]): Attributes added
            by the item.
        melds (Optional[Tuple[Materia, ...]]):  :class:`~simfantasy.simulator.Materia`
            affixed to the item.
        name (Optional[str]): Name of the materia, for convenience.
    """
    slot: Slot
    stats: Tuple[Tuple[Attribute, int], ...]
    melds: Tuple[Materia, ...] = None
    name: str = None


class Weapon(NamedTuple):
    """An :class:`~simfantasy.simulator.Item` that only fits in :data:`~simfantasy.enums.Slot.SLOT_WEAPON`.

    Arguments:
        magic_damage (:obj:`int`): Magic damage inflicted by the weapon. May be hidden for non-casters.
        physical_damage (:obj:`int`): Physical damage inflicted by the weapon. May be hidden for casters.
        delay (:obj:`float`): Weapon attack delay.
        auto_attack (:obj:`float`): Auto attack value.
        slot (:class:`~simfantasy.enums.Slot`): The slot where the item fits.
        stats (:obj:`tuple` [:obj:`tuple` [:class:`~simfantasy.enums.Attribute`, :obj:`int`], ...]): Attributes added
            by the item.
        melds (Optional[:obj:`tuple` [:class:`~simfantasy.simulator.Materia`]]):  :class:`~simfantasy.simulator.Materia`
            affixed to the item.
        name (Optional[:obj:`str`]): Name of the materia, for convenience.
    """
    magic_damage: int
    physical_damage: int
    delay: float
    auto_attack: float
    stats: Tuple[Tuple[Attribute, int], ...]
    slot = Slot.WEAPON
    melds: Tuple[Materia, ...] = None
    name: str = None


class Simulation:
    """Business logic for managing the simulated combat encounter and subsequent reporting.

    Arguments:
        combat_length (Optional[datetime.timedelta]): Desired combat length. Default: 5 minutes.
        log_level (Optional[int]): Minimum message level necessary to see logger output. Default: :obj:`logging.INFO`.
        log_event_filter (Optional[str]): Pattern for filtering logging output to only matching class names.
            Default: None.
        execute_time (Optional[datetime.timedelta]): Length of time to allow jobs to use "execute" actions.
            Default: 1 minute.
        log_pushes (Optional[bool]): True to show events being placed on the queue. Default: True.
        log_pops (Optional[bool]): True to show events being popped off the queue. Default: True.
        iterations (Optional[int]): Number of encounters to simulate. Default: 100.
        log_action_attempts (Optional[bool]): True to log actions attempted by :class:`~simfantasy.simulator.Actor`
            decision engines.

    Attributes:
        actors (List[simfantasy.simulator.Actor]): Actors involved in the encounter.
        combat_length (datetime.timedelta): Length of the encounter.
        current_iteration (int): Current iteration index.
        current_time (datetime.timestamp): "In game" timestamp.
        events (List[simfantasy.events.Event]): Heapified list of upcoming events.
        execute_time (datetime.timedelta): Length of time to allow jobs to use "execute" actions.
        iterations (int): Number of encounters to simulate. Default: 100.
        log_action_attempts (bool): True to log actions attempted by :class:`~simfantasy.simulator.Actor` decision
            engines.
        log_event_filter (Optional[Pattern]): Pattern for filtering logging output to only matching class names.
        log_pops (bool): True to show events being popped off the queue. Default: True.
        log_pushes (bool): True to show events being placed on the queue. Default: True.
        logger (logging.Logger): Logger instance to stdout/stderr.
        start_time (datetime.timestamp): Time that combat started.
    """

    def __init__(self, combat_length: timedelta = None, log_level: int = None, log_event_filter: str = None,
                 execute_time: timedelta = None, log_pushes: bool = None, log_pops: bool = None, iterations: int = None,
                 log_action_attempts: bool = None):
        # FIXME Do I even need to set these here? They aren't mutable.
        if combat_length is None:
            combat_length = timedelta(minutes=5)

        if log_level is None:
            log_level = logging.INFO

        if execute_time is None:
            execute_time = timedelta(seconds=60)

        if log_pushes is None:
            log_pushes = True

        if log_pops is None:
            log_pops = True

        if log_action_attempts is None:
            log_action_attempts = False

        self.combat_length: timedelta = combat_length
        self.log_event_filter: Pattern = re.compile(log_event_filter) if log_event_filter else None
        self.execute_time: timedelta = execute_time
        self.log_pushes: bool = log_pushes
        self.log_pops: bool = log_pops
        self.iterations: int = iterations
        self.log_action_attempts: bool = log_action_attempts

        self.current_iteration: int = None
        self.actors: List[Actor] = []
        self.start_time: datetime = None
        self.current_time: datetime = None
        self.events = []

        heapify(self.events)

        self.__set_logger(log_level)

    @property
    def in_execute(self) -> bool:
        """Indicate whether the encounter is currently in an "execute" phase.

        "Execute" phases are usually when an enemy falls below a certain health percentage, allowing actions such as
        :class:`simfantasy.jobs.bard.MiserysEndAction` to be used.

        Examples:
            A fresh simulation that has just started a moment ago:

            >>> sim = Simulation(combat_length=timedelta(seconds=60), execute_time=timedelta(seconds=30))
            >>> sim.start_time = sim.current_time = datetime.now()
            >>> print("Misery's End") if sim.in_execute else print('Heavy Shot')
            Heavy Shot

            And now, if we adjust the start time to force us halfway into the execute phase:

            >>> sim.start_time = sim.current_time - timedelta(seconds=30)
            >>> print("Misery's End") if sim.in_execute else print('Heavy Shot')
            Misery's End

        Returns:
            bool: True if the encounter is in an execute phase, False otherwise.
        """
        return self.current_time + self.execute_time >= self.start_time + self.combat_length

    def unschedule(self, event) -> bool:
        """Unschedule an event, ensuring that it is not executed.

        Does not "remove" the event. In actuality, flags the event itself as unscheduled to prevent having to
        resort the events list and subsequently recalculate the heap invariant.

        Examples:
            >>> from simfantasy.events import Event
            >>> sim = Simulation()
            >>> sim.start_time = sim.current_time = datetime.now()
            >>> class MyEvent(Event):
            ...     def execute(self):
            ...         pass

            Unscheduling an upcoming event:

            >>> event = MyEvent(sim)
            >>> sim.schedule(event)
            >>> sim.unschedule(event)
            True
            >>> event.unscheduled
            True

            However, unscheduling a past event will fail:

            >>> event = MyEvent(sim)
            >>> sim.schedule(event, timedelta(seconds=-30))
            >>> sim.unschedule(event)
            False
            >>> event.unscheduled
            False

            With logging enabled, information about the current timings and the event will be displayed:

            >>> sim.current_iteration = 1000
            >>> sim.current_time = sim.start_time + timedelta(minutes=10)
            >>> sim.logger.warning = lambda s, *args: print(s % args)
            >>> sim.unschedule(event)
            [1000] 600.000 Wanted to unschedule event past event <MyEvent> at 30.000
            False

        Arguments:
            event (simfantasy.events.Event): The event to unschedule.

        Returns:
            bool: True if the event was unscheduled without issue. False if an error occurred, specifically a
            desync bug between the game clock and the event loop.
        """
        if event.timestamp < self.current_time:  # Some event desync clearly happened.
            self.logger.warning('[%s] %s Wanted to unschedule event past event %s at %s',
                                self.current_iteration, self.relative_timestamp, event,
                                format(abs(event.timestamp - self.start_time).total_seconds(), '.3f'))

            return False

        if self.log_event_filter is None or self.log_event_filter.match(event.__class__.__name__) is not None:
            self.logger.debug('[%s] XX %s %s', self.current_iteration,
                              format(abs(event.timestamp - self.start_time).total_seconds(), '.3f'), event)

        event.unscheduled = True

        return True

    def schedule(self, event, delta: timedelta = None) -> None:
        """Schedule an event to occur in the future.

        Examples:
            >>> from simfantasy.events import Event
            >>> sim = Simulation()
            >>> sim.start_time = sim.current_time = datetime.now()
            >>> class MyEvent(Event):
            ...     def execute(self):
            ...         pass
            >>> event = MyEvent(sim)
            >>> event in sim.events
            False
            >>> sim.schedule(event)
            >>> event in sim.events
            True


        Arguments:
            event (simfantasy.events.Event): The event to schedule.
            delta (Optional[datetime.timedelta]): An optional amount of time to wait before the event should be
                executed. When delta is None, the event will be scheduled for the current timestamp, and executed after
                any preexisting events already scheduled for the current timestamp are finished.
        """
        if delta is None:
            delta = timedelta()

        event.timestamp = self.current_time + delta

        heappush(self.events, event)

        if self.log_pushes is True:
            if self.log_event_filter is None or self.log_event_filter.match(event.__class__.__name__) is not None:
                self.logger.debug('[%s] => %s %s', self.current_iteration,
                                  format(abs(event.timestamp - self.start_time).total_seconds(), '.3f'),
                                  event)

    def run(self) -> None:
        """Run the simulation and process all events."""
        from simfantasy.events import ActorReadyEvent, CombatStartEvent, CombatEndEvent, ServerTickEvent

        auras_df = pd.DataFrame()
        damage_df = pd.DataFrame()
        resources_df = pd.DataFrame()

        try:
            # Create a friendly progress indicator for the user.
            with humanfriendly.Spinner(label='Simulating', total=self.iterations) as spinner:
                # Store iteration runtimes so we can predict overall runtime.
                iteration_runtimes = []

                for iteration in range(self.iterations):
                    pd_runtimes = pd.Series(iteration_runtimes)

                    iteration_start = datetime.now()
                    self.current_iteration = iteration

                    # Schedule the bookend events.
                    self.schedule(CombatStartEvent(sim=self))
                    self.schedule(CombatEndEvent(sim=self), self.combat_length)

                    # Schedule the server ticks.
                    for delta in range(3, int(self.combat_length.total_seconds()), 3):
                        self.schedule(ServerTickEvent(sim=self), delta=timedelta(seconds=delta))

                    # TODO Maybe move this to Actor#arise?
                    # Tell the actors to get ready.
                    for actor in self.actors:
                        self.schedule(ActorReadyEvent(sim=self, actor=actor))

                    # Start the event loop.
                    while len(self.events) > 0:
                        event = heappop(self.events)

                        # Ignore events that are flagged as unscheduled.
                        if event.unscheduled is True:
                            continue

                        # Some event desync clearly happened.
                        if event.timestamp < self.current_time:
                            self.logger.critical(
                                '[%s] %s %s timestamp %s before current timestamp',
                                self.current_iteration,
                                self.relative_timestamp,
                                event,
                                (event.timestamp - self.start_time).total_seconds()
                            )

                        # Update the simulation's current time to the latest event.
                        self.current_time = event.timestamp

                        if self.log_pops is True:
                            if self.log_event_filter is None or self.log_event_filter.match(
                                    event.__class__.__name__) is not None:
                                self.logger.debug('[%s] <= %s %s',
                                                  self.current_iteration,
                                                  format(abs(event.timestamp - self.start_time).total_seconds(), '.3f'),
                                                  event)

                        # Handle the event.
                        event.execute()

                    # Build statistical dataframes for the completed iteration.
                    for actor in self.actors:
                        auras_df = auras_df.append(pd.DataFrame.from_records(actor.statistics['auras']))
                        damage_df = damage_df.append(pd.DataFrame.from_records(actor.statistics['damage']))
                        resources_df = resources_df.append(pd.DataFrame.from_records(actor.statistics['resources']))

                    # Add the iteration runtime to the collection.
                    iteration_runtimes.append(datetime.now() - iteration_start)

                    # Update our fancy progress indicator with the runtime estimation.
                    spinner.label = 'Simulating ({0})'.format(
                        (pd_runtimes.mean() * (self.iterations - self.current_iteration)))
                    spinner.step(iteration)

            self.logger.info('Finished %s iterations in %s (mean %s).\n', self.iterations, pd_runtimes.sum(),
                             pd_runtimes.mean())
        except KeyboardInterrupt:  # Handle SIGINT.
            self.logger.critical('Interrupted at %s / %s iterations after %s.\n', self.current_iteration,
                                 self.iterations, pd_runtimes.sum())

        # TODO Everything.
        auras_df.set_index('iteration', inplace=True)
        damage_df.set_index('iteration', inplace=True)
        resources_df.set_index('iteration', inplace=True)

        TerminalReporter(self, auras=auras_df, damage=damage_df, resources=resources_df).report()
        # HTMLReporter(self, df).report()

        self.logger.info('Quitting!')

    @property
    def relative_timestamp(self) -> str:
        """Return a formatted string containing the number of seconds since the simulation began."""
        return format((self.current_time - self.start_time).total_seconds(), '.3f')

    def __set_logger(self, log_level: int) -> None:
        """
        Create and set the logger instance.

        :param log_level: The minimum priority level a message needs to be shown.
        """
        logger = logging.getLogger()
        logger.setLevel(log_level)

        logstream = logging.StreamHandler()
        logstream.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))

        logger.addHandler(logstream)

        self.logger = logger


class Aura(ABC):
    """A buff or debuff that can be applied to a target."""

    #: Initial duration of the effect.
    duration: timedelta = None

    refresh_behavior: RefreshBehavior = None
    """Specify how the aura should be refreshed if it already exists on the target."""

    refresh_extension: timedelta = None
    """For :class:`simfantasy.enums.RefreshBehavior`, specify how much time should be added to the current duration."""

    max_stacks: int = 1

    def __init__(self) -> None:
        self.application_event = None
        self.expiration_event = None
        self.stacks = 0

    @property
    def name(self):
        return self.__class__.__name__

    def apply(self, target):
        if self in target.auras:
            target.sim.logger.critical(
                '[%s] %s Adding duplicate buff %s into %s',
                target.sim.current_iteration,
                target.sim.relative_timestamp, self, target
            )

        self.stacks = 1
        target.auras.append(self)

    def expire(self, target):
        try:
            self.stacks = 0
            target.auras.remove(self)
        except ValueError:
            target.sim.logger.critical('[%s] %s Failed removing %s from %s', target.sim.current_iteration,
                                       target.sim.relative_timestamp, self, target)

    @property
    def up(self):
        return self.remains > timedelta()

    @property
    def remains(self):
        if self.expiration_event is None or self.expiration_event.timestamp < self.expiration_event.sim.current_time:
            return timedelta()

        return self.expiration_event.timestamp - self.expiration_event.sim.current_time

    def __str__(self):
        return '<{cls}>'.format(cls=self.__class__.__name__)


class TickingAura(Aura):
    @property
    @abstractmethod
    def potency(self):
        pass

    def __init__(self) -> None:
        super().__init__()

        self.tick_event = None

    def apply(self, target):
        super().apply(target)

        self.tick_event.ticks_remain = self.ticks

    @property
    def ticks(self):
        return int(floor(self.duration.total_seconds() / 3)) - 1


class Actor:
    """A participant in an encounter."""

    job: Job = None
    role: Role = None
    _target_data_class: ClassVar = None

    # TODO Get rid of level?
    def __init__(self,
                 sim: Simulation,
                 race: Race,
                 level: int = None,
                 target: 'Actor' = None,
                 name: str = None,
                 gear: Tuple[Tuple[Slot, Union[Item, Weapon]], ...] = None):
        """
        Create a new actor.

        :param sim: The encounter that the actor will enter.
        :param race: Race and clan.
        :param level: Level. Note that most calculations only work at 70.
        :param target: Primary target.
        """
        if level is None:
            level = 70

        if gear is None:
            gear = ()

        if name is None:
            name = humanfriendly.text.random_string(length=10)

        self.sim: Simulation = sim
        self.race: Race = race
        self.level: int = level
        self.target: 'Actor' = target
        self.name = name

        self.__target_data = {}

        self.animation_unlock_at: datetime = None
        self.gcd_unlock_at: datetime = None
        self.auras: List[Aura] = []

        self.stats: Dict[Attribute, int] = {}
        self.gear: Dict[Slot, Union[Item, Weapon]] = {}
        self.resources: Dict[Resource, Tuple[int, int]] = {}

        self.equip_gear(gear)

        self.statistics = {}

        self.sim.actors.append(self)

        self.sim.logger.debug('Initialized: %s', self)

    def arise(self):
        self.__target_data = {}
        self.animation_unlock_at = None
        self.gcd_unlock_at = None
        self.auras.clear()

        self.stats = self.calculate_base_stats()
        self.apply_gear_attribute_bonuses()
        self.resources = self.calculate_resources()

        self.statistics = {
            'auras': [],
            'damage': [],
            'resources': [],
        }

    def calculate_resources(self):
        main_stat = main_stat_per_level[self.level]
        job_resources = get_base_resources_by_job(self.job)

        # FIXME It's broken.
        # @formatter:off
        hp = floor(3600 * (job_resources[Resource.HP] / 100)) + floor(
            (self.stats[Attribute.VITALITY] - main_stat) * 21.5)
        mp = floor((job_resources[Resource.MP] / 100) * ((6000 * (self.stats[Attribute.PIETY] - 292) / 2170) + 12000))
        # @formatter:on

        return {
            Resource.HP: (hp, hp),
            Resource.MP: (mp, mp),
            Resource.TP: (1000, 1000),  # TODO Math for this?
        }

    @property
    def target_data(self):
        if self.target not in self.__target_data:
            self.__target_data[self.target] = self._target_data_class(source=self)

        return self.__target_data[self.target]

    @property
    def gcd_up(self):
        return self.gcd_unlock_at is None or self.gcd_unlock_at <= self.sim.current_time

    @property
    def animation_up(self):
        return self.animation_unlock_at is None or self.animation_unlock_at <= self.sim.current_time

    def equip_gear(self, gear: Tuple[Tuple[Slot, Union[Weapon, Item]], ...]):
        for slot, item in gear:
            if not slot & item.slot:
                raise Exception('Tried to place equipment in an incorrect slot.')

            self.gear[slot] = item

    def apply_gear_attribute_bonuses(self):
        for slot, item in self.gear.items():
            for gear_stat, bonus in item.stats:
                if gear_stat not in self.stats:
                    self.stats[gear_stat] = 0

                self.stats[gear_stat] += bonus

            for materia in item.melds:
                if materia.attribute not in self.stats:
                    self.stats[materia.attribute] = 0

                self.stats[materia.attribute] += materia.bonus

    @abstractmethod
    def decide(self) -> Iterable:
        """Given current simulation environment, decide what action should be performed, if any."""
        yield

    def has_aura(self, aura: Aura) -> bool:
        """
        Determine if the aura exists on the actor.

        :param aura: The aura to check for.
        :return: True if the aura is presence.
        """
        return aura in self.auras

    def calculate_base_stats(self) -> Dict[Attribute, int]:
        """Calculate and set base primary and secondary stats."""
        base_main_stat = main_stat_per_level[self.level]
        base_sub_stat = sub_stat_per_level[self.level]

        base_stats = {
            Attribute.STRENGTH: 0,
            Attribute.DEXTERITY: 0,
            Attribute.VITALITY: 0,
            Attribute.INTELLIGENCE: 0,
            Attribute.MIND: 0,
            Attribute.CRITICAL_HIT: base_sub_stat,
            Attribute.DETERMINATION: base_main_stat,
            Attribute.DIRECT_HIT: base_sub_stat,
            Attribute.SKILL_SPEED: base_sub_stat,
            Attribute.TENACITY: base_sub_stat,
            Attribute.PIETY: base_main_stat,
        }

        job_stats = get_base_stats_by_job(self.job)
        race_stats = get_racial_attribute_bonuses(self.race)

        for stat, bonus in job_stats.items():
            base_stats[stat] += floor(base_main_stat * (bonus / 100)) + race_stats[stat]

        if self.role is Role.HEALER:
            base_stats[Attribute.PIETY] += piety_per_level[self.level]

        return base_stats

    def __str__(self):
        return '<{cls} name={name}>'.format(cls=self.__class__.__name__, name=self.name)
