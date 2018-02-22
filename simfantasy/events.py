from abc import ABCMeta, abstractmethod
from datetime import datetime, timedelta
from math import ceil, floor

import numpy

from simfantasy.common_math import divisor_per_level, get_base_stats_by_job, \
    main_stat_per_level, sub_stat_per_level
from simfantasy.enums import Attribute, Job, RefreshBehavior, Slot
from simfantasy.simulator import Actor, Aura, Simulation


class Event(metaclass=ABCMeta):
    """Emitted objects corresponding to in-game occurrences."""

    def __init__(self, sim: Simulation):
        """
        Create a new event.

        :param sim: The simulation that the event is fired within.
        """
        self.sim = sim

        self.timestamp: datetime = None

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
        pass


class CombatEndEvent(Event):
    """An event indicating that combat has ceased."""

    def execute(self) -> None:
        """Clear any remaining events in the heap."""
        self.sim.events.clear()


class AuraEvent(Event, metaclass=ABCMeta):
    """
    An event that deals with an "aura", i.e., a buff or debuff that can be applied to an
    :class:`~simfantasy.simulator.Actor`.
    """

    def __init__(self, sim: Simulation, target: Actor, aura: Aura):
        """
        Create a new event.

        :param sim: The simulation that the event is fired within.
        :param target: The :class:`~simfantasy.simulator.Actor` context in which to evaluate the aura.
        :param aura: The aura that will interact with the target.
        """
        super().__init__(sim=sim)

        self.target = target
        self.aura = aura

        if self.aura.__class__ not in self.target.statistics['auras']:
            self.target.statistics['auras'][self.aura.__class__] = {
                'applications': [],
                'expirations': [],
                'refreshes': [],
                'consumptions': [],
            }

    def __str__(self) -> str:
        """String representation of the object."""
        return '<{cls} aura={aura} target={target}>'.format(cls=self.__class__.__name__,
                                                            aura=self.aura.__class__.__name__,
                                                            target=self.target.name)


class ApplyAuraEvent(AuraEvent):
    """An event indicating that an aura should be added to an :class:`~simfantasy.simulator.Actor`."""

    def execute(self) -> None:
        """Add the aura to the target and fire any post-application hooks from the aura itself."""
        self.target.auras.append(self.aura)
        self.aura.apply(target=self.target)

        self.target.statistics['auras'][self.aura.__class__]['applications'].append(self.timestamp)


class ExpireAuraEvent(AuraEvent):
    """An event indicating that an aura should be removed from an :class:`~simfantasy.simulator.Actor`."""

    def execute(self) -> None:
        """Remove the aura if still present on the target and fire any post-expiration hooks from the aura itself."""
        if self.aura in self.target.auras:
            self.target.auras.remove(self.aura)
            self.aura.expire(target=self.target)

            self.target.statistics['auras'][self.aura.__class__]['expirations'].append(self.timestamp)


class ActorReadyEvent(Event):
    """An event indicating that an :class:`~simfantasy.simulator.Actor` is ready to perform new actions."""

    def __init__(self, sim: Simulation, actor: Actor):
        """
        Create a new event.

        :param sim: The simulation that the event is fired within.
        :param actor: The :class:`~simfantasy.simulator.Actor` context, i.e, the one recovering from nonready state.
        """
        super().__init__(sim=sim)

        self.actor = actor

    def execute(self) -> None:
        pass

    def __str__(self):
        """String representation of the object."""
        return '<{cls} actor={actor}>'.format(cls=self.__class__.__name__,
                                              actor=self.actor.name)


class CastEvent(Event):
    """An event indicating that an :class:`~simfantasy.simulator.Actor` has performed an action on a target."""

    animation = timedelta(seconds=0.75)
    """Length of the ability's animation."""

    affected_by: Attribute = None
    """The attribute that will contribute to the damage dealt formula."""

    hastened_by: Attribute = None
    """The attribute that will contribute to the reduction of recast (GCD) time."""

    is_off_gcd: bool = False
    """True if ability can be cast off of the GCD."""

    potency: int = 0
    """Potency for damage-dealing abilities."""

    recast_time: timedelta = None
    """Length of recast (cooldown) time."""

    can_recast_at: datetime = None
    """Timestamp when the ability will be available for use again."""

    def __init__(self, sim: Simulation, source: Actor, target: Actor = None):
        """
        Create a new event.

        :param sim: The simulation that the event is fired within.
        :param source: The :class:`~simfantasy.simulator.Actor` context that spawned the event.
        :param target: The :class:`~simfantasy.simulator.Actor` context the event focuses on.
        """
        super().__init__(sim=sim)

        self.source = source
        self.target = target

        self.__is_critical_hit = None
        """
        Deferred attribute. Set once unless cached value is invalidated. True if the ability was determined to be a
        critical hit.
        """

        self.__is_direct_hit = None
        """
        Deferred attribute. Set once unless cached value is invalidated. True if the ability was determined to be a
        direct hit.
        """

    def execute(self) -> None:
        """Handle GCD and recast scheduling and store ability statistical data."""
        self.sim.schedule_in(ActorReadyEvent(sim=self.sim, actor=self.source),
                             delta=self.animation if self.is_off_gcd else self.gcd)

        self.source.animation_unlock_at = self.sim.current_time + self.animation
        self.source.gcd_unlock_at = self.sim.current_time + (self.gcd if not self.is_off_gcd else timedelta())

        if self.recast_time is not None:
            self.__class__.can_recast_at = self.sim.current_time + self.recast_time

        if self.__class__ not in self.source.statistics['actions']:
            self.source.statistics['actions'][self.__class__] = {
                'casts': [],
                'execute_time': [],
                'damage': [],
                'critical_hits': [],
                'direct_hits': [],
                'critical_direct_hits': [],
            }

        self.source.statistics['actions'][self.__class__]['casts'].append(self.sim.current_time)
        self.source.statistics['actions'][self.__class__]['execute_time'].append(
            (self.sim.current_time, max(self.animation, self.gcd if not self.is_off_gcd else timedelta()))
        )
        self.source.statistics['actions'][self.__class__]['damage'].append((self.sim.current_time, self.direct_damage))

        if self.is_critical_hit:
            self.source.statistics['actions'][self.__class__]['critical_hits'].append(self.sim.current_time)

        if self.is_direct_hit:
            self.source.statistics['actions'][self.__class__]['direct_hits'].append(self.sim.current_time)

        if self.is_critical_hit and self.is_direct_hit:
            self.source.statistics['actions'][self.__class__]['critical_direct_hits'].append(self.sim.current_time)

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
        if self.__is_critical_hit is None:
            if self.critical_hit_chance >= 100:
                self.__is_critical_hit = True
            elif self.critical_hit_chance <= 0:
                self.__is_critical_hit = False
            else:
                self.__is_critical_hit = numpy.random.uniform() <= self.critical_hit_chance

        return self.__is_critical_hit

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
        if self.__is_direct_hit is None:
            if self.direct_hit_chance >= 100:
                self.__is_direct_hit = True
            elif self.direct_hit_chance <= 0:
                self.__is_direct_hit = False
            else:
                self.__is_direct_hit = numpy.random.uniform() <= self.direct_hit_chance

        return self.__is_direct_hit

    @property
    def direct_damage(self) -> int:
        """
        Calculate the damage dealt directly to the target by the ability. Accounts for criticals, directs, and
        randomization.

        :return: The damage inflicted as an integer value.
        """
        base_stats = get_base_stats_by_job(self.source.job)

        if self.affected_by is Attribute.ATTACK_POWER:
            if self.source.job in [Job.BARD, Job.MACHINIST, Job.NINJA]:
                job_attribute_modifier = base_stats[Attribute.DEXTERITY]
                attack_rating = self.source.stats[Attribute.DEXTERITY]
            else:
                job_attribute_modifier = base_stats[Attribute.STRENGTH]
                attack_rating = self.source.stats[Attribute.STRENGTH]

            weapon_damage = self.source.gear[Slot.WEAPON].physical_damage
        elif self.affected_by is Attribute.ATTACK_MAGIC_POTENCY:
            if self.source.job in [Job.ASTROLOGIAN, Job.SCHOLAR, Job.WHITE_MAGE]:
                job_attribute_modifier = base_stats[Attribute.MIND]
                attack_rating = self.source.stats[Attribute.MIND]
            else:
                job_attribute_modifier = base_stats[Attribute.INTELLIGENCE]
                attack_rating = self.source.stats[Attribute.INTELLIGENCE]

            weapon_damage = self.source.gear[Slot.WEAPON].magic_damage
        elif self.affected_by is Attribute.HEALING_MAGIC_POTENCY:
            job_attribute_modifier = base_stats[Attribute.MIND]
            weapon_damage = self.source.gear[Slot.WEAPON].magic_damage
            attack_rating = self.source.stats[Attribute.MIND]
        else:
            raise Exception('Action affected by unexpected attribute.')

        main_stat = main_stat_per_level[self.source.level]
        sub_stat = sub_stat_per_level[self.source.level]
        divisor = divisor_per_level[self.source.level]

        f_ptc = self.potency / 100
        f_wd = floor((main_stat * job_attribute_modifier / 100) + weapon_damage)
        f_atk = floor((125 * (attack_rating - 292) / 292) + 100) / 100
        f_det = floor(130 * (self.source.stats[Attribute.DETERMINATION] - main_stat) / divisor + 1000) / 1000
        f_tnc = floor(100 * (self.source.stats[Attribute.TENACITY] - sub_stat) / divisor + 1000) / 1000
        f_chr = floor(200 * (self.source.stats[Attribute.CRITICAL_HIT] - sub_stat) / divisor + 1400) / 1000

        damage_randomization = numpy.random.uniform(0.95, 1.05)

        damage = int(floor(
            (f_ptc * f_wd * f_atk * f_det * f_tnc) *
            (f_chr if self.is_critical_hit else 1) *
            (1.25 if self.is_direct_hit else 1) *
            damage_randomization
        ))

        return damage

    @property
    def gcd(self) -> timedelta:
        """
        Calculate the GCD lock time of the ability.

        :return: A timedelta that can be used to schedule an :class:`ActorReadyEvent`.
        """
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
        type_2_mod = 0

        gcd_m = floor((1000 - floor(130 * (speed - sub_stat) / divisor)) * 2.5)

        gcd_c_a = floor(
            floor(floor((100 - arrow_mod) * (100 - type_1_mod) / 100) * (100 - haste_mod) / 100) - fey_wind_mod
        )
        gcd_c_b = (type_2_mod - 100) / -100
        gcd_c = floor(
            floor(floor(ceil(gcd_c_a * gcd_c_b) * gcd_m / 100) * riddle_of_fire_mod / 1000) * astral_umbral_mod / 100
        )

        gcd = gcd_c / 100

        return timedelta(seconds=gcd)

    def schedule_aura_events(self, aura: Aura, target: Actor = None):
        if target is None:
            target = self.target

        if aura.expiration_event is not None and aura.expiration_event in self.sim.events:
            self.sim.schedule_in(RefreshAuraEvent(sim=self.sim, target=target, aura=aura))
            self.sim.events.remove(aura.expiration_event)
        else:
            aura.application_event = ApplyAuraEvent(sim=self.sim, target=target, aura=aura)
            aura.expiration_event = ExpireAuraEvent(sim=self.sim, target=target, aura=aura)

            self.sim.schedule_in(aura.application_event)
            self.sim.schedule_in(aura.expiration_event, delta=aura.duration)

    def __str__(self) -> str:
        """String representation of the object."""
        return '<{cls} source={source} target={target} crit={crit} direct={direct}>'.format(
            cls=self.__class__.__name__,
            source=self.source.name,
            target=self.target.name,
            crit=self.is_critical_hit,
            direct=self.is_direct_hit,
        )


class RefreshAuraEvent(AuraEvent):
    def __init__(self, sim: Simulation, target: Actor, aura: Aura):
        super().__init__(sim, target, aura)

        self.remains = (self.aura.expiration_event.timestamp - self.sim.current_time).total_seconds()

    def execute(self) -> None:
        if self.aura.refresh_behavior is RefreshBehavior.RESET or self.aura.refresh_behavior is None:
            delta = self.aura.duration
        elif self.aura.refresh_behavior is RefreshBehavior.EXTEND_TO_MAX:
            delta = max(self.aura.duration,
                        (self.sim.current_time - self.aura.expiration_event).total_seconds() +
                        self.aura.refresh_extension)

        self.aura.expiration_event = ExpireAuraEvent(sim=self.sim, target=self.target, aura=self.aura)
        self.sim.schedule_in(self.aura.expiration_event, delta=delta)

        self.target.statistics['auras'][self.aura.__class__]['refreshes'].append((self.timestamp, self.remains))

    def __str__(self) -> str:
        return '<{cls} aura={aura} target={target} behavior={behavior} remains={remains}>'.format(
            cls=self.__class__.__name__,
            aura=self.aura.__class__.__name__,
            target=self.target.name,
            behavior=self.aura.refresh_behavior,
            remains=format(self.remains, '.3f')
        )


class ConsumeAuraEvent(AuraEvent):
    def __init__(self, sim: Simulation, target: Actor, aura: Aura):
        super().__init__(sim, target, aura)

        self.remains = (self.aura.expiration_event.timestamp - self.sim.current_time).total_seconds()

    def execute(self) -> None:
        self.sim.events.remove(self.aura.expiration_event)
        self.target.auras.remove(self.aura)

        self.target.statistics['auras'][self.aura.__class__]['consumptions'].append((self.timestamp, self.remains))
