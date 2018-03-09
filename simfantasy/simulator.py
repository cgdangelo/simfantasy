import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from heapq import heapify, heappop, heappush
from math import floor
from typing import ClassVar, Dict, Iterable, List, Pattern, Tuple, Union

import humanfriendly
import pandas as pd

from simfantasy.common_math import get_base_resources_by_job, get_base_stats_by_job, get_racial_attribute_bonuses, \
    main_stat_per_level, piety_per_level, sub_stat_per_level
from simfantasy.enums import Attribute, Job, Race, RefreshBehavior, Resource, Role, Slot
from simfantasy.equipment import Item, Weapon
from simfantasy.reporting import TerminalReporter


class TargetData(ABC):
    pass


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
        current_time (datetime.datetime): "In game" timestamp.
        events (List[simfantasy.events.Event]): Heapified list of upcoming events.
        execute_time (datetime.timedelta): Length of time to allow jobs to use "execute" actions.
        iterations (int): Number of encounters to simulate. Default: 100.
        log_action_attempts (bool): True to log actions attempted by :class:`~simfantasy.simulator.Actor` decision
            engines.
        log_event_filter (Optional[Pattern]): Pattern for filtering logging output to only matching class names.
        log_pops (bool): True to show events being popped off the queue. Default: True.
        log_pushes (bool): True to show events being placed on the queue. Default: True.
        logger (logging.Logger): Logger instance to stdout/stderr.
        start_time (datetime.datetime): Time that combat started.
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

        Returns:
            bool: True if the encounter is in an execute phase, False otherwise.

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
        """
        return self.current_time + self.execute_time >= self.start_time + self.combat_length

    def unschedule(self, event) -> bool:
        """Unschedule an event, ensuring that it is not executed.

        Does not "remove" the event. In actuality, flags the event itself as unscheduled to prevent having to
        resort the events list and subsequently recalculate the heap invariant.

        Arguments:
            event (simfantasy.events.Event): The event to unschedule.

        Returns:
            bool: True if the event was unscheduled without issue. False if an error occurred, specifically a
            desync bug between the game clock and the event loop.

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
            >>> event in sim.events
            True

            Note that, as stated above, the event is not actually removed.

            Unscheduling an event without a timestamp, or an event that has already occurred will fail:

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

        Arguments:
            event (simfantasy.events.Event): The event to schedule.
            delta (Optional[datetime.timedelta]): An optional amount of time to wait before the event should be
                executed. When delta is None, the event will be scheduled for the current timestamp, and executed after
                any preexisting events already scheduled for the current timestamp are finished.

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
        """Return a formatted string containing the number of seconds since the simulation began.

        Returns:
            str: A string, with precision to the thousandths.

        Examples:
            For a simulation that has been running for 5 minutes (300 seconds):

            >>> sim = Simulation()
            >>> sim.start_time = datetime.now()
            >>> sim.current_time = sim.start_time + timedelta(minutes=5)
            >>> sim.relative_timestamp
            '300.000'

            And in another 30 seconds:

            >>> sim.current_time += timedelta(seconds=30)
            >>> sim.relative_timestamp
            '330.000'
        """
        return format((self.current_time - self.start_time).total_seconds(), '.3f')

    def __set_logger(self, log_level: int) -> None:
        """Create and set the logger instance.

        Arguments:
            log_level (int): The minimum priority level a message needs to be shown.
        """
        logger = logging.getLogger()
        logger.setLevel(log_level)

        logstream = logging.StreamHandler()
        logstream.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))

        logger.addHandler(logstream)

        self.logger = logger


class Aura(ABC):
    """A buff or debuff that can be applied to a target.

    Attributes:
        application_event (simfantasy.events.ApplyAuraEvent): Pointer to the scheduled event that will apply the aura
            to the target.
        duration (datetime.timedelta): Initial duration of the aura.
        expiration_event (simfantasy.events.ExpireAuraEvent): Pointer to the scheduled event that will remove the aura
            from the target.
        max_stacks (int): The maximum number of stacks that the aura can accumulate.
        refresh_behavior (simfantasy.enums.RefreshBehavior): Defines how the aura behaves when refreshes, i.e., what
            happens when reapplying an aura that already exists on the target.
        refresh_extension (datetime.timedelta): For :class:`simfantasy.enums.RefreshBehavior.EXTEND_TO_MAX`, this defines
            the amount of time that should be added to the aura's current remaining time.
        stacks (int): The current number of stacks that the aura has accumulated. Should be less than or equal to
            `max_stacks`.
    """

    duration: timedelta = None
    max_stacks: int = 1
    refresh_behavior: RefreshBehavior = None
    refresh_extension: timedelta = None

    def __init__(self) -> None:
        self.application_event = None
        self.expiration_event = None
        self.stacks = 0

    @property
    def name(self) -> str:
        """Return the name of the aura.

        Examples:
            By default, shows the class name.

            >>> class MyCustomAura(Aura): pass
            >>> aura = MyCustomAura()
            >>> aura.name
            'MyCustomAura'

            This property should be overwritten to provide a friendlier name, since it will be used for data
            visualization and reporting:

            >>> class MyCustomAura(Aura):
            ...    @property
            ...    def name(self):
            ...        return 'My Custom'
            >>> aura = MyCustomAura()
            >>> aura.name
            'My Custom'
        """
        return self.__class__.__name__

    def apply(self, target) -> None:
        """Apply the aura to the target.

        Arguments:
            target (simfantasy.simulator.Actor): The target that the aura will be applied to.

        Examples:
            >>> class FakeActor:
            ...     def __init__(self):
            ...         self.auras = []
            >>> actor = FakeActor()
            >>> aura = Aura()
            >>> aura in actor.auras
            False
            >>> aura.apply(actor)
            >>> aura in actor.auras
            True
        """
        if self in target.auras:
            target.sim.logger.critical(
                '[%s] %s Adding duplicate buff %s into %s',
                target.sim.current_iteration,
                target.sim.relative_timestamp, self, target
            )

        self.stacks = 1
        target.auras.append(self)

    def expire(self, target) -> None:
        """Remove the aura from the target.

        Warnings:
            In the event that the aura does not exist on the target, the exception will be trapped, and error output
            will be shown.

        Arguments:
            target (simfantasy.simulator.Actor): The target that the aura will be removed from.
        """
        try:
            self.stacks = 0
            target.auras.remove(self)
        except ValueError:
            target.sim.logger.critical('[%s] %s Failed removing %s from %s', target.sim.current_iteration,
                                       target.sim.relative_timestamp, self, target)

    @property
    def up(self) -> bool:
        """Indicates whether the aura is still on the target or not.

        Quite simply, this is a check to see whether the remaining time on the aura is greater than zero.

        Returns:
            bool: True if the aura is still active, False otherwise.
        """
        return self.remains > timedelta()

    @property
    def remains(self) -> timedelta:
        """Return the length of time the aura will remain active on the target.

        Examples:
            For auras with expiration events in the past, we interpret this to mean that they have already fallen off,
            and return zero:

            >>> aura = Aura()
            >>> aura.remains == timedelta()
            True

            On the other hand, if the expiration date is still forthcoming, we use its timestamp to determine the
            remaining time. Consider an aura that is due to expire in 30 seconds:

            >>> sim = Simulation()
            >>> sim.current_time = datetime.now()
            >>> from simfantasy.events import ExpireAuraEvent
            >>> aura.expiration_event = ExpireAuraEvent(sim, None, aura)
            >>> aura.expiration_event.timestamp = sim.current_time + timedelta(seconds=30)

            Obviously, the remaining time will be 30 seconds:

            >>> aura.remains == timedelta(seconds=30)
            True

            And if we move forward in time 10 seconds, we can expect the remaining time to decrease accordingly:

            >>> sim.current_time += timedelta(seconds=10)
            >>> aura.remains == timedelta(seconds=20)
            True
        """
        if self.expiration_event is None or self.expiration_event.timestamp < self.expiration_event.sim.current_time:
            return timedelta()

        return self.expiration_event.timestamp - self.expiration_event.sim.current_time

    def __str__(self) -> str:
        return '<{cls}>'.format(cls=self.__class__.__name__)


class TickingAura(Aura):
    """An aura that ticks on the target, e.g., a damage-over-time spell.

    Attributes:
        tick_event (simfantasy.events.DotTickEvent): Pointer to the event that will apply the next tick.
    """

    @property
    @abstractmethod
    def potency(self):
        """Defines the potency for the dot.

        Returns:
            int: Amount of potency per tick.
        """
        pass

    def __init__(self) -> None:
        super().__init__()

        self.tick_event = None

    def apply(self, target) -> None:
        super().apply(target)

        self.tick_event.ticks_remain = self.ticks

    @property
    def ticks(self):
        """Return the base number of times that the aura will tick on the target.

        Damage-over-time effects are synchronized to server tick events, so by default we assume that the number of
        ticks is :math:`\\frac{duration}{3}`.

        Returns:
            int: Number of ticks.

        Examples:
            Consider a damage-over-time spell that has a base duration of 30 seconds:

            >>> class MyDot(TickingAura):
            ...     duration = timedelta(seconds=30)
            ...     potency = 100

            Since server ticks occur every 3 seconds, we can expect :math:`\\frac{30}{3} = 10` ticks:

            >>> aura = MyDot()
            >>> aura.duration = timedelta(seconds=30)
            >>> aura.ticks
            10
        """
        return int(floor(self.duration.total_seconds() / 3))


class Actor:
    """A participant in an encounter.

    Warnings:
        Although level is accepted as an argument, many of the formulae only work at level 70. This argument may be
        deprecated in the future, or at least restricted to max levels of each game version, i.e., 50, 60, 70 for
        A Realm Reborn, Heavensward, and Stormblood respectively, where it's more likely that someone spent the time to
        figure out all the math.

    Arguments:
        sim (simfantasy.simulator.Simulation): Pointer to the simulation that the actor is participating in.
        race (simfantasy.enums.Race): Race and clan of the actor.
        level (int): Level of the actor.
        target (simfantasy.simulator.Actor): The enemy that the actor is targeting.
        name (str): Name of the actor.
        gear (Optional[Dict[~simfantasy.enums.Slot, Union[~simfantasy.simulator.Item, ~simfantasy.simulator.Weapon]]]):
            Collection of equipment that the actor is wearing.

    Attributes:
        _target_data_class (Type[simfantasy.simulator.TargetData]): Reference to class type that is used to track target
            data.
        __target_data (Dict[~simfantasy.simulator.Actor, ~simfantasy.simulator.TargetData): Mapping of actors to any
            available target state data.
        animation_unlock_at (datetime.datetime): Timestamp when the actor will be able to execute actions again without
            being inhibited by animation lockout.
        auras (List[simfantasy.simulator.Aura]): Auras, both friendly and hostile, that exist on the actor.
        gcd_unlock_at (datetime.datetime): Timestamp when the actor will be able to execute GCD actions again without
            being inhibited by GCD lockout.
        gear (Dict[~simfantasy.enums.Slot, Union[~simfantasy.simulator.Item, ~simfantasy.simulator.Weapon]]):
            Collection of equipment that the actor is wearing.
        job (simfantasy.enums.Job): The actor's job specialization.
        level (int): Level of the actor.
        name (str): Name of the actor.
        race (simfantasy.enums.Race): Race and clan of the actor.
        resources (Dict[~simfantasy.enums.Resource, Tuple[int, int]]): Mapping of resource type to a tuple containing
            the current amount and maximum capacity.
        sim (simfantasy.simulator.Simulation): Pointer to the simulation that the actor is participating in.
        statistics (Dict[str, List[Dict[Any, Any]]]): Collection of different event occurrences that are used for
            reporting and visualizations.
        stats (Dict[~simfantasy.enums.Attribute, int]): Mapping of attribute type to amount.
        target (simfantasy.simulator.Actor): The enemy that the actor is targeting.
    """

    job: Job = None
    role: Role = None
    _target_data_class: ClassVar[TargetData] = None

    # TODO Get rid of level?
    def __init__(self, sim: Simulation, race: Race, level: int = None, target: 'Actor' = None, name: str = None,
                 gear: Dict[Slot, Union[Item, Weapon]] = None):
        if level is None:
            level = 70

        if gear is None:
            gear = {}

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
        """Prepare the actor for combat."""
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
        """Determine the resource levels for the actor.

        In particular, sets the HP, MP and TP resource levels.
        """
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
    def target_data(self) -> TargetData:
        """Return target state data.

        For new targets, or at least ones that the actor has never switched to before, there will not be any target data
        available. In that scenario, this property initializes a new instance of the target data class and returns it.
        If there is already target state data, it will be returned directly.

        Returns:
            simfantasy.simulator.TargetData: Contains all the target state data from the source actor to the target.
        """
        if self.target not in self.__target_data:
            self.__target_data[self.target] = self._target_data_class(source=self)

        return self.__target_data[self.target]

    @property
    def gcd_up(self) -> bool:
        """Determine if the actor is GCD locked.

        The global cooldown, or GCD, is a 2.5s lockout that prevents other GCD actions from being performed. Actions
        on the GCD are constrained by their "execute time", or :math:`\\max_{GCD, CastTime}`.

        Examples:
            Consider an actor that has just performed some action, and is thus gcd locked for 0.75s:

            >>> sim = Simulation()
            >>> sim.current_time = datetime.now()
            >>> actor = Actor(sim, Race.ENEMY)
            >>> actor.gcd_unlock_at = sim.current_time + timedelta(seconds=0.75)

            During this period, the actor will be unable to perform actions that are also on the GCD:

            >>> actor.gcd_up
            False

            However, once the simulation's game clock advances past the GCD lockout timestamp, the actor can once
            again perform GCD actions:

            >>> sim.current_time = actor.gcd_unlock_at + timedelta(seconds=1)
            >>> actor.gcd_up
            True

        Returns:
            bool: True if the actor is still GCD locked, False otherwise.
        """
        return self.gcd_unlock_at is None or self.gcd_unlock_at <= self.sim.current_time

    @property
    def animation_up(self) -> bool:
        """Determine if the actor is animation locked.

        Many actions have an animation timing of 0.75s. This locks out the actor from performing multiple oGCD actions
        simultaneously. This lockout is tracked and can inhibit actions from being performed accordingly.

        Examples:
            Consider an actor that has just performed some action, and is thus animation locked for 0.75s:

            >>> sim = Simulation()
            >>> sim.current_time = datetime.now()
            >>> actor = Actor(sim, Race.ENEMY)
            >>> actor.animation_unlock_at = sim.current_time + timedelta(seconds=0.75)

            During this period, the actor will be unable to perform actions that also have animation timings:

            >>> actor.animation_up
            False

            However, once the simulation's game clock advances past the animation lockout timestamp, the actor can once
            again perform actions:

            >>> sim.current_time = actor.animation_unlock_at + timedelta(seconds=1)
            >>> actor.animation_up
            True

        Returns:
            bool: True if the actor is still animation locked, False otherwise.
        """
        return self.animation_unlock_at is None or self.animation_unlock_at <= self.sim.current_time

    def equip_gear(self, gear: Dict[Slot, Union[Weapon, Item]]):
        """Equip items in the appropriate slots."""
        for slot, item in gear.items():
            if not slot & item.slot:
                raise Exception('Tried to place equipment in an incorrect slot.')

            self.gear[slot] = item

    def apply_gear_attribute_bonuses(self):
        """Apply stat bonuses gained from items and melds.

        Examples:
            Consider the `Kujakuo Kai`_ bow for Bards:

            >>> kujakuo_kai = Weapon(item_level=370, name='Kujakuo Kai', physical_damage=104, magic_damage=70,
            ...                      auto_attack=105.38, delay=3.04,
            ...                      stats={
            ...                          Attribute.DEXTERITY: 347,
            ...                          Attribute.VITALITY: 380,
            ...                          Attribute.CRITICAL_HIT: 218,
            ...                          Attribute.DIRECT_HIT: 311,
            ...                      })

            Equipping this item will add its stat bonuses to the actor:

            >>> sim = Simulation()
            >>> actor = Actor(sim, Race.ENEMY)
            >>> actor.equip_gear({Slot.WEAPON: kujakuo_kai})
            >>> actor.apply_gear_attribute_bonuses()
            >>> actor.stats[Attribute.DEXTERITY] == 347
            True

            Bonuses from melded materia are also applied:

            >>> savage_aim_vi = Materia(Attribute.CRITICAL_HIT, 40)
            >>> kujakuo_kai.melds = [savage_aim_vi, savage_aim_vi]
            >>> actor.stats = {}
            >>> actor.equip_gear({Slot.WEAPON: kujakuo_kai})
            >>> actor.apply_gear_attribute_bonuses()
            >>> actor.stats[Attribute.CRITICAL_HIT] == 218 + 40 + 40
            True

        .. _Kujakuo Kai:
            https://na.finalfantasyxiv.com/lodestone/playguide/db/item/81019e5dbd4/
        """
        for slot, item in self.gear.items():
            for gear_stat, bonus in item.stats.items():
                if gear_stat not in self.stats:
                    self.stats[gear_stat] = 0

                self.stats[gear_stat] += bonus

            for materia in item.melds:
                if materia.attribute not in self.stats:
                    self.stats[materia.attribute] = 0

                self.stats[materia.attribute] += materia.bonus

    @abstractmethod
    def decide(self) -> Iterable:
        """Given current simulation environment, decide what action should be performed, if any.

        The "decision engine" for each actor is a generator function that yields the desired actions. This method should
        be constructed as a priority list, where more important actions are towards the top, and less important actions
        towards the bottom. A notable exception is for filler spells, i.e. :class:`~simfantasy.events.MeleeAttackAction`
        and :class:`~simfantasy.melee.ShotAction`. Auto-attack actions don't interfere with other skills and happen at
        regular intervals, so they can (and should) be safely placed at top priority.

        See Also:
            Refer to :func:`simfantasy.events.ActorReadyEvent.execute` for clarification on what happens with actions
            yielded from the decision engine.

        Yields:
            Optional[simfantasy.events.Action]: An instance of an action that will attempt to be performed. If None is
            yielded, no further attempts to find a suitable action will be made until the actor is ready again.
        """
        yield

    def has_aura(self, aura: Aura) -> bool:
        """Determine if the aura exists on the actor.

        Warnings:
            Probably deprecated in favor of :func:`simfantasy.simulator.Aura.up`.
        """
        return aura in self.auras

    def calculate_base_stats(self) -> Dict[Attribute, int]:
        """Calculate and set base primary and secondary stats.

        Base stats are determined by a combination of level, job and race/clan affiliation.

        Returns:
            Dict[Attribute, int]: Mapping of attributes to amounts.
        """
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
