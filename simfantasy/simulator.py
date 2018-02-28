import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from heapq import heapify, heappop, heappush
from math import floor
from typing import ClassVar, Dict, List, Tuple, Union

import humanfriendly
from humanfriendly.tables import format_pretty_table, format_robust_table

from simfantasy.common_math import get_base_resources_by_job, get_base_stats_by_job, get_racial_attribute_bonuses, \
    main_stat_per_level, piety_per_level, sub_stat_per_level
from simfantasy.enums import Attribute, Job, Race, RefreshBehavior, Resource, Role, Slot


class Simulation:
    """A simulated combat encounter."""

    def __init__(self, combat_length: timedelta = None, log_level: int = None, vertical_output: bool = None,
                 log_event_filter: str = None, execute_time: timedelta = None):
        """
        Create a new simulation.

        :param combat_length: Desired combat length. Default: 5 minutes.
        """
        if combat_length is None:
            combat_length = timedelta(minutes=5)

        if log_level is None:
            log_level = logging.INFO

        if vertical_output is None:
            vertical_output = False

        if execute_time is None:
            execute_time = timedelta(seconds=60)

        self.combat_length: timedelta = combat_length
        """Total length of encounter. Not in real time."""

        self.vertical_output: bool = vertical_output

        self.log_event_filter = re.compile(log_event_filter) if log_event_filter else None

        self.execute_time = execute_time

        self.actors: List[Actor] = []
        """List of actors involved in this encounter, i.e., players and enemies."""

        self.start_time: datetime = None

        self.current_time: datetime = None
        """Current game timestamp."""

        self.events = []
        """Scheduled events."""

        heapify(self.events)

        self.__set_logger(log_level)

    @property
    def in_execute(self):
        return self.current_time + self.execute_time >= self.start_time + self.combat_length

    def unschedule(self, event):
        if event is None or event not in self.events or event.timestamp < self.current_time:
            return

        if self.log_event_filter is None or self.log_event_filter.match(event.__class__.__name__) is not None:
            self.logger.debug('XX %s %s', format(abs(event.timestamp - self.start_time).total_seconds(), '.3f'), event)

        self.events.remove(event)
        self.events.sort()

    def schedule(self, event, delta: timedelta = None) -> None:
        """
        Schedule an event to occur in the future.

        :type event: simfantasy.events.Event
        :param event: An event.
        :param delta: Time difference from current for event to occur.
        """
        if delta is None:
            delta = timedelta()

        event.timestamp = self.current_time + delta

        heappush(self.events, event)

        if self.log_event_filter is None or self.log_event_filter.match(event.__class__.__name__) is not None:
            self.logger.debug('=> %s %s', format(abs(event.timestamp - self.start_time).total_seconds(), '.3f'), event)

    def run(self) -> None:
        """Run the simulation and process all events."""
        from simfantasy.events import ActorReadyEvent, CombatStartEvent, CombatEndEvent, ServerTickEvent

        self.schedule(CombatStartEvent(sim=self))
        self.schedule(CombatEndEvent(sim=self), self.combat_length)

        for delta in range(3, int(self.combat_length.total_seconds()), 3):
            self.schedule(ServerTickEvent(sim=self), delta=timedelta(seconds=delta))

        for actor in self.actors:
            self.schedule(ActorReadyEvent(sim=self, actor=actor))

        with humanfriendly.AutomaticSpinner(label='Simulating'):
            while len(self.events) > 0:
                event = heappop(self.events)

                if event.timestamp < self.current_time:
                    self.logger.critical(
                        '%s %s timestamp %s before current timestamp',
                        self.relative_timestamp,
                        event,
                        (event.timestamp - self.start_time).total_seconds()
                    )

                self.current_time = event.timestamp

                if self.log_event_filter is None or self.log_event_filter.match(event.__class__.__name__) is not None:
                    self.logger.debug('<= %s %s',
                                      format(abs(event.timestamp - self.start_time).total_seconds(), '.3f'), event)

                event.execute()

        self.logger.info('Analyzing encounter data...\n')

        for actor in self.actors:
            tables = []

            format_table = format_robust_table if self.vertical_output else format_pretty_table

            actor_dps = 0

            if len(actor.statistics['damage']) > 0:
                statistics = []
                dot_statistics = []

                actor_damage = 0

                for cls in actor.statistics['damage']:
                    s = actor.statistics['damage'][cls]

                    total_damage = sum(damage for timestamp, damage in s['damage'])
                    casts = len(s['casts'])
                    execute_time = sum(duration.total_seconds() for timestamp, duration in s['execute_time'])

                    actor_damage += total_damage

                    if len(s['ticks']) > 0:
                        tick_dmg = sum(damage for timestamp, damage in s['ticks'])

                        actor_damage += tick_dmg

                        dot_statistics.append((
                            cls.__class__.__name__,
                            len(s['ticks']),
                            format(tick_dmg, ',.0f')
                        ))

                    statistics.append((
                        cls.__class__.__name__,
                        casts,
                        format(total_damage, ',.0f'),
                        format(total_damage / casts, ',.3f'),
                        format(total_damage / self.combat_length.total_seconds(), ',.3f'),
                        format(total_damage / execute_time, ',.3f'),
                        format(len(s['critical_hits']) / casts * 100, '.3f'),
                        format(len(s['direct_hits']) / casts * 100, '.3f'),
                        format(len(s['critical_direct_hits']) / casts * 100, '.3f'),
                    ))

                if len(dot_statistics) > 0:
                    tables.append(format_table(dot_statistics, ('Name', 'Ticks', 'Damage')))

                tables.append(format_table(
                    statistics,
                    (
                        'Name',
                        'Casts',
                        'Damage',
                        'Damage (Mean)',
                        'DPS',
                        'DPET',
                        'Crit %',
                        'Direct %',
                        'D.Crit %'
                    )
                ))

                actor_dps = format(actor_damage / self.combat_length.total_seconds(), '.3f')

            if len(actor.statistics['auras']) > 0:
                statistics = []

                for cls in actor.statistics['auras']:
                    s = actor.statistics['auras'][cls]

                    total_overflow = sum(remains.total_seconds() for timestamp, remains in s['refreshes'])
                    average_overflow = total_overflow / len(s['refreshes']) if s['refreshes'] else 0

                    statistics.append((
                        cls.__name__,
                        format(len(s['applications']), ',.0f'),
                        format(len(s['expirations']), ',.0f'),
                        format(len(s['refreshes']), ',.0f'),
                        format(len(s['consumptions']), ',.0f'),
                        format(total_overflow, ',.3f'),
                        format(average_overflow, ',.3f'),
                    ))

                tables.append(format_table(
                    statistics,
                    ('Name', 'Applications', 'Expirations', 'Refreshes', 'Consumptions', 'Overflow', 'Overflow (Mean)'),
                ))

            if len(tables) > 0:
                self.logger.info('Actor: %s (%s DPS)\n\n%s\n', actor.name, actor_dps, '\n'.join(tables))

        self.logger.info('Quitting!')

    @property
    def relative_timestamp(self):
        return format((self.current_time - self.start_time).total_seconds(), '.3f')

    def __set_logger(self, log_level: int):
        logger = logging.getLogger()
        logger.setLevel(log_level)

        logstream = logging.StreamHandler()
        logstream.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))

        logger.addHandler(logstream)

        self.logger = logger


class Aura(ABC):
    """A buff or debuff that can be applied to a target."""

    duration: timedelta = None
    """Initial duration of the effect."""

    refresh_behavior: RefreshBehavior = None
    refresh_extension: timedelta = None
    max_stacks: int = 1

    def __init__(self) -> None:
        self.application_event = None
        self.expiration_event = None
        self.stacks = 0

    def apply(self, target):
        if self in target.auras:
            target.sim.logger.critical(
                '%s Adding duplicate buff %s into %s',
                target.sim.relative_timestamp, self, target
            )

        self.stacks = 1
        target.auras.append(self)

    def expire(self, target):
        try:
            self.stacks = 0
            target.auras.remove(self)
        except ValueError:
            target.sim.logger.critical('%s Failed removing %s from %s',
                                       (target.sim.current_time - target.sim.start_time).total_seconds(), self, target)

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
                 equipment: Dict[Slot, 'Item'] = None):
        """
        Create a new actor.

        :param sim: The encounter that the actor will enter.
        :param race: Race and clan.
        :param level: Level. Note that most calculations only work at 70.
        :param target: Primary target.
        """
        if level is None:
            level = 70

        if equipment is None:
            equipment = {}

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

        self.stats = self.calculate_base_stats()

        self.gear: Dict[Slot, Union[Item, Weapon]] = {}
        self.equip_gear(equipment)

        self.resources: Dict[Resource, Tuple[int, int]] = self.calculate_resources()

        self.statistics = {
            'actions': {},
            'auras': {},
            'damage': {},
            'dots': {},
            'resources': {},
        }

        self.sim.actors.append(self)

        self.sim.logger.debug('Initialized: %s', self)

    def calculate_resources(self):
        main_stat = main_stat_per_level[self.level]
        job_resources = get_base_resources_by_job(self.job)

        # FIXME It's broken.
        hp = floor(3600 * (job_resources[Resource.HEALTH] / 100)) + \
             floor((self.stats[Attribute.VITALITY] - main_stat) * 21.5)
        mp = floor(
            (job_resources[Resource.MANA] / 100) *
            ((6000 * (self.stats[Attribute.PIETY] - 292) / 2170) + 12000)
        )

        return {
            Resource.HEALTH: (hp, hp),
            Resource.MANA: (mp, mp),
        }

    @property
    def target_data(self):
        if self.target not in self.__target_data:
            self.__target_data[self.target] = self._target_data_class(source=self)

        return self.__target_data[self.target]

    @property
    def ready(self):
        return (self.animation_unlock_at is None and self.gcd_unlock_at is None) or (
                self.animation_unlock_at <= self.sim.current_time and self.gcd_unlock_at <= self.sim.current_time)

    def equip_gear(self, equipment: Dict[Slot, 'Item']):
        """
        Equip items and adjust stats accordingly.

        :param equipment: Dictionary mapping :class:`Slot<simfantasy.enums.Slot>` to :class:`Item`.
        :return:
        """
        for slot, item in equipment.items():
            if not slot & item.slot:
                raise Exception('Tried to place equipment in an incorrect slot.')

            if slot in self.gear and self.gear[slot] is not None:
                raise Exception('Tried to replace gear in slot.')

            self.gear[slot] = item

            for gear_stat, bonus in item.stats.items():
                if gear_stat not in self.stats:
                    self.stats[gear_stat] = 0

                self.stats[gear_stat] += bonus

            for meld_stat, bonus in item.melds:
                if meld_stat not in self.stats:
                    self.stats[meld_stat] = 0

                self.stats[meld_stat] += bonus

    @abstractmethod
    def decide(self) -> None:
        """Given current simulation environment, decide what action should be performed, if any."""

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


class Item:
    def __init__(self,
                 slot: Slot,
                 name: str = None,
                 stats: Dict[Attribute, int] = None,
                 melds: List[Tuple[Attribute, int]] = None):
        if melds is None:
            melds = []

        self.slot = slot
        self.name = name
        self.stats = stats
        self.melds = melds


class Weapon(Item):
    def __init__(self,
                 physical_damage: int,
                 magic_damage: int,
                 auto_attack: float,
                 delay: float,
                 name: str = None,
                 stats: Dict[Attribute, int] = None,
                 melds: List[Tuple[Attribute, int]] = None):
        super().__init__(slot=Slot.WEAPON, name=name, stats=stats, melds=melds)

        self.physical_damage = physical_damage
        self.magic_damage = magic_damage
        self.auto_attack = auto_attack
        self.delay = delay
