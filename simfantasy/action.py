# -*- coding: utf-8 -*-
"""Abilities and weaponskills that can be performed by an actor."""

import logging
from datetime import datetime, timedelta
from functools import lru_cache
from math import ceil, floor
from typing import List, Tuple, Union

from simfantasy.actor import Actor
from simfantasy.aura import Aura, TickingAura
from simfantasy.common_math import divisor_per_level, sub_stat_per_level
from simfantasy.enum import Attribute, Resource, Slot
from simfantasy.event import ActorReadyEvent, ApplyAuraEvent, AutoAttackEvent, DamageEvent, \
    DotTickEvent, ExpireAuraEvent, RefreshAuraEvent, ResourceEvent
from simfantasy.simulator import Simulation

LOGGER = logging.getLogger(__name__)


class Action:
    """An ability that can be performed by an actor.

    Arguments:
        sim (simfantasy.simulator.Simulation): The simulation where the action is performed.
        source (simfantasy.actor.Actor): The actor that performed the action.

    Attributes:
        animation (datetime.timedelta): Length of the animation delay caused by the action.
            Default: 0.75 seconds.
        base_cast_time (datetime.timedelta): Length of the action's cast time.
            Default: Instant cast.
        base_recast_time (datetime.timedelta): Length of time until the ability can be used again.
            Default: base GCD length, 2.5 seconds.
        can_recast_at (datetime.datetime): Timestamp when the action can be performed again.
        cost (Tuple[simfantasy.enum.Resource, int]): The resource type and amount needed to perform
            the action.
        guarantee_crit (bool): Ensures the damage will be a critical hit. Default: False.
        hastened_by (simfantasy.enum.Attribute): The attribute that contributes to lowering the
            cast/recast time of the action. Default: None.
        is_off_gcd (bool): True for actions that are not bound to the GCD, False otherwise.
            Default: False.
        potency (int): Potency of the action's impact, i.e., damage healed or inflicted.
            Default: None.
        powered_by (Attribute): The attribute that contributes to the total impact of the action.
            Default: None.
        shares_recast_with: (Union[simfantasy.action.Action, List[~simfantasy.action.Action]]):
            Action(s) that are on the same recast timer. Default: None.
        sim (simfantasy.simulator.Simulation): The simulation where the action is performed.
        source (simfantasy.actor.Actor): The actor that performed the action.
    """
    animation: timedelta = timedelta(seconds=0.75)
    base_cast_time: timedelta = timedelta()
    base_recast_time: timedelta = timedelta(seconds=2.5)
    cost: Tuple[Resource, int] = None
    guarantee_crit: bool = None
    hastened_by: Attribute = None
    is_off_gcd: bool = False
    potency: int = None
    powered_by: Attribute = None
    shares_recast_with: Union['Action', List['Action']] = None

    def __init__(self, sim: Simulation, source: Actor) -> None:
        self.sim: Simulation = sim
        self.source: Actor = source
        self.can_recast_at: datetime = None
        self.speed = lru_cache(maxsize=None)(self._speed)

    @property
    def ready(self):
        """Flag that indicates if the action can be performed or not.

        Returns:
            bool: True if the action can be performed, False otherwise.
        """
        return not self.on_cooldown \
               and (self.source.animation_up or self.animation == timedelta()) \
               and (self.is_off_gcd or self.source.gcd_up)

    @property
    def name(self):
        """Name of the action.

        Should be overridden with a friendlier name. Returns the class name by default.

        Returns:
            string: Name of the action.

        Examples:
            >>> class MyAction(Action): pass
            >>> MyAction(None, None).name
            'MyAction'
            >>> class MyNamedAction(Action):
            ...     @property
            ...     def name(self):
            ...         return 'CustomName'
            >>> MyNamedAction(None, None).name
            'CustomName'
        """
        return self.__class__.__name__

    def perform(self):
        """Perform the action.

        Automatically schedules common action side effects when appropriate.

        Examples:
            .. testsetup::
                >>> from datetime import datetime
                >>> sim = Simulation(); sim.start_time = sim.current_time = datetime.now()
                >>> actor = Actor(sim, None)
                >>> class Bloodletter(Action): pass
                >>> class RainOfDeath(Action): pass
                >>> bloodletter = Bloodletter(sim, actor)
                >>> rain_of_death = RainOfDeath(sim, actor)

            Actions that share a recast timer will have their recast times set:

            >>> bloodletter.shares_recast_with = rain_of_death
            >>> rain_of_death.can_recast_at is None
            True
            >>> bloodletter.perform()
            >>> bloodletter.can_recast_at is not None
            True
            >>> bloodletter.can_recast_at == rain_of_death.can_recast_at
            True
        """
        LOGGER.debug('[%s] @@ %s %s uses %s',
                     self.sim.current_iteration,
                     self.sim.relative_timestamp,
                     self.source,
                     self)

        self.set_recast_at(self.animation_execute_time + self.recast_time)
        self.schedule_resource_consumption()
        self.schedule_damage_event()

        self.source.animation_unlock_at = self.sim.current_time + self.animation
        self.sim.schedule(ActorReadyEvent(self.sim, self.source), self.animation_execute_time)

        if not self.is_off_gcd:
            self.source.gcd_unlock_at = self.sim.current_time + self.gcd

    @property
    def animation_execute_time(self):
        """Helper function to return whatever is longer, the action's animation or cast time.

        Returns:
            datetime.timedelta
        """
        return max(self.animation, self.cast_time)

    def schedule_resource_consumption(self):
        """Schedules an event to consume the resource needed to perform the action.

        Notes:
            The cost must not be None.

        When the action is performed, i.e., after its
        :attr:`~simfantasy.action.Action.animation_execute_time` has passed, a
        :class:`simfantasy.event.ResourceEvent` will occur that consumes the resource cost defined
        in the :attr:`~simfantasy.action.Action.cost`.
        """
        if self.cost is not None:
            resource, amount = self.cost
            self.sim.schedule(ResourceEvent(self.sim, self.source, resource, -amount),
                              self.animation_execute_time)

    def schedule_damage_event(self):
        """Schedules an event to inflict damage.

        Notes:
            The potency must not be None.

        When the action is performed, i.e., after its
        :attr:`~simfantasy.action.Action.animation_execute_time` has passed, a
        :class:`simfantasy.event.DamageEvent` will inflict damage based on the amount defined in the
        :attr:`~simfantasy.action.Action.potency`.
        """
        if self.potency is not None:
            self.sim.schedule(
                DamageEvent(self.sim, self.source, self.source.target, self, self.potency,
                            self._trait_multipliers, self._buff_multipliers, self.guarantee_crit),
                self.animation_execute_time)

    def set_recast_at(self, delta: timedelta):
        """Sets the timestamp when the action can be performed again.

        Based on the given delta, sets the recast timestamp by adding it to the simulation's
        current timestamp. If the action shares a recast with one or more other actions, those will
        have their recast timestamps set as well.

        Arguments:
            delta (datetime.timedelta): The amount of time that must pass to perform this action
                again.

        Examples:
            .. testsetup::
                >>> class MyAction(Action): pass
                >>> sim = Simulation()
                >>> actor = Actor(sim)
                >>> action = MyAction(sim, actor)

            >>> action.set_recast_at(timedelta(seconds=30))
            >>> action.can_recast_at == sim.current_time + timedelta(seconds=30)
            True
        """
        recast_at = self.sim.current_time + delta

        self.can_recast_at = recast_at

        if self.shares_recast_with is not None:
            if isinstance(self.shares_recast_with, list):
                for shared_action in self.shares_recast_with:
                    shared_action.can_recast_at = recast_at
            else:
                self.shares_recast_with.can_recast_at = recast_at

    def schedule_aura_events(self, target: Actor, aura: Aura):
        """Schedule events to apply and remove an aura from a target.

        For a new aura, :class:`simfantasy.event.ApplyAuraEvent` and
        :class:`simfantasy.event.ExpireAuraEvent` will be scheduled. If the aura already exists on
        the target, a :class:`simfantasy.event.RefreshAuraEvent` will be scheduled instead, which
        will subsequently adjust the timestamps of the existing events.

        Arguments:
            target (simfantasy.actor.Actor): The actor that will receive the aura.
            aura (simfantasy.aura.Aura): The aura to apply to the actor.

        Examples:
            .. testsetup::
                >>> class MyAction(Action): pass
                >>> sim = Simulation()
                >>> actor = Actor(sim)
                >>> action = MyAction(sim, actor)
                >>> class MyAura(Aura): duration = timedelta(seconds=10)
                >>> aura = MyAura(sim, actor)

            A new aura will have its events scheduled for the first time:

            >>> aura.application_event is None
            True
            >>> aura.expiration_event is None
            True
            >>> action.schedule_aura_events(actor, aura)
            >>> aura.application_event # doctest: +ELLIPSIS
            <simfantasy.event.ApplyAuraEvent ...>
            >>> aura.expiration_event # doctest: +ELLIPSIS
            <simfantasy.event.ExpireAuraEvent ...>

            An existing aura will not receive new events, but instead will have its expiry event
            adjusted and rescheduled accordingly:

            >>> original_expiry = aura.expiration_event
            >>> action.schedule_aura_events(actor, aura)
            >>> original_expiry is aura.expiration_event
        """
        delta = self.animation_execute_time

        if aura.expiration_event is not None:
            self.sim.schedule(RefreshAuraEvent(self.sim, target, aura), delta)
            self.sim.unschedule(aura.expiration_event)
        else:
            aura.application_event = ApplyAuraEvent(self.sim, target, aura)
            aura.expiration_event = ExpireAuraEvent(self.sim, target, aura)

            self.sim.schedule(aura.application_event, delta)
            self.sim.schedule(aura.expiration_event, delta + aura.duration)

    def schedule_dot(self, dot: TickingAura):
        self.schedule_aura_events(self.source.target, dot)

        if dot.tick_event is not None and dot.tick_event.timestamp > self.sim.current_time:
            self.sim.unschedule(dot.tick_event)

        tick_event = DotTickEvent(self.sim, self.source, self.source.target, self, dot.potency, dot)

        dot.tick_event = tick_event

        self.sim.schedule(tick_event, self.animation_execute_time + timedelta(seconds=3))

    @property
    def on_cooldown(self):
        return self.can_recast_at is not None and self.can_recast_at > self.sim.current_time

    @property
    def cooldown_remains(self):
        return timedelta() if not self.on_cooldown else self.can_recast_at - self.sim.current_time

    @property
    def cast_time(self):
        if self.hastened_by is not None:
            return self.speed(self.base_cast_time)

        return self.base_cast_time

    @property
    def recast_time(self):
        if self.base_recast_time == timedelta(seconds=2.5):
            return self.gcd

        return self.base_recast_time

    @property
    def gcd(self):
        if self.hastened_by is not None:
            return self.speed(timedelta(seconds=2.5))

        return timedelta(seconds=2.5)

    @property
    def type_ii_speed_mod(self):
        return 0

    def _speed(self, action_delay: timedelta) -> timedelta:
        speed = self.source.stats[self.hastened_by]

        sub_stat = sub_stat_per_level[self.source.level]
        divisor = divisor_per_level[self.source.level]

        # TODO Implement all these buffs.

        rapid_fire = False

        if rapid_fire:
            return timedelta(seconds=1.5)

        arrow_mod = 0
        haste_mod = 0
        fey_wind_mod = 0

        riddle_of_fire = False
        riddle_of_fire_mod = 115 if riddle_of_fire else 100

        astral_umbral = False
        astral_umbral_mod = 50 if astral_umbral else 100

        type_1_mod = 0
        type_2_mod = self.type_ii_speed_mod

        gcd_m = 1000 - floor(130 * (speed - sub_stat) / divisor)
        gcd_m = floor(gcd_m * action_delay.total_seconds())

        gcd_c_a = floor(100 - arrow_mod) * ((100 - type_1_mod) / 100)
        gcd_c_a = floor(gcd_c_a * ((100 - haste_mod) / 100))
        gcd_c_a = floor(gcd_c_a - fey_wind_mod)
        gcd_c_b = (100 - type_2_mod) / 100

        gcd_c = ceil(gcd_c_a * gcd_c_b)
        gcd_c = floor(gcd_c * gcd_m / 100)
        gcd_c = floor(gcd_c * riddle_of_fire_mod / 1000)
        gcd_c = floor(gcd_c * astral_umbral_mod / 100)

        gcd = gcd_c / 100

        return timedelta(seconds=gcd)

    @property
    def _buff_multipliers(self) -> List[float]:
        return [1.0]

    @property
    def _trait_multipliers(self) -> List[float]:
        return [1.0]

    def __str__(self):
        return '<{cls}>'.format(cls=self.__class__.__name__)


class AutoAttackAction(Action):
    animation = timedelta()
    is_off_gcd = True
    hastened_by = Attribute.SKILL_SPEED

    # TODO Would like to avoid having to duplicate so much code here.
    def perform(self):
        animation_unlock = self.source.animation_unlock_at

        super().perform()

        self.sim.schedule(ActorReadyEvent(self.sim, self.source), self.recast_time)

        self.source.animation_unlock_at = animation_unlock

    @property
    def base_recast_time(self):
        return timedelta(seconds=self.source.gear[Slot.WEAPON].delay)

    def create_damage_event(self):
        self.sim.schedule(
            AutoAttackEvent(self.sim, self.source, self.source.target, self, self.potency,
                            self._trait_multipliers, self._buff_multipliers, self.guarantee_crit))


class MeleeAttackAction(AutoAttackAction):
    name = 'Attack'
    potency = 110


class ShotAction(AutoAttackAction):
    name = 'Shot'
    potency = 100
