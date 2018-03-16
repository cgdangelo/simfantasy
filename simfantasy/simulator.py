import logging
import re
from datetime import datetime, timedelta
from heapq import heapify, heappop, heappush
from typing import List, Pattern

import humanfriendly
import pandas as pd

from simfantasy.reporting import TerminalReporter


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
        log_action_attempts (Optional[bool]): True to log actions attempted by :class:`~simfantasy.actor.Actor`
            decision engines.

    Attributes:
        actors (List[simfantasy.actor.Actor]): Actors involved in the encounter.
        combat_length (datetime.timedelta): Length of the encounter.
        current_iteration (int): Current iteration index.
        current_time (datetime.datetime): "In game" timestamp.
        events (List[simfantasy.event.Event]): Heapified list of upcoming events.
        execute_time (datetime.timedelta): Length of time to allow jobs to use "execute" actions.
        iterations (int): Number of encounters to simulate. Default: 100.
        log_action_attempts (bool): True to log actions attempted by :class:`~simfantasy.actor.Actor` decision
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
        self.actors = []
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
            event (simfantasy.event.Event): The event to unschedule.

        Returns:
            bool: True if the event was unscheduled without issue. False if an error occurred, specifically a
            desync bug between the game clock and the event loop.

        Examples:
            >>> from simfantasy.event import Event
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
            event (simfantasy.event.Event): The event to schedule.
            delta (Optional[datetime.timedelta]): An optional amount of time to wait before the event should be
                executed. When delta is None, the event will be scheduled for the current timestamp, and executed after
                any preexisting events already scheduled for the current timestamp are finished.

        Examples:
            >>> from simfantasy.event import Event
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
            event.timestamp = self.current_time
        else:
            event.timestamp = self.current_time + delta

        heappush(self.events, event)

        if self.log_pushes is True:
            if self.log_event_filter is None or self.log_event_filter.match(event.__class__.__name__) is not None:
                self.logger.debug('[%s] => %s %s', self.current_iteration,
                                  format(abs(event.timestamp - self.start_time).total_seconds(), '.3f'),
                                  event)

    def run(self) -> None:
        """Run the simulation and process all events."""
        from simfantasy.event import ActorReadyEvent, CombatStartEvent, CombatEndEvent, ServerTickEvent

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
