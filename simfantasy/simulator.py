import logging
from abc import abstractmethod
from datetime import datetime, timedelta
from heapq import heapify, heappop, heappush
from math import floor
from typing import Dict, List, Tuple, Type, Union

import humanfriendly
from humanfriendly.tables import format_pretty_table

from simfantasy.common_math import get_base_stats_by_job, get_racial_attribute_bonuses, \
    main_stat_per_level, sub_stat_per_level
from simfantasy.enums import Attribute, Job, Race, Slot, RefreshBehavior


class Simulation:
    """A simulated combat encounter."""

    def __init__(self, combat_length: timedelta = None, log_level: int = None):
        """
        Create a new simulation.

        :param combat_length: Desired combat length. Default: 5 minutes.
        """
        if combat_length is None:
            combat_length = timedelta(minutes=5)

        if log_level is None:
            log_level = logging.INFO

        self.combat_length: timedelta = combat_length
        """Total length of encounter. Not in real time."""

        self.actors: List[Actor] = []
        """List of actors involved in this encounter, i.e., players and enemies."""

        self.start_time: datetime = None

        self.current_time: datetime = None
        """Current game timestamp."""

        self.events = []
        """Scheduled events."""

        heapify(self.events)

        self.__set_logger(log_level)

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

        self.logger.debug('=> %s %s', format(abs(event.timestamp - self.start_time).total_seconds(), '.3f'), event)

    def run(self) -> None:
        """Run the simulation and process all events."""
        from simfantasy.events import CombatStartEvent, CombatEndEvent

        self.schedule_in(CombatStartEvent(sim=self))
        self.schedule_in(CombatEndEvent(sim=self), self.combat_length)

        with humanfriendly.AutomaticSpinner(label='Simulating'):
            while len(self.events) > 0:
                event = heappop(self.events)

                self.logger.debug('<= %s %s', format(abs(event.timestamp - self.start_time).total_seconds(), '.3f'), event)

                event.execute()

                self.current_time = event.timestamp

                for actor in self.actors:
                    if actor.ready:
                        actor.decide()

        self.logger.info('Analyzing encounter data...')

        for actor in self.actors:
            if len(actor.statistics['actions']) > 0:
                ability_statistics = []

                for cls in actor.statistics['actions']:
                    s = actor.statistics['actions'][cls]
                    total_damage = sum(damage for timestamp, damage in s['damage'])
                    casts = len(s['casts'])

                    ability_statistics.append((
                        cls.__name__,
                        casts,
                        format(total_damage, ',.0f'),
                        format(total_damage / self.combat_length.total_seconds(), ',.3f'),
                        humanfriendly.terminal.ansi_wrap(color='red',
                                                         text=format((len(s['critical_hits']) / casts) * 100, '.3f')),
                        humanfriendly.terminal.ansi_wrap(color='blue',
                                                         text=format((len(s['direct_hits']) / casts) * 100, '.3f')),
                        humanfriendly.terminal.ansi_wrap(color='magenta',
                                                         text=format((len(s['critical_direct_hits']) / casts) * 100,
                                                                     '.3f')),
                    ))

                table = format_pretty_table(
                    ability_statistics,
                    ('Name', 'Casts', 'Damage', 'DPS', 'Crit %', 'Direct %', 'D.Crit %')
                )
                self.logger.info('Actor: %s\n\n%s\n', actor.name, table)

        self.logger.info('Quitting')

    def __set_logger(self, log_level: int):
        logger = logging.getLogger()
        logger.setLevel(log_level)

        logstream = logging.StreamHandler()
        logstream.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))

        logger.addHandler(logstream)

        self.logger = logger


class Aura:
    """A buff or debuff that can be applied to a target."""

    duration: timedelta = None
    """Initial duration of the effect."""

    refresh_behavior: RefreshBehavior = None
    refresh_extension: timedelta = None

    def __init__(self) -> None:
        self.application_event = None
        self.expiration_event = None

    def apply(self, target):
        pass

    def expire(self, target):
        pass


class Actor:
    """A participant in an encounter."""

    job: Job = None

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

        self.animation_unlock_at: datetime = None
        self.gcd_unlock_at: datetime = None
        self.auras: List[Aura] = []

        self.stats = self.calculate_base_stats()

        self.gear: Dict[Slot, Union[Item, Weapon]] = {}
        self.equip_gear(equipment)

        self.statistics = {
            'actions': {},
            'buffs': {},
        }

        self.sim.actors.append(self)

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

    def cast(self, cast_class, target: 'Actor' = None) -> None:
        """
        Cast an ability on the target.

        :type cast_class: type[~simfantasy.events.CastEvent]
        :param cast_class: The type of ability.
        :param target: The target to cast on.
        """
        if target is None:
            target = self.target

        if not cast_class.is_off_gcd and \
                target.gcd_unlock_at is not None and \
                target.gcd_unlock_at > self.sim.current_time:
            return

        if cast_class.is_off_gcd and \
                target.animation_unlock_at is not None and \
                target.animation_unlock_at > self.sim.current_time:
            return

        if cast_class.can_recast_at is not None and cast_class.can_recast_at > self.sim.current_time:
            return

        self.sim.schedule_in(cast_class(sim=self.sim, source=self, target=target))

    def on_cooldown(self, action_class):
        return action_class.can_recast_at is not None and action_class.can_recast_at > self.sim.current_time

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
