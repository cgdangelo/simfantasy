from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from math import floor
from typing import ClassVar, Dict, Iterable, List, Tuple, Union

import humanfriendly

from simfantasy.auras import Aura
from simfantasy.common_math import get_base_resources_by_job, get_base_stats_by_job, get_racial_attribute_bonuses, \
    main_stat_per_level, piety_per_level, sub_stat_per_level
from simfantasy.enums import Attribute, Job, Race, Resource, Role, Slot
from simfantasy.equipment import Item, Materia, Weapon
from simfantasy.simulator import Simulation


class TargetData(ABC):
    pass


class Actor:
    """A participant in an encounter.

    Warnings:
        Although level is accepted as an argument, many of the formulae only work at level 70. This argument may be
        deprecated in the future, or at least restricted to max levels of each game version, i.e., 50, 60, 70 for
        A Realm Reborn, Heavensward, and Stormblood respectively, where it's more likely that someone spent the time to
        figure out all the math.

    Arguments:
        sim (simfantasy.simulator.Simulation): Pointer to the simulation that the actor is participating in.
        race (simfantasy.enums.Race): Race and clan of the actor.
        level (int): Level of the actor.
        target (simfantasy.actor.Actor): The enemy that the actor is targeting.
        name (str): Name of the actor.
        gear (Optional[Dict[~simfantasy.enums.Slot, Union[~simfantasy.simulator.Item, ~simfantasy.simulator.Weapon]]]):
            Collection of equipment that the actor is wearing.

    Attributes:
        _target_data_class (Type[simfantasy.simulator.TargetData]): Reference to class type that is used to track target
            data.
        __target_data (Dict[~simfantasy.simulator.Actor, ~simfantasy.simulator.TargetData): Mapping of actors to any
            available target state data.
        animation_unlock_at (datetime.datetime): Timestamp when the actor will be able to execute actions again without
            being inhibited by animation lockout.
        auras (List[simfantasy.auras.Aura]): Auras, both friendly and hostile, that exist on the actor.
        gcd_unlock_at (datetime.datetime): Timestamp when the actor will be able to execute GCD actions again without
            being inhibited by GCD lockout.
        gear (Dict[~simfantasy.enums.Slot, Union[~simfantasy.simulator.Item, ~simfantasy.simulator.Weapon]]):
            Collection of equipment that the actor is wearing.
        job (simfantasy.enums.Job): The actor's job specialization.
        level (int): Level of the actor.
        name (str): Name of the actor.
        race (simfantasy.enums.Race): Race and clan of the actor.
        resources (Dict[~simfantasy.enums.Resource, Tuple[int, int]]): Mapping of resource type to a tuple containing
            the current amount and maximum capacity.
        sim (simfantasy.simulator.Simulation): Pointer to the simulation that the actor is participating in.
        statistics (Dict[str, List[Dict[Any, Any]]]): Collection of different event occurrences that are used for
            reporting and visualizations.
        stats (Dict[~simfantasy.enums.Attribute, int]): Mapping of attribute type to amount.
        target (simfantasy.simulator.Actor): The enemy that the actor is targeting.
    """

    job: Job = None
    role: Role = None
    _target_data_class: ClassVar[TargetData] = None

    # TODO Get rid of level?
    def __init__(self, sim: Simulation, race: Race, level: int = None, target: 'Actor' = None, name: str = None,
                 gear: Dict[Slot, Union[Item, Weapon]] = None):
        if level is None:
            level = 70

        if gear is None:
            gear = {}

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

        self.stats: Dict[Attribute, int] = {}
        self.gear: Dict[Slot, Union[Item, Weapon]] = {}
        self.resources: Dict[Resource, Tuple[int, int]] = {}

        self.equip_gear(gear)

        self.statistics = {}

        self.sim.actors.append(self)

        self.sim.logger.debug('Initialized: %s', self)

    def arise(self):
        """Prepare the actor for combat."""
        self.__target_data = {}
        self.animation_unlock_at = None
        self.gcd_unlock_at = None
        self.auras.clear()

        self.stats = self.calculate_base_stats()
        self.apply_gear_attribute_bonuses()
        self.resources = self.calculate_resources()

        self.statistics = {
            'auras': [],
            'damage': [],
            'resources': [],
        }

    def calculate_resources(self):
        """Determine the resource levels for the actor.

        In particular, sets the HP, MP and TP resource levels.
        """
        main_stat = main_stat_per_level[self.level]
        job_resources = get_base_resources_by_job(self.job)

        # FIXME It's broken.
        # @formatter:off
        hp = floor(3600 * (job_resources[Resource.HP] / 100)) + floor(
            (self.stats[Attribute.VITALITY] - main_stat) * 21.5)
        mp = floor((job_resources[Resource.MP] / 100) * ((6000 * (self.stats[Attribute.PIETY] - 292) / 2170) + 12000))
        # @formatter:on

        return {
            Resource.HP: (hp, hp),
            Resource.MP: (mp, mp),
            Resource.TP: (1000, 1000),  # TODO Math for this?
        }

    @property
    def target_data(self) -> TargetData:
        """Return target state data.

        For new targets, or at least ones that the actor has never switched to before, there will not be any target data
        available. In that scenario, this property initializes a new instance of the target data class and returns it.
        If there is already target state data, it will be returned directly.

        Returns:
            simfantasy.actor.TargetData: Contains all the target state data from the source actor to the target.
        """
        if self.target not in self.__target_data:
            self.__target_data[self.target] = self._target_data_class(source=self)

        return self.__target_data[self.target]

    @property
    def gcd_up(self) -> bool:
        """Determine if the actor is GCD locked.

        The global cooldown, or GCD, is a 2.5s lockout that prevents other GCD actions from being performed. Actions
        on the GCD are constrained by their "execute time", or :math:`\\max_{GCD, CastTime}`.

        Examples:
            Consider an actor that has just performed some action, and is thus gcd locked for 0.75s:

            >>> sim = Simulation()
            >>> sim.current_time = datetime.now()
            >>> actor = Actor(sim, Race.ENEMY)
            >>> actor.gcd_unlock_at = sim.current_time + timedelta(seconds=0.75)

            During this period, the actor will be unable to perform actions that are also on the GCD:

            >>> actor.gcd_up
            False

            However, once the simulation's game clock advances past the GCD lockout timestamp, the actor can once
            again perform GCD actions:

            >>> sim.current_time = actor.gcd_unlock_at + timedelta(seconds=1)
            >>> actor.gcd_up
            True

        Returns:
            bool: True if the actor is still GCD locked, False otherwise.
        """
        return self.gcd_unlock_at is None or self.gcd_unlock_at <= self.sim.current_time

    @property
    def animation_up(self) -> bool:
        """Determine if the actor is animation locked.

        Many actions have an animation timing of 0.75s. This locks out the actor from performing multiple oGCD actions
        simultaneously. This lockout is tracked and can inhibit actions from being performed accordingly.

        Examples:
            Consider an actor that has just performed some action, and is thus animation locked for 0.75s:

            >>> sim = Simulation()
            >>> sim.current_time = datetime.now()
            >>> actor = Actor(sim, Race.ENEMY)
            >>> actor.animation_unlock_at = sim.current_time + timedelta(seconds=0.75)

            During this period, the actor will be unable to perform actions that also have animation timings:

            >>> actor.animation_up
            False

            However, once the simulation's game clock advances past the animation lockout timestamp, the actor can once
            again perform actions:

            >>> sim.current_time = actor.animation_unlock_at + timedelta(seconds=1)
            >>> actor.animation_up
            True

        Returns:
            bool: True if the actor is still animation locked, False otherwise.
        """
        return self.animation_unlock_at is None or self.animation_unlock_at <= self.sim.current_time

    def equip_gear(self, gear: Dict[Slot, Union[Weapon, Item]]):
        """Equip items in the appropriate slots."""
        for slot, item in gear.items():
            if not slot & item.slot:
                raise Exception('Tried to place equipment in an incorrect slot.')

            self.gear[slot] = item

    def apply_gear_attribute_bonuses(self):
        """Apply stat bonuses gained from items and melds.

        Examples:
            Consider the `Kujakuo Kai`_ bow for Bards:

            >>> kujakuo_kai = Weapon(item_level=370, name='Kujakuo Kai', physical_damage=104, magic_damage=70,
            ...                      auto_attack=105.38, delay=3.04,
            ...                      stats={
            ...                          Attribute.DEXTERITY: 347,
            ...                          Attribute.VITALITY: 380,
            ...                          Attribute.CRITICAL_HIT: 218,
            ...                          Attribute.DIRECT_HIT: 311,
            ...                      })

            Equipping this item will add its stat bonuses to the actor:

            >>> sim = Simulation()
            >>> actor = Actor(sim, Race.ENEMY)
            >>> actor.equip_gear({Slot.WEAPON: kujakuo_kai})
            >>> actor.apply_gear_attribute_bonuses()
            >>> actor.stats[Attribute.DEXTERITY] == 347
            True

            Bonuses from melded materia are also applied:

            >>> savage_aim_vi = Materia(Attribute.CRITICAL_HIT, 40)
            >>> kujakuo_kai.melds = [savage_aim_vi, savage_aim_vi]
            >>> actor.stats = {}
            >>> actor.equip_gear({Slot.WEAPON: kujakuo_kai})
            >>> actor.apply_gear_attribute_bonuses()
            >>> actor.stats[Attribute.CRITICAL_HIT] == 218 + 40 + 40
            True

        .. _Kujakuo Kai:
            https://na.finalfantasyxiv.com/lodestone/playguide/db/item/81019e5dbd4/
        """
        for slot, item in self.gear.items():
            for gear_stat, bonus in item.stats.items():
                if gear_stat not in self.stats:
                    self.stats[gear_stat] = 0

                self.stats[gear_stat] += bonus

            for materia in item.melds:
                if materia.attribute not in self.stats:
                    self.stats[materia.attribute] = 0

                self.stats[materia.attribute] += materia.bonus

    @abstractmethod
    def decide(self) -> Iterable:
        """Given current simulation environment, decide what action should be performed, if any.

        The "decision engine" for each actor is a generator function that yields the desired actions. This method should
        be constructed as a priority list, where more important actions are towards the top, and less important actions
        towards the bottom. A notable exception is for filler spells, i.e. :class:`~simfantasy.events.MeleeAttackAction`
        and :class:`~simfantasy.melee.ShotAction`. Auto-attack actions don't interfere with other skills and happen at
        regular intervals, so they can (and should) be safely placed at top priority.

        See Also:
            Refer to :func:`simfantasy.events.ActorReadyEvent.execute` for clarification on what happens with actions
            yielded from the decision engine.

        Yields:
            Optional[simfantasy.events.Action]: An instance of an action that will attempt to be performed. If None is
            yielded, no further attempts to find a suitable action will be made until the actor is ready again.
        """
        yield

    def has_aura(self, aura: Aura) -> bool:
        """Determine if the aura exists on the actor.

        Warnings:
            Probably deprecated in favor of :func:`simfantasy.simulator.Aura.up`.
        """
        return aura in self.auras

    def calculate_base_stats(self) -> Dict[Attribute, int]:
        """Calculate and set base primary and secondary stats.

        Base stats are determined by a combination of level, job and race/clan affiliation.

        Returns:
            Dict[Attribute, int]: Mapping of attributes to amounts.
        """
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
