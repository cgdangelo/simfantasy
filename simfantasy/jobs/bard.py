from datetime import timedelta
from typing import Dict, List, Optional, Tuple, Union

import numpy

from simfantasy.enums import Attribute, Job, Race, Resource, Role, Slot
from simfantasy.events import Action, ApplyAuraEvent, ConsumeAuraEvent, DamageEvent, DotTickEvent, \
    Event, ExpireAuraEvent, ResourceEvent, ShotAction
from simfantasy.simulator import Actor, Aura, Item, Simulation, TickingAura, Weapon


class Bard(Actor):
    job = Job.BARD
    role = Role.DPS

    def __init__(self, sim: Simulation, race: Race, level: int = None, target: Actor = None, name: str = None,
                 gear: Tuple[Tuple[Slot, Union[Item, Weapon]], ...] = None):
        super().__init__(sim, race, level, target, name, gear)

        self._target_data_class = TargetData
        self.actions = None
        self.buffs = None

    def arise(self):
        super().arise()

        self.actions = Actions(self.sim, self)
        self.buffs = Buffs(self.sim, self)

    def calculate_resources(self) -> Dict[Resource, Tuple[int, int]]:
        resources = super().calculate_resources()

        resources[Resource.REPERTOIRE] = (0, 0)

        return resources

    def decide(self) -> None:
        if not self.actions.shot.on_cooldown:
            return self.actions.shot.perform()

        current_mp, max_mp = self.resources[Resource.MANA]
        current_rep, max_rep = self.resources[Resource.REPERTOIRE]

        if self.animation_up and self.gcd_up and not self.buffs.foe_requiem.up and current_mp == max_mp:
            return self.actions.foe_requiem.perform()

        if self.animation_up and self.gcd_up and self.actions.raging_strikes.on_cooldown \
                and self.actions.raging_strikes.can_recast_at - self.sim.current_time < timedelta(seconds=5):
            if self.target_data.windbite.up and self.target_data.venomous_bite.up:
                if self.target_data.windbite.remains <= self.buffs.raging_strikes.duration \
                        or self.target_data.venomous_bite.remains <= self.buffs.raging_strikes.duration:
                    return self.actions.iron_jaws.perform()

        if self.animation_up and not self.buffs.raging_strikes.up and not self.actions.raging_strikes.on_cooldown:
            return self.actions.raging_strikes.perform()

        if self.animation_up and self.buffs.raging_strikes.up \
                and self.buffs.raging_strikes.remains < timedelta(seconds=3) \
                and not self.actions.barrage.on_cooldown \
                and not self.actions.empyreal_arrow.on_cooldown:
            return self.actions.barrage.perform()

        if self.animation_up and self.gcd_up and self.buffs.straight_shot.remains < timedelta(seconds=3):
            return self.actions.straight_shot.perform()

        if self.animation_up and not self.actions.wanderers_minuet.on_cooldown:
            return self.actions.wanderers_minuet.perform()

        if self.animation_up and self.song is self.buffs.wanderers_minuet and current_rep > 0 \
                and (current_rep == max_rep or self.buffs.wanderers_minuet.remains < timedelta(seconds=3)):
            return self.actions.pitch_perfect.perform()

        if self.animation_up and not self.song:
            if not self.actions.mages_ballad.on_cooldown:
                return self.actions.mages_ballad.perform()
            elif not self.actions.armys_paeon.on_cooldown:
                return self.actions.armys_paeon.perform()

        if self.animation_up and self.gcd_up and self.target_data.windbite.up and self.target_data.venomous_bite.up:
            if self.target_data.windbite.remains <= timedelta(seconds=3) \
                    or self.target_data.venomous_bite.remains <= timedelta(seconds=3):
                return self.actions.iron_jaws.perform()

        if self.animation_up and self.gcd_up and self.buffs.straighter_shot.up and self.buffs.raging_strikes.up:
            if not self.actions.barrage.on_cooldown:
                return self.actions.barrage.perform()

            return self.actions.refulgent_arrow.perform()

        if self.animation_up and not self.actions.empyreal_arrow.on_cooldown:
            if self.song is not self.buffs.wanderers_minuet or current_rep < max_rep or self.buffs.barrage.up:
                return self.actions.empyreal_arrow.perform()

            if self.actions.raging_strikes.can_recast_at - self.sim.current_time > self.actions.empyreal_arrow.recast_time:
                return self.actions.empyreal_arrow.perform()

        if self.animation_up and self.gcd_up and not self.target_data.windbite.up:
            return self.actions.windbite.perform()

        if self.animation_up and self.gcd_up and not self.target_data.venomous_bite.up:
            return self.actions.venomous_bite.perform()

        if self.animation_up and not self.actions.bloodletter.on_cooldown:
            return self.actions.bloodletter.perform()

        if self.animation_up and self.sim.in_execute and not self.actions.miserys_end.on_cooldown:
            return self.actions.miserys_end.perform()

        if self.animation_up and not self.actions.sidewinder.on_cooldown:
            return self.actions.sidewinder.perform()

        if self.animation_up and self.gcd_up:
            self.actions.heavy_shot.perform()

    @property
    def song(self) -> Optional['BardSongBuff']:
        if self.buffs.mages_ballad.up:
            return self.buffs.mages_ballad
        elif self.buffs.armys_paeon.up:
            return self.buffs.armys_paeon
        elif self.buffs.wanderers_minuet.up:
            return self.buffs.wanderers_minuet

        return None


class BardAction(Action):
    affected_by_barrage: bool = False
    hastened_by = Attribute.SKILL_SPEED
    powered_by = Attribute.ATTACK_POWER
    source: Bard

    def perform(self) -> None:
        super().perform()

        if self.source.buffs.barrage.up and self.affected_by_barrage:
            self.sim.schedule(
                DamageEvent(self.sim, self.source, self.source.target, self, self.potency, self._trait_multipliers,
                            self._buff_multipliers, self.guarantee_crit), self.cast_time)

            self.sim.schedule(
                DamageEvent(self.sim, self.source, self.source.target, self, self.potency, self._trait_multipliers,
                            self._buff_multipliers, self.guarantee_crit), self.cast_time)

            self.sim.schedule(ConsumeAuraEvent(self.sim, self.source, self.source.buffs.barrage))

    @property
    def type_ii_speed_mod(self) -> int:
        if self.source.buffs.armys_paeon.up:
            current, maximum = self.source.resources[Resource.REPERTOIRE]
            return current * 4

        return 0

    @property
    def _trait_multipliers(self) -> List[float]:
        _trait_multipliers = super()._trait_multipliers

        if self.source.level >= 20:
            _trait_multipliers += [1.1]

        if self.source.level >= 40:
            _trait_multipliers += [1.2]

        return _trait_multipliers

    @property
    def _buff_multipliers(self) -> List[float]:
        _buff_multipliers = super()._buff_multipliers

        # TODO Make this possible.
        # if self.source.target_data.foe_requiem.up:
        #     yield 1.1

        if self.source.target_data.foe_requiem in self.source.target.auras:
            _buff_multipliers += [1.1]

        if self.source.buffs.raging_strikes.up:
            _buff_multipliers += [1.1]

        return _buff_multipliers


class RepertoireEvent(Event):
    def __init__(self, sim: Simulation, bard: Bard):
        super().__init__(sim)

        self.bard = bard

    def execute(self) -> None:
        super().execute()

        if self.bard.buffs.mages_ballad.up:
            self.bard.actions.bloodletter.set_recast_at(self.bard.actions.bloodletter.animation)
        elif self.bard.song is not None:
            self.sim.schedule(ResourceEvent(self.sim, self.bard, Resource.REPERTOIRE, 1))

    def __str__(self):
        return '<{cls} song={song}>'.format(
            cls=self.__class__.__name__,
            song=self.bard.song.name,
        )


class BardDotTickEvent(DotTickEvent):
    def execute(self) -> None:
        super().execute()

        if self.source.song is not None and self.is_critical_hit:
            self.sim.schedule(RepertoireEvent(self.sim, self.source))


class BardShotAction(BardAction, ShotAction):
    pass


class Actions:
    def __init__(self, sim: Simulation, source: Bard):
        self.shot = BardShotAction(sim, source)

        self.armys_paeon = ArmysPaeonAction(sim, source)
        self.barrage = BarrageAction(sim, source)
        self.bloodletter = BloodletterAction(sim, source)
        self.empyreal_arrow = EmpyrealArrowAction(sim, source)
        self.foe_requiem = FoeRequiemAction(sim, source)
        self.heavy_shot = HeavyShotAction(sim, source)
        self.iron_jaws = IronJawsAction(sim, source)
        self.mages_ballad = MagesBalladAction(sim, source)
        self.miserys_end = MiserysEndAction(sim, source)
        self.pitch_perfect = PitchPerfectAction(sim, source)
        self.raging_strikes = RagingStrikesAction(sim, source)
        self.rain_of_death = RainOfDeathAction(sim, source)
        self.refulgent_arrow = RefulgentArrowAction(sim, source)
        self.sidewinder = SidewinderAction(sim, source)
        self.straight_shot = StraightShotAction(sim, source)
        self.venomous_bite = VenomousBiteAction(sim, source)
        self.wanderers_minuet = WanderersMinuetAction(sim, source)
        self.windbite = WindbiteAction(sim, source)


class Buffs:
    def __init__(self, sim: Simulation, source: Bard):
        self.armys_paeon = ArmysPaeonBuff()
        self.barrage = BarrageBuff()
        self.foe_requiem = FoeRequiemBuff(source)
        self.mages_ballad = MagesBalladBuff()
        self.raging_strikes = RagingStrikesBuff()
        self.straight_shot = StraightShotBuff()
        self.straighter_shot = StraighterShotBuff()
        self.wanderers_minuet = WanderersMinuetBuff()


class TargetData:
    def __init__(self, source: Bard):
        self.foe_requiem = FoeRequiemDebuff()
        self.venomous_bite = VenomousBiteDebuff(source)
        self.windbite = WindbiteDebuff(source)


class StraighterShotBuff(Aura):
    duration = timedelta(seconds=10)
    name = 'Straighter Shot'


class HeavyShotAction(BardAction):
    affected_by_barrage = True
    name = 'Heavy Shot'
    potency = 150

    def perform(self):
        super().perform()

        if numpy.random.uniform() < 0.2:
            self.schedule_aura_events(self.source, self.source.buffs.straighter_shot)


class StraightShotBuff(Aura):
    duration = timedelta(seconds=30)
    name = 'Straight Shot'

    def apply(self, target):
        super().apply(target)

        target.stats[Attribute.CRITICAL_HIT] *= 1.1

    def expire(self, target):
        super().expire(target)

        target.stats[Attribute.CRITICAL_HIT] /= 1.1


class StraightShotAction(BardAction):
    affected_by_barrage = True
    name = 'Straight Shot'
    potency = 140

    @property
    def guarantee_crit(self):
        return self.source.buffs.straighter_shot.up

    def perform(self):
        super().perform()

        if self.source.buffs.straighter_shot.up:
            self.sim.schedule(ConsumeAuraEvent(self.sim, self.source, self.source.buffs.straighter_shot))

        self.schedule_aura_events(self.source, self.source.buffs.straight_shot)


class RagingStrikesBuff(Aura):
    duration = timedelta(seconds=20)
    name = 'Raging Strikes'


class RagingStrikesAction(BardAction):
    base_recast_time = timedelta(seconds=90)
    is_off_gcd = True
    name = 'Raging Strikes'

    def perform(self):
        super().perform()

        self.schedule_aura_events(self.source, self.source.buffs.raging_strikes)


class VenomousBiteDebuff(TickingAura):
    def __init__(self, source: Bard):
        super().__init__()

        self.source = source

    @property
    def name(self):
        return '%s Bite' % ('Venomous' if self.source.level < 64 else 'Caustic')

    @property
    def potency(self):
        return 40 if self.source.level < 64 else 45

    @property
    def duration(self):
        return timedelta(seconds=15 if self.source.level < 64 else 30)


class VenomousBiteAction(BardAction):
    affected_by_barrage = True

    @property
    def name(self):
        return '%s Bite' % ('Venomous' if self.source.level < 64 else 'Caustic')

    @property
    def potency(self):
        return 100 if self.source.level < 64 else 120

    def perform(self):
        super().perform()

        dot = self.source.target_data.venomous_bite

        self.schedule_aura_events(self.source.target, dot)

        if dot.tick_event is not None:
            self.sim.unschedule(dot.tick_event)

        tick_event = BardDotTickEvent(self.sim, self.source, self.source.target, self, dot.potency, dot)

        dot.tick_event = tick_event

        self.sim.schedule(dot.tick_event, timedelta(seconds=3))


# FIXME Animation time likely longer than default.
class MiserysEndAction(BardAction):
    base_recast_time = timedelta(seconds=12)
    is_off_gcd = True
    name = "Misery's End"
    potency = 190


class BloodletterAction(BardAction):
    base_recast_time = timedelta(seconds=8)
    is_off_gcd = True
    name = 'Bloodletter'
    potency = 130

    def __init__(self, sim: Simulation, source: Actor):
        super().__init__(sim, source)

    @property
    def shares_recast_with(self):
        return self.source.actions.rain_of_death


class WindbiteDebuff(TickingAura):
    def __init__(self, source: Bard):
        super().__init__()

        self.source = source

    @property
    def name(self):
        return '%sbite' % ('Wind' if self.source.level < 64 else 'Storm')

    @property
    def potency(self):
        return 50 if self.source.level < 64 else 55

    @property
    def duration(self):
        return timedelta(seconds=15 if self.source.level < 64 else 30)


class WindbiteAction(BardAction):
    affected_by_barrage = True

    @property
    def name(self):
        return '%sbite' % ('Wind' if self.source.level < 64 else 'Storm')

    @property
    def potency(self):
        return 60 if self.source.level < 64 else 120

    def perform(self):
        super().perform()

        dot = self.source.target_data.windbite

        self.schedule_aura_events(self.source.target, dot)

        if dot.tick_event is not None:
            self.sim.unschedule(dot.tick_event)

        tick_event = BardDotTickEvent(
            sim=self.sim,
            source=self.source,
            target=self.source.target,
            action=self,
            potency=dot.potency,
            aura=dot,
        )

        dot.tick_event = tick_event

        self.sim.schedule(dot.tick_event, timedelta(seconds=3))


# TODO Implement crit buff for allies.
class BardSongBuff(Aura):
    duration = timedelta(seconds=30)

    def expire(self, target: Actor):
        super().expire(target)

        target.resources[Resource.REPERTOIRE] = (0, 0)


class BardSongAction(BardAction):
    base_recast_time = timedelta(seconds=80)
    is_off_gcd = True
    potency = 100

    def perform(self):
        if self.source.song is not None:
            self.sim.unschedule(self.source.song.expiration_event)
            self.sim.schedule(self.source.song.expiration_event)

        super().perform()


class MagesBalladBuff(BardSongBuff):
    name = "Mage's Ballad"


class MagesBalladAction(BardSongAction):
    name = "Mage's Ballad"

    def perform(self):
        super().perform()

        self.schedule_aura_events(self.source, self.source.buffs.mages_ballad)


class RainOfDeathAction(BardAction):
    is_off_gcd = True
    name = 'Rain of Death'
    potency = 100

    @property
    def shares_recast_with(self):
        return self.source.actions.bloodletter


class IronJawsAction(BardAction):
    affected_by_barrage = True
    name = 'Iron Jaws'
    potency = 100

    def perform(self):
        super().perform()

        if self.source.target_data.windbite.up:
            self.schedule_aura_events(self.source.target, self.source.target_data.windbite)

        if self.source.target_data.venomous_bite.up:
            self.schedule_aura_events(self.source.target, self.source.target_data.venomous_bite)


class SidewinderAction(BardAction):
    base_recast_time = timedelta(seconds=60)
    name = 'Sidewinder'
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


class RefulgentArrowAction(BardAction):
    affected_by_barrage = True
    name = 'Refulgent Arrow'
    potency = 300

    def perform(self):
        super().perform()

        if self.source.buffs.straighter_shot.up:
            self.sim.schedule(ConsumeAuraEvent(self.sim, self.source, self.source.buffs.straighter_shot))


class BarrageBuff(Aura):
    duration = timedelta(seconds=10)
    name = 'Barrage'


class BarrageAction(BardAction):
    base_recast_time = timedelta(seconds=80)
    is_off_gcd = True
    name = 'Barrage'

    def perform(self):
        super().perform()

        self.schedule_aura_events(self.source, self.source.buffs.barrage)


class FoeTickEvent(ResourceEvent):
    def __init__(self, sim: Simulation, target: Actor):
        super().__init__(sim, target, Resource.MANA, -1680)

    def execute(self) -> None:
        super().execute()

        current_mp, max_mp = self.target.resources[Resource.MANA]

        if current_mp > 0:
            self.sim.schedule(FoeTickEvent(self.sim, self.target), timedelta(seconds=3))
        else:
            original_target = self.target.target

            for actor in self.sim.actors:
                if actor.race is Race.ENEMY:
                    self.target.target = actor

                    self.sim.schedule(ExpireAuraEvent(self.sim, actor, self.target.target_data.foe_requiem),
                                      timedelta(seconds=6))

            self.target.target = original_target

            self.sim.schedule(ExpireAuraEvent(self.sim, self.target, self.target.buffs.foe_requiem))


class FoeRequiemDebuff(Aura):
    name = "Foe's Requiem"


class FoeRequiemBuff(Aura):
    name = "Foe's Requiem"

    def __init__(self, source: Actor) -> None:
        super().__init__()

        self.source = source

    @property
    def up(self):
        return self in self.source.auras


class FoeRequiemAction(BardAction):
    base_cast_time = timedelta(seconds=1.5)
    name = "Foe's Requiem"

    def perform(self):
        super().perform()

        self.sim.schedule(ApplyAuraEvent(self.sim, self.source, self.source.buffs.foe_requiem), self.cast_time)

        delta = self.cast_time + timedelta(seconds=3)

        original_target = self.source.target

        for actor in self.sim.actors:
            if actor.race is Race.ENEMY:
                self.source.target = actor
                self.sim.schedule(ApplyAuraEvent(self.sim, actor, self.source.target_data.foe_requiem), delta)

        self.source.target = original_target

        self.sim.schedule(FoeTickEvent(self.sim, self.source), delta)


class ArmysPaeonBuff(BardSongBuff):
    name = "Army's Paeon"

    def apply(self, target):
        super().apply(target)

        target.resources[Resource.REPERTOIRE] = (0, 4)


class ArmysPaeonAction(BardSongAction):
    name = "Army's Paeon"

    def perform(self):
        super().perform()

        self.schedule_aura_events(self.source, self.source.buffs.armys_paeon)


class WanderersMinuetBuff(BardSongBuff):
    name = "The Wanderer's Minuet"

    def apply(self, target):
        super().apply(target)

        target.resources[Resource.REPERTOIRE] = (0, 3)


class WanderersMinuetAction(BardSongAction):
    name = "The Wanderer's Minuet"

    def perform(self):
        super().perform()

        self.schedule_aura_events(self.source, self.source.buffs.wanderers_minuet)


class PitchPerfectAction(BardAction):
    affected_by_barrage = True
    base_recast_time = timedelta(seconds=3)
    is_off_gcd = True
    name = 'Pitch Perfect'

    def perform(self):
        super().perform()

        self.sim.schedule(ResourceEvent(self.sim, self.source, Resource.REPERTOIRE, -3))

    @property
    def potency(self):
        repertoire = self.source.resources[Resource.REPERTOIRE]

        if repertoire == 1:
            return 100
        elif repertoire == 2:
            return 240
        else:
            return 420

    def __str__(self):
        return '<{cls} repertoire={repertoire}>'.format(
            cls=self.__class__.__name__,
            repertoire=self.source.resources[Resource.REPERTOIRE],
        )


class EmpyrealArrowAction(BardAction):
    affected_by_barrage = True
    base_recast_time = timedelta(seconds=15)
    name = 'Empyreal Arrow'
    is_off_gcd = True
    potency = 230

    def perform(self):
        super().perform()

        if self.source.song is not None:
            self.sim.schedule(ResourceEvent(self.sim, self.source, Resource.REPERTOIRE, 1))
