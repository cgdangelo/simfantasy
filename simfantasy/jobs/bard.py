from datetime import timedelta
from typing import Dict, List

from simfantasy.enums import Attribute, Job, Race, Slot
from simfantasy.events import Action
from simfantasy.simulator import Actor, Aura, Item, Simulation, TickingAura


class Bard(Actor):
    job = Job.BARD

    def __init__(self,
                 sim: Simulation,
                 race: Race,
                 level: int = None,
                 target: Actor = None,
                 name: str = None,
                 equipment: Dict[Slot, Item] = None):
        super().__init__(sim=sim, race=race, level=level, target=target, name=name, equipment=equipment)

        self._target_data_class = TargetData
        self.actions = Actions(sim, self)
        self.buffs = Buffs()

    def decide(self):
        if not self.buffs.raging_strikes.up and not self.actions.raging_strikes.on_cooldown:
            return self.actions.raging_strikes.perform()

        if self.buffs.straight_shot.remains < timedelta(seconds=3):
            return self.actions.straight_shot.perform()

        if not self.target_data.venomous_bite.up or self.target_data.venomous_bite.remains < timedelta(seconds=3):
            return self.actions.venomous_bite.perform()

        if not self.actions.sidewinder.on_cooldown:
            return self.actions.sidewinder.perform()

        self.actions.heavy_shot.perform()


class BardAction(Action):
    source: Bard
    hastened_by = Attribute.SKILL_SPEED
    powered_by = Attribute.ATTACK_POWER

    @property
    def _trait_multipliers(self) -> List[float]:
        yield from super()._trait_multipliers

        if self.source.level >= 20:
            yield 1.1

        if self.source.level >= 40:
            yield 1.2

    @property
    def _buff_multipliers(self) -> List[float]:
        yield from super()._buff_multipliers

        if self.source.buffs.raging_strikes.up:
            yield 1.1


class Actions:
    def __init__(self, sim: Simulation, source: Bard):
        self.heavy_shot = HeavyShotAction(sim, source)
        self.raging_strikes = RagingStrikesAction(sim, source)
        self.sidewinder = SidewinderAction(sim, source)
        self.straight_shot = StraightShotAction(sim, source)
        self.venomous_bite = VenomousBiteAction(sim, source)


class Buffs:
    def __init__(self):
        self.straight_shot = StraightShotBuff()
        self.raging_strikes = RagingStrikesBuff()


class TargetData:
    def __init__(self, source: Bard):
        self.windbite = WindbiteDebuff(source=source)
        self.venomous_bite = VenomousBiteDebuff(source=source)


class HeavyShotAction(BardAction):
    potency = 150


class StraightShotBuff(Aura):
    duration = timedelta(seconds=30)

    def apply(self, target):
        super().apply(target)

        target.stats[Attribute.CRITICAL_HIT] *= 1.1

    def expire(self, target):
        super().expire(target)

        target.stats[Attribute.CRITICAL_HIT] /= 1.1


class StraightShotAction(BardAction):
    potency = 140

    def perform(self):
        self.schedule_aura_events(self.source, self.source.buffs.straight_shot)

        super().perform()


class RagingStrikesBuff(Aura):
    duration = timedelta(seconds=20)


class RagingStrikesAction(BardAction):
    base_recast_time = timedelta(seconds=90)
    is_off_gcd = True

    def perform(self):
        super().perform()

        self.schedule_aura_events(self.source, self.source.buffs.raging_strikes)


class VenomousBiteDebuff(TickingAura):
    def __init__(self, source: Bard):
        super().__init__()

        self.source = source

    @property
    def potency(self):
        return 40 if self.source.level < 64 else 45

    @property
    def duration(self):
        return timedelta(seconds=15 if self.source.level < 64 else 30)


class VenomousBiteAction(BardAction):
    @property
    def potency(self):
        return 100 if self.source.level < 64 else 120

    def perform(self):
        super().perform()

        self.schedule_aura_events(self.source.target, self.source.target_data.venomous_bite)
        self.schedule_dot(self.source.target_data.venomous_bite)


class SidewinderAction(BardAction):
    base_recast_time = timedelta(seconds=60)
    is_off_gcd = True

    @property
    def potency(self):
        if self.source.level < 64:
            return 100

        if self.source.target_data.windbite.up and self.source.target_data.venomous_bite.up:
            return 260

        if self.source.target_data.windbite.up or self.source.target_data.venomous_bite.up:
            return 175

        return 100


# from datetime import timedelta
# from math import floor
# from typing import Dict
#
# import numpy
#
# from simfantasy.enums import Attribute, Job, Race, RefreshBehavior, Slot
# from simfantasy.events import CastEvent, ConsumeAuraEvent, DotTickEvent
# from simfantasy.simulator import Actor, Aura, CastFactory, DotAura, Item, Simulation
#
#
# class Buffs:
#     def __init__(self):
#         self.raging_strikes = RagingStrikesBuff()
#         self.straight_shot = StraightShotBuff()
#         self.straighter_shot = StraighterShotBuff()
#
#
# class Actions:
#     def __init__(self, source: 'Bard'):
#         self.heavy_shot = CastFactory(source=source, cast_class=HeavyShotCast)
#         self.iron_jaws = CastFactory(source=source, cast_class=IronJawsCast)
#         self.raging_strikes = CastFactory(source=source, cast_class=RagingStrikesCast)
#         self.refulgent_arrow = CastFactory(source=source, cast_class=RefulgentArrowCast)
#         self.sidewinder = CastFactory(source=source, cast_class=SidewinderCast)
#         self.straight_shot = CastFactory(source=source, cast_class=StraightShotCast)
#
#         self.venomous_bite = CastFactory(source=source, cast_class=VenomousBiteCast)
#         self.windbite = CastFactory(source=source, cast_class=WindbiteCast)
#
#
# class TargetData:
#     def __init__(self, source: 'Bard'):
#         self.windbite = WindbiteDebuff(source=source)
#         self.venomous_bite = VenomousBiteDebuff(source=source)
#
#
# class Bard(Actor):
#     job = Job.BARD
#
#     def __init__(self,
#                  sim: Simulation,
#                  race: Race,
#                  level: int = None,
#                  target: Actor = None,
#                  name: str = None,
#                  equipment: Dict[Slot, Item] = None):
#         super().__init__(sim=sim, race=race, level=level, target=target, name=name, equipment=equipment)
#
#         self._target_data_class = TargetData
#         self.buffs = Buffs()
#         self.actions = Actions(source=self)
#
#     def calculate_base_stats(self) -> Dict[Attribute, int]:
#         base_stats = super().calculate_base_stats()
#
#         if self.level >= 20:
#             base_stats[Attribute.DEXTERITY] += 8
#
#         if self.level >= 40:
#             base_stats[Attribute.DEXTERITY] += 16
#
#         if self.level >= 60:
#             base_stats[Attribute.DEXTERITY] += 24
#
#         return base_stats
#
#     def decide(self):
#         if self.buffs.straighter_shot.up:
#             return self.actions.refulgent_arrow.cast()
#
#         if self.buffs.straight_shot.remains < timedelta(seconds=3):
#             return self.actions.straight_shot.cast()
#
#         if not self.actions.raging_strikes.on_cooldown:
#             return self.actions.raging_strikes.cast()
#
#         if self.target_data.windbite.up and self.target_data.venomous_bite.up:
#             if self.target_data.windbite.remains < timedelta(seconds=3) or \
#                     self.target_data.venomous_bite.remains < timedelta(seconds=3):
#                 return self.actions.iron_jaws.cast()
#
#             if not self.actions.sidewinder.on_cooldown:
#                 return self.actions.sidewinder.cast()
#
#         if not self.target_data.windbite.up:
#             return self.actions.windbite.cast()
#
#         if not self.target_data.venomous_bite.up:
#             return self.actions.venomous_bite.cast()
#
#         self.actions.heavy_shot.cast()
#
#
# class BardCastEvent(CastEvent):
#     source: Bard
#
#     affected_by = Attribute.ATTACK_POWER
#     hastened_by = Attribute.SKILL_SPEED
#
#     @property
#     def direct_damage(self) -> int:
#         direct_damage = super().direct_damage
#
#         if self.source.level >= 20:
#             direct_damage = floor(direct_damage * 1.1)
#
#         if self.source.level >= 40:
#             direct_damage = floor(direct_damage * 1.2)
#
#         if self.source.buffs.raging_strikes.up:
#             direct_damage = floor(direct_damage * 1.1)
#
#         return direct_damage
#
#
# class StraighterShotBuff(Aura):
#     duration = timedelta(seconds=10)
#     refresh_behavior = RefreshBehavior.RESET
#
#
# class StraightShotBuff(Aura):
#     duration = timedelta(seconds=30)
#     refresh_behavior = RefreshBehavior.RESET
#
#     def apply(self, target: Bard):
#         target.stats[Attribute.CRITICAL_HIT] *= 1.1
#
#     def expire(self, target: Bard):
#         target.stats[Attribute.CRITICAL_HIT] /= 1.1
#
#
# class StraightShotCast(BardCastEvent):
#     potency = 140
#
#     @property
#     def critical_hit_chance(self):
#         return 100.0 if self.source.buffs.straighter_shot.up else super().critical_hit_chance
#
#     def execute(self):
#         super().execute()
#
#         self.schedule_aura_events(aura=self.source.buffs.straight_shot, target=self.source)
#
#         if self.source.buffs.straighter_shot.up:
#             self.sim.schedule_in(ConsumeAuraEvent(sim=self.sim,
#                                                   target=self.source,
#                                                   aura=self.source.buffs.straighter_shot))
#
#
class WindbiteDebuff(Aura):
    def __init__(self, source: Bard):
        super().__init__()

        self.source = source

    @property
    def potency(self):
        return 50 if self.source.level < 64 else 55

    @property
    def duration(self):
        return timedelta(seconds=15 if self.source.level < 64 else 30)

#
#
# class WindbiteCast(BardCastEvent):
#     @property
#     def potency(self):
#         return 60 if self.source.level < 64 else 120
#
#     def execute(self):
#         super().execute()
#
#         self.schedule_aura_events(aura=self.source.target_data.windbite, target=self.source.target)
#         self.sim.schedule_in(DotTickEvent(sim=self.sim, aura=self.source.target_data.windbite))
#
#
#
#
# class VenomousBiteCast(BardCastEvent):
#     @property
#     def potency(self):
#         return 100 if self.source.level < 64 else 120
#
#     def execute(self):
#         super().execute()
#
#         self.schedule_aura_events(aura=self.source.target_data.venomous_bite, target=self.target)
#
#
# class HeavyShotCast(BardCastEvent):
#     potency = 150
#
#     def execute(self):
#         super().execute()
#
#         if numpy.random.uniform() <= 0.2:
#             self.schedule_aura_events(aura=self.source.buffs.straighter_shot, target=self.source)
#
#
# class RagingStrikesBuff(Aura):
#     duration = timedelta(seconds=20)
#
#
# class RagingStrikesCast(BardCastEvent):
#     is_off_gcd = True
#     recast_time = timedelta(seconds=80)
#
#     @property
#     def critical_hit_chance(self):
#         return 0.0
#
#     @property
#     def direct_hit_chance(self):
#         return 0.0
#
#     def execute(self):
#         super().execute()
#
#         self.schedule_aura_events(aura=self.source.buffs.raging_strikes, target=self.source)
#
#
# class RefulgentArrowCast(BardCastEvent):
#     potency = 300
#
#     def execute(self):
#         super().execute()
#
#         self.sim.schedule_in(ConsumeAuraEvent(sim=self.sim, target=self.source, aura=self.source.buffs.straighter_shot))
#
#
# class SidewinderCast(BardCastEvent):
#     recast_time = timedelta(seconds=60)
#
#     @property
#     def potency(self):
#         if self.source.level < 64:
#             return 100
#
#         if self.source.target_data.windbite.up and self.source.target_data.venomous_bite.up:
#             return 260
#
#         if self.source.target_data.windbite.up or self.source.target_data.venomous_bite.up:
#             return 175
#
#         return 100
#
#
# class IronJawsCast(BardCastEvent):
#     def execute(self):
#         super().execute()
#
#         if self.source.target_data.windbite.up:
#             self.schedule_aura_events(self.source.target_data.windbite)
#
#         if self.source.target_data.venomous_bite.up:
#             self.schedule_aura_events(self.source.target_data.venomous_bite)
