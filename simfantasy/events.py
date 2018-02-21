from datetime import timedelta
from math import ceil, floor

import numpy

from simfantasy.common_math import divisor_per_level, get_base_stats_by_job, \
    main_stat_per_level, sub_stat_per_level
from simfantasy.enums import Attribute, Job, Slot
from simfantasy.simulator import Actor, Aura, Simulation


class Event:
    def __init__(self, sim: Simulation):
        self.sim = sim

    def __lt__(self, other):
        return False

    def __str__(self):
        return '<{cls}>'.format(cls=self.__class__.__name__)

    def execute(self):
        pass


class CombatEndEvent(Event):
    def execute(self):
        self.sim.events.clear()


class AuraEvent(Event):
    def __init__(self, sim: Simulation, target: Actor, aura: Aura):
        super().__init__(sim=sim)

        self.target = target
        self.aura = aura

    def __str__(self):
        return '<{cls} aura={aura} target={target}>'.format(cls=self.__class__.__name__,
                                                            aura=self.aura.__class__.__name__,
                                                            target=self.target.name)


class ApplyAuraEvent(AuraEvent):
    def execute(self):
        self.target.auras.append(self.aura)
        self.aura.apply(target=self.target)


class ExpireAuraEvent(AuraEvent):
    def execute(self):
        if self.aura in self.target.auras:
            self.target.auras.remove(self.aura)
            self.aura.expire(target=self.target)


class PlayerReadyEvent(Event):
    def __init__(self, sim: Simulation, actor: Actor):
        super().__init__(sim=sim)

        self.actor = actor

    def execute(self):
        pass

    def __str__(self):
        return '<{cls} actor={actor}>'.format(cls=self.__class__.__name__,
                                              actor=self.actor.name)


class CastEvent(Event):
    animation = timedelta(seconds=0.75)
    affected_by: Attribute = None
    hastened_by: Attribute = None
    off_gcd: bool = False
    potency: int = 0

    def __init__(self, sim: Simulation, source: Actor, target: Actor = None):
        super().__init__(sim=sim)

        self.source = source
        self.target = target

        self.__is_critical_hit = None
        self.__is_direct_hit = None

    def execute(self):
        self.sim.schedule_in(PlayerReadyEvent(sim=self.sim, actor=self.source),
                             delta=self.animation if self.off_gcd else self.gcd)

        self.source.animation_unlock_at = self.sim.current_time + self.animation
        self.source.gcd_unlock_at = self.sim.current_time + (self.gcd if not self.off_gcd else timedelta())

        if self.__class__ not in self.source.statistics:
            self.source.statistics[self.__class__] = {
                'casts': [],
                'damage': [],
                'critical_hits': [],
                'direct_hits': [],
                'critical_direct_hits': [],
            }

        self.source.statistics[self.__class__]['casts'].append(self.sim.current_time)
        self.source.statistics[self.__class__]['damage'].append((self.sim.current_time, self.direct_damage))

        if self.is_critical_hit:
            self.source.statistics[self.__class__]['critical_hits'].append(self.sim.current_time)

        if self.is_direct_hit:
            self.source.statistics[self.__class__]['direct_hits'].append(self.sim.current_time)

        if self.is_critical_hit and self.is_direct_hit:
            self.source.statistics[self.__class__]['critical_direct_hits'].append(self.sim.current_time)

    @property
    def critical_hit_chance(self):
        sub_stat = sub_stat_per_level[self.source.level]
        divisor = divisor_per_level[self.source.level]
        p_chr = floor(200 * (self.source.stats[Attribute.CRITICAL_HIT] - sub_stat) / divisor + 50) / 1000

        return p_chr

    @property
    def is_critical_hit(self):
        if self.__is_critical_hit is None:
            if self.critical_hit_chance >= 100:
                self.__is_critical_hit = True
            else:
                self.__is_critical_hit = numpy.random.uniform() <= self.critical_hit_chance

        return self.__is_critical_hit

    @property
    def direct_hit_chance(self):
        sub_stat = sub_stat_per_level[self.source.level]
        divisor = divisor_per_level[self.source.level]
        p_dhr = floor(550 * (self.source.stats[Attribute.DIRECT_HIT] - sub_stat) / divisor) / 1000

        return p_dhr

    @property
    def is_direct_hit(self):
        if self.__is_direct_hit is None:
            if self.direct_hit_chance >= 100:
                self.__is_direct_hit = True
            else:
                self.__is_direct_hit = numpy.random.uniform() <= self.direct_hit_chance

        return self.__is_direct_hit

    @property
    def direct_damage(self) -> int:
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
    def gcd(self):
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

    def __str__(self):
        return '<{cls} source={source} target={target} crit={crit} direct={direct}>'.format(
            cls=self.__class__.__name__,
            source=self.source.name,
            target=self.target.name,
            crit=self.is_critical_hit,
            direct=self.is_direct_hit,
        )
