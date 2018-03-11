from datetime import timedelta
from math import ceil, floor
from typing import List, Tuple

from simfantasy.actor import Actor
from simfantasy.aura import Aura, TickingAura
from simfantasy.common_math import divisor_per_level, sub_stat_per_level
from simfantasy.enum import Attribute, Resource, Slot
from simfantasy.errors import ActionOnCooldownError, ActorAnimationLockedError, ActorGCDLockedError
from simfantasy.event import ActorReadyEvent, ApplyAuraEvent, AutoAttackEvent, DamageEvent, DotTickEvent, \
    ExpireAuraEvent, RefreshAuraEvent, ResourceEvent
from simfantasy.simulator import Simulation


class Action:
    animation = timedelta(seconds=0.75)
    base_cast_time: timedelta = timedelta()
    base_recast_time: timedelta = timedelta(seconds=2.5)
    cost: Tuple[Resource, int] = None
    guarantee_crit: bool = None
    hastened_by: Attribute = None
    is_off_gcd: bool = False
    potency: int = 0
    powered_by: Attribute = None
    shares_recast_with: 'Action' = None

    def __init__(self, sim: Simulation, source: Actor):
        self.sim = sim
        self.source = source
        self.can_recast_at = None

    @property
    def name(self):
        return self.__class__.__name__

    def perform(self):
        if self.on_cooldown:
            raise ActionOnCooldownError(self.sim, self.source, self)

        if self.animation > timedelta() and \
                self.source.animation_unlock_at is not None and \
                self.source.animation_unlock_at > self.sim.current_time:
            raise ActorAnimationLockedError(self.sim, self.source, self)

        if not self.is_off_gcd and \
                self.source.gcd_unlock_at is not None and \
                self.source.gcd_unlock_at > self.sim.current_time:
            raise ActorGCDLockedError(self.sim, self.source, self)

        self.sim.logger.debug('[%s] @@ %s %s uses %s', self.sim.current_iteration, self.sim.relative_timestamp,
                              self.source, self)

        self.source.animation_unlock_at = self.sim.current_time + self.animation
        self.sim.schedule(ActorReadyEvent(self.sim, self.source), self.animation_execute_time)

        if not self.is_off_gcd:
            self.source.gcd_unlock_at = self.sim.current_time + self.gcd
            self.sim.schedule(ActorReadyEvent(self.sim, self.source), max(self.cast_time, self.gcd))

        self.set_recast_at(self.animation_execute_time + self.recast_time)

        self.schedule_resource_consumption()

        self.schedule_damage_event()

    @property
    def animation_execute_time(self):
        return max(self.animation, self.cast_time)

    def schedule_resource_consumption(self):
        if self.cost is not None:
            resource, amount = self.cost
            self.sim.schedule(ResourceEvent(self.sim, self.source, resource, -amount),
                              self.animation_execute_time)

    def schedule_damage_event(self):
        if self.potency > 0:
            self.sim.schedule(
                DamageEvent(self.sim, self.source, self.source.target, self, self.potency, self._trait_multipliers,
                            self._buff_multipliers, self.guarantee_crit), self.animation_execute_time)

    def set_recast_at(self, delta: timedelta):
        recast_at = self.sim.current_time + delta

        self.can_recast_at = recast_at

        if self.shares_recast_with is not None:
            self.shares_recast_with.can_recast_at = recast_at

    def schedule_aura_events(self, target: Actor, aura: Aura):
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
            return self._speed(self.base_cast_time)

        return self.base_cast_time

    @property
    def recast_time(self):
        if self.base_recast_time > timedelta(seconds=2.5):
            return self._speed(self.base_recast_time)

        return self.gcd

    @property
    def gcd(self):
        if self.hastened_by is not None:
            return self._speed(timedelta(seconds=2.5))

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

        gcd_m = floor((1000 - floor(130 * (speed - sub_stat) / divisor)) * action_delay.total_seconds())

        gcd_c_a = floor(
            floor(floor((100 - arrow_mod) * (100 - type_1_mod) / 100) * (100 - haste_mod) / 100) - fey_wind_mod
        )
        gcd_c_b = (type_2_mod - 100) / -100
        gcd_c = floor(
            floor(floor(ceil(gcd_c_a * gcd_c_b) * gcd_m / 100) * riddle_of_fire_mod / 1000) * astral_umbral_mod / 100
        )

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
            AutoAttackEvent(self.sim, self.source, self.source.target, self, self.potency, self._trait_multipliers,
                            self._buff_multipliers, self.guarantee_crit))


class MeleeAttackAction(AutoAttackAction):
    name = 'Attack'
    potency = 110


class ShotAction(AutoAttackAction):
    name = 'Shot'
    potency = 100
