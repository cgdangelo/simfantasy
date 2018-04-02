import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from math import floor
from typing import TYPE_CHECKING

from simfantasy.actor import Actor
from simfantasy.enum import RefreshBehavior
from simfantasy.simulator import Simulation

if TYPE_CHECKING:
    from simfantasy.event import ApplyAuraEvent, ExpireAuraEvent, DotTickEvent

logger = logging.getLogger(__name__)


class Aura(ABC):
    """A buff or debuff that can be applied to a target.

    Attributes:
        application_event (simfantasy.event.ApplyAuraEvent): Pointer to the scheduled event that
            will apply the aura to the target.
        duration (datetime.timedelta): Initial duration of the aura.
        expiration_event (simfantasy.event.ExpireAuraEvent): Pointer to the scheduled event that
            will remove the aura from the target.
        max_stacks (int): The maximum number of stacks that the aura can accumulate.
        refresh_behavior (simfantasy.enum.RefreshBehavior): Defines how the aura behaves when
            refreshed, i.e., what happens when reapplying an aura that already exists on the target.
        refresh_extension (datetime.timedelta): For :class:`simfantasy.enums.RefreshBehavior.EXTEND_TO_MAX`,
            this defines the amount of time that should be added to the aura's current remaining
            time.
        stacks (int): The current number of stacks that the aura has accumulated. Should be less
            than or equal to `max_stacks`.
    """

    duration: timedelta = None
    max_stacks: int = 1
    refresh_behavior: RefreshBehavior = None
    refresh_extension: timedelta = None

    def __init__(self, sim: Simulation, source: Actor) -> None:
        self.sim: Simulation = sim
        self.source: Actor = source
        self.application_event: ApplyAuraEvent = None
        self.expiration_event: ExpireAuraEvent = None
        self.stacks: int = 0

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
            target (simfantasy.actor.Actor): The target that the aura will be applied to.

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
            logger.critical(
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
            target (simfantasy.actor.Actor): The target that the aura will be removed from.
        """
        try:
            self.stacks = 0
            target.auras.remove(self)
        except ValueError:
            logger.critical('[%s] %s Failed removing %s from %s', target.sim.current_iteration,
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
            >>> from simfantasy.event import ExpireAuraEvent
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
        if self.application_event is None or self.application_event.timestamp > self.application_event.sim.current_time:
            return timedelta()

        if self.expiration_event is None or self.expiration_event.timestamp < self.expiration_event.sim.current_time:
            return timedelta()

        return self.expiration_event.timestamp - self.expiration_event.sim.current_time

    def __str__(self) -> str:
        return '<{cls}>'.format(cls=self.__class__.__name__)


class TickingAura(Aura):
    """An aura that ticks on the target, e.g., a damage-over-time spell.

    Attributes:
        tick_event (simfantasy.event.DotTickEvent): Pointer to the event that will apply the next tick.
    """

    @property
    @abstractmethod
    def potency(self):
        """Defines the potency for the dot.

        Returns:
            int: Amount of potency per tick.
        """
        pass

    def __init__(self, sim, source) -> None:
        super().__init__(sim, source)

        self.tick_event: DotTickEvent = None

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
