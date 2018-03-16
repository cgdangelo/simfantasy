from abc import ABCMeta, abstractmethod
from datetime import datetime, timedelta
from math import floor
from typing import List

import numpy

from simfantasy.actor import Actor
from simfantasy.aura import Aura, TickingAura
from simfantasy.common_math import divisor_per_level, get_base_stats_by_job, \
    main_stat_per_level, sub_stat_per_level
from simfantasy.enum import Attribute, Job, RefreshBehavior, Resource, Slot
from simfantasy.simulator import Simulation


class Event(metaclass=ABCMeta):
    """Emitted objects corresponding to in-game occurrences."""

    def __init__(self, sim: Simulation):
        """
        Create a new event.

        :param sim: The simulation that the event is fired within.
        """
        self.sim = sim
        self.timestamp: datetime = None
        self.unscheduled = False

    def __lt__(self, other: 'Event') -> bool:
        """
        Comparison for determining if one Event is less than another. Required for sorting the event heap. Returns

        :param other: The other event to compare to.
        :return: True if current event occurs before other.
        """
        return self.timestamp < other.timestamp

    def __str__(self) -> str:
        """String representation of the object."""
        return '<{cls}>'.format(cls=self.__class__.__name__)

    @abstractmethod
    def execute(self) -> None:
        """Handle the event appropriately when popped off the heap queue."""


class CombatStartEvent(Event):
    def __init__(self, sim: Simulation):
        super().__init__(sim)

        self.sim.current_time = self.sim.start_time = datetime.now()

    def execute(self) -> None:
        for actor in self.sim.actors:
            self.sim.logger.debug('[%s] ^^ %s %s arises', self.sim.current_iteration, self.sim.relative_timestamp,
                                  actor)
            actor.arise()


class CombatEndEvent(Event):
    """An event indicating that combat has ceased."""

    def execute(self) -> None:
        """Clear any remaining events in the heap."""
        self.sim.events.clear()


class AuraEvent(Event, metaclass=ABCMeta):
    """
    An event that deals with an "aura", i.e., a buff or debuff that can be applied to an
    :class:`~simfantasy.actor.Actor`.
    """

    def __init__(self, sim: Simulation, target: Actor, aura: Aura):
        """
        Create a new event.

        :param sim: The simulation that the event is fired within.
        :param target: The :class:`~simfantasy.actor.Actor` context in which to evaluate the aura.
        :param aura: The aura that will interact with the target.
        """
        super().__init__(sim)

        self.target = target
        self.aura = aura

    def __str__(self) -> str:
        """String representation of the object."""
        return '<{cls} aura={aura} target={target}>'.format(
            cls=self.__class__.__name__,
            aura=self.aura.name,
            target=self.target.name
        )


class ApplyAuraEvent(AuraEvent):
    """An event indicating that an aura should be added to an :class:`~simfantasy.actor.Actor`."""

    def execute(self) -> None:
        """Add the aura to the target and fire any post-application hooks from the aura itself."""
        self.aura.apply(self.target)

        self.target.statistics['auras'].append({
            'iteration': self.sim.current_iteration,
            'timestamp': self.sim.current_time,
            'target': self.target.name,
            'aura': self.aura.name,
            'application': True,
        })


class ExpireAuraEvent(AuraEvent):
    """An event indicating that an aura should be removed from an :class:`~simfantasy.actor.Actor`."""

    def execute(self) -> None:
        """Remove the aura if still present on the target and fire any post-expiration hooks from the aura itself."""
        self.aura.expire(self.target)
        self.aura.expiration_event = None

        self.target.statistics['auras'].append({
            'iteration': self.sim.current_iteration,
            'timestamp': self.sim.current_time,
            'target': self.target.name,
            'aura': self.aura.name,
            'expiration': True,
        })


class ActorReadyEvent(Event):
    """An event indicating that an :class:`~simfantasy.actor.Actor` is ready to perform new actions."""

    def __init__(self, sim: Simulation, actor: Actor):
        """
        Create a new event.

        :param sim: The simulation that the event is fired within.
        :param actor: The :class:`~simfantasy.actor.Actor` context, i.e, the one recovering from nonready state.
        """
        super().__init__(sim)

        self.actor = actor

    def execute(self) -> None:
        decision_engine = self.actor.decide()

        for decision in decision_engine:
            if decision is not None:
                try:
                    decision_action, decision_options = decision
                except TypeError:
                    decision_action, decision_options = decision, None

                if decision_action.ready and (decision_options is None or decision_options() is True):
                    decision_action.perform()
            else:
                return

        # Got nothing from the actor, so try again in 100ms.
        self.sim.schedule(self, timedelta(seconds=0.1))

    def __str__(self):
        """String representation of the object."""
        return '<{cls} actor={actor}>'.format(
            cls=self.__class__.__name__,
            actor=self.actor.name
        )


class RefreshAuraEvent(AuraEvent):
    def __init__(self, sim: Simulation, target: Actor, aura: Aura):
        super().__init__(sim, target, aura)

        self.remains = self.aura.expiration_event.timestamp - self.sim.current_time

    def execute(self) -> None:
        if self.aura.refresh_behavior is RefreshBehavior.RESET:
            delta = self.aura.duration
        elif self.aura.refresh_behavior is RefreshBehavior.EXTEND_TO_MAX:
            delta = max(self.aura.duration,
                        self.sim.current_time - self.aura.expiration_event + self.aura.refresh_extension)
        else:
            delta = self.aura.duration

        self.aura.expire(self.target)
        self.aura.apply(self.target)

        self.aura.expiration_event = ExpireAuraEvent(self.sim, self.target, self.aura)
        self.sim.schedule(self.aura.expiration_event, delta)

        self.target.statistics['auras'].append({
            'iteration': self.sim.current_iteration,
            'timestamp': self.sim.current_time,
            'target': self.target.name,
            'aura': self.aura.name,
            'refresh': True,
        })

    def __str__(self) -> str:
        return '<{cls} aura={aura} target={target} behavior={behavior} remains={remains}>'.format(
            cls=self.__class__.__name__,
            aura=self.aura.name,
            target=self.target.name,
            behavior=self.aura.refresh_behavior,
            remains=format(self.remains.total_seconds(), '.3f')
        )


class ConsumeAuraEvent(AuraEvent):
    def __init__(self, sim: Simulation, target: Actor, aura: Aura):
        super().__init__(sim, target, aura)

        self.remains = self.aura.expiration_event.timestamp - self.sim.current_time

    def execute(self) -> None:
        self.aura.expire(self.target)
        self.sim.unschedule(self.aura.expiration_event)
        self.aura.expiration_event = None

        self.target.statistics['auras'].append({
            'iteration': self.sim.current_iteration,
            'timestamp': self.sim.current_time,
            'target': self.target.name,
            'aura': self.aura.name,
            'consumption': True,
        })


class DamageEvent(Event):
    def __init__(self, sim: Simulation, source: Actor, target: Actor, action, potency: int,
                 trait_multipliers: List[float] = None, buff_multipliers: List[float] = None,
                 guarantee_crit: bool = None):
        super().__init__(sim)

        if trait_multipliers is None:
            trait_multipliers = []

        if buff_multipliers is None:
            buff_multipliers = []

        self.source = source
        self.target = target
        self.action = action
        self.potency = potency
        self.trait_multipliers = trait_multipliers
        self.buff_multipliers = buff_multipliers

        self._damage = None

        self._is_critical_hit = guarantee_crit
        """
        Deferred attribute. Set once unless cached value is invalidated. True if the ability was determined to be a
        critical hit.
        """

        self._is_direct_hit = None
        """
        Deferred attribute. Set once unless cached value is invalidated. True if the ability was determined to be a
        direct hit.
        """

    def execute(self):
        self.source.statistics['damage'].append({
            'iteration': self.sim.current_iteration,
            'timestamp': self.sim.current_time,
            'source': self.source.name,
            'target': self.target.name,
            'action': self.action.name,
            'damage': self.damage,
            'critical': self.is_critical_hit,
            'direct': self.is_direct_hit
        })

    @property
    def critical_hit_chance(self) -> float:
        """
        Calculate the critical hit probability.

        :return: A float in the range [0, 1].
        """
        sub_stat = sub_stat_per_level[self.source.level]
        divisor = divisor_per_level[self.source.level]
        p_chr = floor(200 * (self.source.stats[Attribute.CRITICAL_HIT] - sub_stat) / divisor + 50) / 1000

        return p_chr

    @property
    def is_critical_hit(self) -> bool:
        """
        Check for a cached value and set if being evaluated for the first time.

        :return: True if the ability is a critical hit.
        """
        if self._is_critical_hit is None:
            if self.critical_hit_chance >= 100:
                self._is_critical_hit = True
            elif self.critical_hit_chance <= 0:
                self._is_critical_hit = False
            else:
                self._is_critical_hit = numpy.random.uniform() <= self.critical_hit_chance

        return self._is_critical_hit

    @property
    def direct_hit_chance(self):
        """
        Calculate the direct hit probability.

        :return: A float in the range [0, 1].
        """
        sub_stat = sub_stat_per_level[self.source.level]
        divisor = divisor_per_level[self.source.level]
        p_dhr = floor(550 * (self.source.stats[Attribute.DIRECT_HIT] - sub_stat) / divisor) / 1000

        return p_dhr

    @property
    def is_direct_hit(self):
        """
        Check for a cached value and set if being evaluated for the first time.

        :return: True if the ability is a direct hit.
        """
        if self._is_direct_hit is None:
            if self.direct_hit_chance >= 100:
                self._is_direct_hit = True
            elif self.direct_hit_chance <= 0:
                self._is_direct_hit = False
            else:
                self._is_direct_hit = numpy.random.uniform() <= self.direct_hit_chance

        return self._is_direct_hit

    @property
    def damage(self) -> int:
        """
        Calculate the damage dealt directly to the target by the ability. Accounts for criticals, directs, and
        randomization.

        :return: The damage inflicted as an integer value.
        """
        if self._damage is not None:
            return self._damage

        base_stats = get_base_stats_by_job(self.source.job)

        if self.action.powered_by is Attribute.ATTACK_POWER:
            if self.source.job is Job.BARD \
                    or self.source.job is Job.MACHINIST \
                    or self.source.job is Job.NINJA:
                job_attribute_modifier = base_stats[Attribute.DEXTERITY]
                attack_rating = self.source.stats[Attribute.DEXTERITY]
            else:
                job_attribute_modifier = base_stats[Attribute.STRENGTH]
                attack_rating = self.source.stats[Attribute.STRENGTH]

            weapon_damage = self.source.gear[Slot.WEAPON].physical_damage
        elif self.action.powered_by is Attribute.ATTACK_MAGIC_POTENCY:
            if self.source.job is Job.ASTROLOGIAN \
                    or self.source.job is Job.SCHOLAR \
                    or self.source.job is Job.WHITE_MAGE:
                job_attribute_modifier = base_stats[Attribute.MIND]
                attack_rating = self.source.stats[Attribute.MIND]
            else:
                job_attribute_modifier = base_stats[Attribute.INTELLIGENCE]
                attack_rating = self.source.stats[Attribute.INTELLIGENCE]

            weapon_damage = self.source.gear[Slot.WEAPON].magic_damage
        elif self.action.powered_by is Attribute.HEALING_MAGIC_POTENCY:
            job_attribute_modifier = base_stats[Attribute.MIND]
            weapon_damage = self.source.gear[Slot.WEAPON].magic_damage
            attack_rating = self.source.stats[Attribute.MIND]
        else:
            raise Exception('Action affected by unexpected attribute.')

        main_stat = main_stat_per_level[self.source.level]
        sub_stat = sub_stat_per_level[self.source.level]
        divisor = divisor_per_level[self.source.level]

        f_ptc = self.potency / 100
        f_wd = floor((main_stat * job_attribute_modifier / 1000) + weapon_damage)
        f_atk = floor((125 * (attack_rating - 292) / 292) + 100) / 100
        f_det = floor(130 * (self.source.stats[Attribute.DETERMINATION] - main_stat) / divisor + 1000) / 1000
        f_tnc = floor(100 * (self.source.stats[Attribute.TENACITY] - sub_stat) / divisor + 1000) / 1000
        f_chr = floor(200 * (self.source.stats[Attribute.CRITICAL_HIT] - sub_stat) / divisor + 1400) / 1000

        damage_randomization = numpy.random.uniform(0.95, 1.05)

        damage = f_ptc * f_wd * f_atk * f_det * f_tnc

        for m in self.trait_multipliers:
            damage *= m

        damage = floor(damage)
        damage = floor(damage * (f_chr if self.is_critical_hit else 1))
        damage = floor(damage * (1.25 if self.is_direct_hit else 1))
        damage = floor(damage * damage_randomization)

        for m in self.buff_multipliers:
            damage = floor(damage * m)

        self._damage = int(damage)

        return self._damage

    def __str__(self) -> str:
        """String representation of the object."""
        return '<{cls} source={source} target={target} action={action} crit={crit} direct={direct} damage={damage} traits={traits} buffs={buffs}>'.format(
            cls=self.__class__.__name__,
            source=self.source.name,
            target=self.target.name,
            action=self.action.name,
            crit=self.is_critical_hit,
            direct=self.is_direct_hit,
            damage=self.damage,
            traits=self.trait_multipliers,
            buffs=self.buff_multipliers,
        )


class DotTickEvent(DamageEvent):
    def __init__(self, sim: Simulation, source: Actor, target: Actor, action, potency: int, aura: TickingAura,
                 ticks_remain: int = None, trait_multipliers: List[float] = None, buff_multipliers: List[float] = None):
        super().__init__(sim, source, target, action, potency, trait_multipliers, buff_multipliers)

        self.aura = aura
        self.action = action

        if ticks_remain is None:
            ticks_remain = self.aura.ticks

        self.ticks_remain = ticks_remain

    def execute(self) -> None:
        self.source.statistics['damage'].append({
            'iteration': self.sim.current_iteration,
            'timestamp': self.sim.current_time,
            'source': self.source.name,
            'target': self.target.name,
            'action': self.action.name,
            'damage': self.damage,
            'critical': self.is_critical_hit,
            'direct': self.is_direct_hit,
            'dot': True,
        })

        self.ticks_remain -= 1

        if self.ticks_remain > 0:
            self.sim.schedule(self, timedelta(seconds=3))

    @property
    def damage(self) -> int:
        if self._damage is not None:
            return self._damage

        base_stats = get_base_stats_by_job(self.source.job)

        if self.action.powered_by is Attribute.ATTACK_POWER:
            if self.source.job is Job.BARD \
                    or self.source.job is Job.MACHINIST \
                    or self.source.job is Job.NINJA:
                job_attribute_modifier = base_stats[Attribute.DEXTERITY]
                attack_rating = self.source.stats[Attribute.DEXTERITY]
            else:
                job_attribute_modifier = base_stats[Attribute.STRENGTH]
                attack_rating = self.source.stats[Attribute.STRENGTH]

            weapon_damage = self.source.gear[Slot.WEAPON].physical_damage
        elif self.action.powered_by is Attribute.ATTACK_MAGIC_POTENCY:
            if self.source.job is Job.ASTROLOGIAN \
                    or self.source.job is Job.SCHOLAR \
                    or self.source.job is Job.WHITE_MAGE:
                job_attribute_modifier = base_stats[Attribute.MIND]
                attack_rating = self.source.stats[Attribute.MIND]
            else:
                job_attribute_modifier = base_stats[Attribute.INTELLIGENCE]
                attack_rating = self.source.stats[Attribute.INTELLIGENCE]

            weapon_damage = self.source.gear[Slot.WEAPON].magic_damage
        elif self.action.powered_by is Attribute.HEALING_MAGIC_POTENCY:
            job_attribute_modifier = base_stats[Attribute.MIND]
            weapon_damage = self.source.gear[Slot.WEAPON].magic_damage
            attack_rating = self.source.stats[Attribute.MIND]
        else:
            raise Exception('Action affected by unexpected attribute.')

        main_stat = main_stat_per_level[self.source.level]
        sub_stat = sub_stat_per_level[self.source.level]
        divisor = divisor_per_level[self.source.level]

        f_ptc = self.potency / 100
        f_wd = floor((main_stat * job_attribute_modifier / 1000) + weapon_damage)
        f_atk = floor((125 * (attack_rating - 292) / 292) + 100) / 100
        f_det = floor(130 * (self.source.stats[Attribute.DETERMINATION] - main_stat) / divisor + 1000) / 1000
        f_tnc = floor(100 * (self.source.stats[Attribute.TENACITY] - sub_stat) / divisor + 1000) / 1000
        f_ss = floor(130 * (self.source.stats[self.action.hastened_by] - sub_stat) / divisor + 1000) / 1000
        f_chr = floor(200 * (self.source.stats[Attribute.CRITICAL_HIT] - sub_stat) / divisor + 1400) / 1000

        damage_randomization = numpy.random.uniform(0.95, 1.05)

        damage = f_ptc * f_wd * f_atk * f_det * f_tnc

        for m in self.trait_multipliers:
            damage *= m

        damage = floor(damage)
        damage = floor(damage * f_ss)
        damage = floor(damage * (f_chr if self.is_critical_hit else 1))
        damage = floor(damage * (1.25 if self.is_direct_hit else 1))
        damage = floor(damage * damage_randomization)

        for m in self.buff_multipliers:
            damage = floor(damage * m)

        self._damage = int(damage)

        return self._damage

    def __str__(self):
        return '<{cls} source={source} target={target} action={action} crit={crit} direct={direct} damage={damage} ticks_remain={ticks_remain}>'.format(
            cls=self.__class__.__name__,
            source=self.source.name,
            target=self.target.name,
            action=self.action.name,
            crit=self.is_critical_hit,
            direct=self.is_direct_hit,
            damage=self.damage,
            ticks_remain=self.ticks_remain,
        )


class ResourceEvent(Event):
    def __init__(self, sim: Simulation, target: Actor, resource: Resource, amount: int):
        super().__init__(sim)

        self.target = target
        self.resource = resource
        self.amount = amount

    def execute(self) -> None:
        current, maximum = self.target.resources[self.resource]

        final_resource = max(min(current + self.amount, maximum), 0)

        self.target.resources[self.resource] = (final_resource, maximum)
        self.target.statistics['resources'].append({
            'iteration': self.sim.current_iteration,
            'timestamp': self.sim.current_time,
            'target': self.target.name,
            'resource': self.resource,
            'amount': self.amount,
            'level': final_resource,
        })

    def __str__(self):
        return '<{cls} target={target} resource={resource} amount={amount}>'.format(
            cls=self.__class__.__name__,
            target=self.target.name,
            resource=self.resource,
            amount=self.amount,
        )


class ServerTickEvent(Event):
    def execute(self) -> None:
        super().execute()

        for actor in self.sim.actors:
            current_mp, max_mp = actor.resources[Resource.MP]
            current_tp, max_tp = actor.resources[Resource.TP]

            if current_mp < max_mp:
                mp_tick = int(floor(0.02 * max_mp))

                self.sim.schedule(ResourceEvent(self.sim, actor, Resource.MP, mp_tick))  # TODO Tick rate?

            if current_tp < max_tp:
                self.sim.schedule(ResourceEvent(self.sim, actor, Resource.TP, 60))  # TODO Tick rate?


class ApplyAuraStackEvent(AuraEvent):
    def execute(self) -> None:
        if self.aura.stacks < self.aura.max_stacks:
            self.aura.stacks += 1


class AutoAttackEvent(DamageEvent):
    @property
    def damage(self) -> int:
        if self._damage is not None:
            return self._damage

        base_stats = get_base_stats_by_job(self.source.job)

        if self.source.job is Job.BARD \
                or self.source.job is Job.MACHINIST \
                or self.source.job is Job.NINJA:
            job_attribute_modifier = base_stats[Attribute.DEXTERITY]
            attack_rating = self.source.stats[Attribute.DEXTERITY]
        else:
            job_attribute_modifier = base_stats[Attribute.STRENGTH]
            attack_rating = self.source.stats[Attribute.STRENGTH]

        weapon_damage = self.source.gear[Slot.WEAPON].physical_damage
        weapon_delay = self.source.gear[Slot.WEAPON].delay

        main_stat = main_stat_per_level[self.source.level]
        sub_stat = sub_stat_per_level[self.source.level]
        divisor = divisor_per_level[self.source.level]

        f_ptc = self.potency / 100
        f_aa = floor(floor((main_stat * job_attribute_modifier / 1000) + weapon_damage) * (weapon_delay / 3))
        f_atk = floor((125 * (attack_rating - 292) / 292) + 100) / 100
        f_det = floor(130 * (self.source.stats[Attribute.DETERMINATION] - main_stat) / divisor + 1000) / 1000
        f_tnc = floor(100 * (self.source.stats[Attribute.TENACITY] - sub_stat) / divisor + 1000) / 1000
        f_chr = floor(200 * (self.source.stats[Attribute.CRITICAL_HIT] - sub_stat) / divisor + 1400) / 1000

        damage_randomization = numpy.random.uniform(0.95, 1.05)

        damage = f_ptc * f_aa * f_atk * f_det * f_tnc

        for m in self.trait_multipliers:
            damage *= m

        damage = floor(damage)
        damage = floor(damage * (f_chr if self.is_critical_hit else 1))
        damage = floor(damage * (1.25 if self.is_direct_hit else 1))
        damage = floor(damage * damage_randomization)

        for m in self.buff_multipliers:
            damage = floor(damage * m)

        self._damage = int(damage)

        return self._damage
