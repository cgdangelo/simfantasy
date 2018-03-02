from math import floor
from typing import Dict, NamedTuple, Tuple, Union, List

import humanfriendly
import simpy

from simfantasy.common_math import get_base_resources_by_job, get_base_stats_by_job, get_racial_attribute_bonuses, \
    main_stat_per_level, piety_per_level, sub_stat_per_level
from simfantasy.enums import Attribute, Job, Race, Resource, Role, Slot


class Materia(NamedTuple):
    attribute: Attribute
    bonus: int
    name: str = None


class Item(NamedTuple):
    slot: Slot
    stats: Tuple[Tuple[Attribute, int], ...]
    melds: Tuple[Materia, ...] = None
    name: str = None


class Weapon(NamedTuple):
    magic_damage: int
    physical_damage: int
    delay: float
    auto_attack: float
    stats: Tuple[Tuple[Attribute, int], ...]
    slot = Slot.WEAPON
    melds: Tuple[Materia, ...] = None
    name: str = None


class Actor:
    job: Job = None
    role: Role = None

    def __init__(self, env: simpy.Environment, race: Race, name: str = None, level: int = 70,
                 gear: Tuple[Tuple[Slot, Union[Item, Weapon]], ...] = None):
        if name is None:
            name = humanfriendly.text.random_string(length=10)

        if gear is None:
            gear = {}

        self.env = env
        self.race = race
        self.name = name
        self.level = level

        self.stats = self._calculate_base_stats()

        self.gear = ()
        self._equip_gear(gear)

        self.resources = self._calculate_resources()

    def _calculate_base_stats(self) -> Dict[Attribute, int]:
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

    def _equip_gear(self, gear: Tuple[Tuple[Slot, Union[Weapon, Item]], ...]):
        for slot, item in gear:
            if not slot & item.slot:
                raise Exception('Tried to place equipment in an incorrect slot.')

            self.gear += item

            for gear_stat, bonus in item.stats:
                if gear_stat not in self.stats:
                    self.stats[gear_stat] = 0

                self.stats[gear_stat] += bonus

            for materia in item.melds:
                if materia.attribute not in self.stats:
                    self.stats[materia.attribute] = 0

                self.stats[materia.attribute] += materia.bonus

    def _calculate_resources(self):
        main_stat = main_stat_per_level[self.level]
        job_resources = get_base_resources_by_job(self.job)

        # FIXME It's broken.
        hp = floor(3600 * (job_resources[Resource.HEALTH] / 100)) + floor(
            (self.stats[Attribute.VITALITY] - main_stat) * 21.5)
        mp = floor((job_resources[Resource.MANA] / 100) * ((6000 * (self.stats[Attribute.PIETY] - 292) / 2170) + 12000))

        return {
            Resource.HEALTH: simpy.Container(self.env, init=hp, capacity=hp),
            Resource.MANA: simpy.Container(self.env, init=mp, capacity=mp),
        }


class Bard(Actor):
    job = Job.BARD
    role = Role.DPS


class Simulation:
    def __init__(self, env: simpy.Environment, actors: List[Actor], combat_length: float = 300):
        self.env = env
        self.actors = actors
        self.combat_length = combat_length
        self.process = env.process(self._main_loop())
        self.server_tick = env.process(self._server_tick())

    def _main_loop(self):
        while True:
            print('%s Step' % env.now)
            yield env.timeout(1)

    def _server_tick(self):
        while True:
            print('%s Server tick' % env.now)
            env.process(self._native_mana_regen())
            yield env.timeout(3)

    def _native_mana_regen(self):
        for actor in self.actors:
            mana = actor.resources[Resource.MANA]
            tick = floor(mana.capacity * 0.02)

            print('%s Mana tick %s %s' % (self.env.now, actor, tick))

            yield mana.put(tick)


savage_aim_vi = Materia(Attribute.CRITICAL_HIT, 40)
savage_might_vi = Materia(Attribute.DETERMINATION, 40)
heavens_eye_vi = Materia(Attribute.DIRECT_HIT, 40)
vitality_vi = Materia(Attribute.VITALITY, 25)

kujakuo = Weapon(name='Kujakuo', physical_damage=102, magic_damage=69, auto_attack=103.36, delay=3.04,
                 stats=((Attribute.DEXTERITY, 330), (Attribute.CRITICAL_HIT, 209), (Attribute.VITALITY, 358),
                        (Attribute.DIRECT_HIT, 298)),
                 melds=(savage_aim_vi, savage_aim_vi))

true_linen_cap = Item(name='True Linen Cap of Aiming', slot=Slot.HEAD,
                      stats=((Attribute.DEXTERITY, 180), (Attribute.CRITICAL_HIT, 114), (Attribute.VITALITY, 193),
                             (Attribute.DIRECT_HIT, 163), (Attribute.DEFENSE, 428), (Attribute.MAGIC_DEFENSE, 428)),
                      melds=(savage_aim_vi, savage_might_vi))

true_linen_jacket = Item(name='True Linen Jacket of Aiming', slot=Slot.BODY,
                         stats=((Attribute.DEXTERITY, 293), (Attribute.CRITICAL_HIT, 265), (Attribute.VITALITY, 314),
                                (Attribute.DETERMINATION, 186), (Attribute.DEFENSE, 599),
                                (Attribute.MAGIC_DEFENSE, 599)),
                         melds=(heavens_eye_vi, heavens_eye_vi))

augmented_tomestone_gloves = Item(name='Augmented Lost Allagan Gloves of Aiming', slot=Slot.HANDS,
                                  stats=((Attribute.DEXTERITY, 172), (Attribute.CRITICAL_HIT, 156),
                                         (Attribute.VITALITY, 182), (Attribute.DIRECT_HIT, 109),
                                         (Attribute.DEFENSE, 418), (Attribute.MAGIC_DEFENSE, 418)),
                                  melds=(heavens_eye_vi, savage_might_vi))

slothskin_belt = Item(name='Slothskin Belt of Aiming', slot=Slot.WAIST,
                      stats=((Attribute.DEXTERITY, 135), (Attribute.DETERMINATION, 122), (Attribute.VITALITY, 145),
                             (Attribute.DIRECT_HIT, 86), (Attribute.DEFENSE, 371), (Attribute.MAGIC_DEFENSE, 371)),
                      melds=(savage_aim_vi,))

true_linen_breeches = Item(name='True Linen Breeches of Aiming', slot=Slot.LEGS,
                           stats=((Attribute.DEXTERITY, 293), (Attribute.SKILL_SPEED, 265), (Attribute.VITALITY, 314),
                                  (Attribute.DIRECT_HIT, 186), (Attribute.DEFENSE, 599),
                                  (Attribute.MAGIC_DEFENSE, 599)),
                           melds=(savage_aim_vi, savage_aim_vi))

slothskin_boots = Item(name='Slothskin Boots of Aiming', slot=Slot.FEET,
                       stats=((Attribute.DEXTERITY, 180), (Attribute.CRITICAL_HIT, 114), (Attribute.VITALITY, 193),
                              (Attribute.SKILL_SPEED, 163), (Attribute.DEFENSE, 428), (Attribute.MAGIC_DEFENSE, 428)),
                       melds=(savage_aim_vi, heavens_eye_vi))

carborundum_earrings = Item(name='Carborundum Earring of Aiming', slot=Slot.EARRINGS,
                            stats=((Attribute.DEXTERITY, 135), (Attribute.SKILL_SPEED, 122),
                                   (Attribute.DETERMINATION, 86), (Attribute.DEFENSE, 1), (Attribute.MAGIC_DEFENSE, 1)),
                            melds=(savage_aim_vi,))

diamond_necklace = Item(name='Diamond Necklace of Aiming', slot=Slot.NECKLACE,
                        stats=((Attribute.DEXTERITY, 149), (Attribute.DETERMINATION, 133), (Attribute.CRITICAL_HIT, 93),
                               (Attribute.DEFENSE, 1), (Attribute.MAGIC_DEFENSE, 1)),
                        melds=(vitality_vi,))

augmented_tomestone_bracelet = Item(name='Augmented Lost Allagan Bracelet of Aiming', slot=Slot.BRACELET,
                                    stats=((Attribute.DEXTERITY, 129), (Attribute.DIRECT_HIT, 82),
                                           (Attribute.CRITICAL_HIT, 117), (Attribute.DEFENSE, 1),
                                           (Attribute.MAGIC_DEFENSE, 1)),
                                    melds=(vitality_vi,))

augmented_tomestone_ring = Item(name='Augmented Lost Allagan Ring of Aiming', slot=Slot.RING,
                                stats=((Attribute.DEXTERITY, 129), (Attribute.DETERMINATION, 117),
                                       (Attribute.CRITICAL_HIT, 82), (Attribute.DEFENSE, 1),
                                       (Attribute.MAGIC_DEFENSE, 1)),
                                melds=(vitality_vi,))

carborundum_ring = Item(name='Carborundum Ring of Aiming', slot=Slot.RING,
                        stats=((Attribute.DEXTERITY, 135), (Attribute.DIRECT_HIT, 122), (Attribute.CRITICAL_HIT, 86),
                               (Attribute.DEFENSE, 1), (Attribute.MAGIC_DEFENSE, 1)),
                        melds=(vitality_vi,))

env = simpy.Environment()

bard = Bard(env, race=Race.HIGHLANDER, name='Dikembe',
            gear=((Slot.WEAPON, kujakuo), (Slot.HEAD, true_linen_cap), (Slot.BODY, true_linen_jacket),
                  (Slot.HANDS, augmented_tomestone_gloves), (Slot.WAIST, slothskin_belt),
                  (Slot.LEGS, true_linen_breeches), (Slot.FEET, slothskin_boots), (Slot.EARRINGS, carborundum_earrings),
                  (Slot.NECKLACE, diamond_necklace), (Slot.BRACELET, augmented_tomestone_bracelet),
                  (Slot.LEFT_RING, augmented_tomestone_ring), (Slot.RIGHT_RING, carborundum_ring)))

sim = Simulation(env, [bard])

env.run(until=30)
