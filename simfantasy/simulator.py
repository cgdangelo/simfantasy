import logging
from abc import abstractmethod
from datetime import timedelta
from heapq import heappop, heapify, heappush
from typing import List, Dict, Type, Tuple

from simfantasy.common_math import calculate_base_stats
from simfantasy.enums import Race, Job, Attribute, Slot

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

logstream = logging.StreamHandler()
logstream.setFormatter(logging.Formatter('[%(levelname)s]\t%(message)s'))

logger.addHandler(logstream)


class Simulation:
    """A simulated combat encounter."""

    def __init__(self, combat_length: timedelta = None):
        """
        Create a new simulation.

        :param combat_length: Desired combat length. Default: 5 minutes.
        """
        if combat_length is None:
            combat_length = timedelta(minutes=5)

        self.combat_length: timedelta = combat_length
        """Total length of encounter. Not in real time."""

        self.actors: List[Actor] = []
        """List of actors involved in this encounter, i.e., players and enemies."""

        self.current_time: timedelta = timedelta()
        """Current game timestamp."""

        self.events = []
        """Scheduled events."""

        heapify(self.events)

    def schedule_in(self, event, delta: timedelta = None) -> None:
        """
        Schedule an event to occur in the future.

        :type event: simfantasy.events.Event
        :param event: An event.
        :param delta: Time difference from current for event to occur.
        """
        if delta is None:
            delta = timedelta()

        heappush(self.events, (self.current_time + delta, event))

    def run(self) -> None:
        """Run the simulation and process all events."""
        logger.info('%s Running!', timedelta())

        from simfantasy.events import CombatEndEvent
        self.schedule_in(CombatEndEvent(sim=self), self.combat_length)

        while self.current_time <= self.combat_length and len(self.events) > 0:
            for actor in self.actors:
                if actor.ready:
                    actor.decide()

            time, event = heappop(self.events)

            logger.debug('%s %s', time, event)

            event.execute()

            self.current_time = time


class Aura:
    """A buff or debuff that can be applied to a target."""

    duration: timedelta
    """Initial duration of the effect."""


class Actor:
    """A participant in an encounter."""

    job: Job = None

    # TODO Get rid of level?
    def __init__(self,
                 sim: Simulation,
                 race: Race,
                 level: int = None,
                 physical_damage: int = None,
                 magic_damage: int = None,
                 target: 'Actor' = None,
                 equipment: Dict[Slot, 'Item'] = None):
        """
        Create a new actor.

        :param sim: The encounter that the actor will enter.
        :param race: Race and clan.
        :param level: Level. Note that most calculations only work at 70.
        :param physical_damage: Current weapon's physical damage.
        :param magic_damage: Current weapon's magic damage.
        :param target: Primary target.
        """
        if level is None:
            level = 70

        if physical_damage is None:
            physical_damage = 0

        if magic_damage is None:
            magic_damage = 0

        if equipment is None:
            equipment = {}

        self.sim: Simulation = sim
        self.race: Race = race
        self.level: int = level
        self.physical_damage: int = physical_damage
        self.magic_damage: int = magic_damage
        self.target: 'Actor' = target

        self.animation_lock: timedelta = timedelta()
        self.gcd_lock: timedelta = timedelta()
        self.ready: bool = True
        self.auras: List[Aura] = []

        self.stats: Dict[Attribute, int] = dict(zip(
            (Attribute.STRENGTH, Attribute.DEXTERITY, Attribute.VITALITY, Attribute.INTELLIGENCE, Attribute.MIND),
            calculate_base_stats(self.level, self.__class__.job, race)
        ))

        self.sim.actors.append(self)

        self.gear: Dict[Attribute, Item] = {}
        self.equip_gear(equipment)

    def equip_gear(self, equipment: Dict[Slot, 'Item']):
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

        logger.debug(self.stats)

    @abstractmethod
    def decide(self) -> None:
        """Given current simulation environment, decide what action should be performed, if any."""

    def has_aura(self, aura_class: Type[Aura]) -> bool:
        """
        Determine if the aura exists on the actor.

        :param aura_class: The type of aura.
        :return: True if the aura is presence.
        """
        return any(isinstance(aura, aura_class) for aura in self.auras)

    def cast(self, cast_class, target: 'Actor' = None) -> None:
        """
        Cast an ability on the target.

        :type cast_class: type[simfantasy.events.CastEvent]
        :param cast_class: The type of ability.
        :param target: The target to cast on.
        """
        if target is None:
            target = self.target

        self.sim.schedule_in(cast_class(sim=self.sim, source=self, target=target))


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
                 melds: List[Tuple[Attribute, int]] = None):
        super().__init__(slot=Slot.WEAPON, name=name, stats={}, melds=melds)

        self.physical_damage = physical_damage
        self.magic_damage = magic_damage
