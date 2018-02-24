import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from heapq import heapify, heappop, heappush
from math import floor
from typing import ClassVar, Dict, List, Tuple, Union

import humanfriendly
from humanfriendly.tables import format_pretty_table, format_robust_table

from simfantasy.common_math import get_base_stats_by_job, get_racial_attribute_bonuses, \
    main_stat_per_level, sub_stat_per_level
from simfantasy.enums import Attribute, Job, Race, RefreshBehavior, Slot


class Simulation:
    """A simulated combat encounter."""

    def __init__(self, combat_length: timedelta = None, log_level: int = None, vertical_output: bool = None,
                 log_event_filter: str = None, execute_time: timedelta = timedelta(seconds=60)):
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

    def schedule_in(self, event, delta: timedelta = None) -> None:
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
        from simfantasy.events import ActorReadyEvent, CombatStartEvent, CombatEndEvent

        self.schedule_in(CombatStartEvent(sim=self))
        self.schedule_in(CombatEndEvent(sim=self), self.combat_length)

        for actor in self.actors:
            self.schedule_in(ActorReadyEvent(sim=self, actor=actor))

        with humanfriendly.AutomaticSpinner(label='Simulating'):
            while len(self.events) > 0:
                event = heappop(self.events)

                self.current_time = event.timestamp

                if self.log_event_filter is None or self.log_event_filter.match(event.__class__.__name__) is not None:
                    self.logger.debug('<= %s %s',
                                      format(abs(event.timestamp - self.start_time).total_seconds(), '.3f'), event)

                event.execute()

        self.logger.info('Analyzing encounter data...\n')

        for actor in self.actors:
            tables = []

            format_table = format_robust_table if self.vertical_output else format_pretty_table

            if len(actor.statistics['damage']) > 0:
                statistics = []

                for cls in actor.statistics['damage']:
                    s = actor.statistics['damage'][cls]
                    total_damage = sum(damage for timestamp, damage in s['damage'])
                    casts = len(s['casts'])
                    execute_time = sum(duration.total_seconds() for timestamp, duration in s['execute_time'])

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
                self.logger.info('Actor: %s\n\n%s\n', actor.name, '\n'.join(tables))

        self.logger.info('Quitting!')

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

    def __init__(self) -> None:
        self.application_event = None
        self.expiration_event = None

    def apply(self, target):
        target.auras.append(self)

    def expire(self, target):
        target.auras.remove(self)

    @property
    def up(self):
        return self.remains > timedelta()

    @property
    def remains(self):
        if self.expiration_event is None:
            return timedelta()

        return self.expiration_event.timestamp - self.expiration_event.sim.current_time


class TickingAura(Aura):
    @property
    @abstractmethod
    def potency(self):
        pass

    def __init__(self) -> None:
        super().__init__()

        self.tick_event = None


class Actor:
    """A participant in an encounter."""

    job: Job = None
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

        self.statistics = {
            'actions': {},
            'auras': {},
            'damage': {},
        }

        self.sim.actors.append(self)

        self.sim.logger.debug('Initialized: %s', self)

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
                 name: str = None,
                 stats: Dict[Attribute, int] = None,
                 melds: List[Tuple[Attribute, int]] = None):
        super().__init__(slot=Slot.WEAPON, name=name, stats=stats, melds=melds)

        self.physical_damage = physical_damage
        self.magic_damage = magic_damage
