from datetime import timedelta
from typing import Dict, List, Optional, Tuple

import numpy

from simfantasy.action import Action, ShotAction
from simfantasy.actor import Actor, TargetData as BaseTargetData
from simfantasy.aura import Aura, TickingAura
from simfantasy.enum import Attribute, Job, Race, Resource, Role
from simfantasy.event import ApplyAuraEvent, ConsumeAuraEvent, DotTickEvent, \
    Event, ExpireAuraEvent, ResourceEvent
from simfantasy.simulator import Simulation


class Bard(Actor):
    job = Job.BARD
    role = Role.DPS

    def create_actions(self):
        super().create_actions()

        self.actions.shot = BardShotAction(self.sim, self)

        self.actions.armys_paeon = ArmysPaeonAction(self.sim, self)
        self.actions.barrage = BarrageAction(self.sim, self)
        self.actions.bloodletter = BloodletterAction(self.sim, self)
        self.actions.empyreal_arrow = EmpyrealArrowAction(self.sim, self)
        self.actions.foe_requiem = FoeRequiemAction(self.sim, self)
        self.actions.heavy_shot = HeavyShotAction(self.sim, self)
        self.actions.iron_jaws = IronJawsAction(self.sim, self)
        self.actions.mages_ballad = MagesBalladAction(self.sim, self)
        self.actions.miserys_end = MiserysEndAction(self.sim, self)
        self.actions.pitch_perfect = PitchPerfectAction(self.sim, self)
        self.actions.raging_strikes = RagingStrikesAction(self.sim, self)
        self.actions.rain_of_death = RainOfDeathAction(self.sim, self)
        self.actions.refulgent_arrow = RefulgentArrowAction(self.sim, self)
        self.actions.sidewinder = SidewinderAction(self.sim, self)
        self.actions.straight_shot = StraightShotAction(self.sim, self)
        self.actions.venomous_bite = VenomousBiteAction(self.sim, self)
        self.actions.wanderers_minuet = WanderersMinuetAction(self.sim, self)
        self.actions.windbite = WindbiteAction(self.sim, self)

    def create_buffs(self):
        super().create_buffs()

        self.buffs.armys_paeon = ArmysPaeonBuff(self.sim, self)
        self.buffs.barrage = BarrageBuff(self.sim, self)
        self.buffs.foe_requiem = FoeRequiemBuff(self.sim, self)
        self.buffs.mages_ballad = MagesBalladBuff(self.sim, self)
        self.buffs.raging_strikes = RagingStrikesBuff(self.sim, self)
        self.buffs.straight_shot = StraightShotBuff(self.sim, self)
        self.buffs.straighter_shot = StraighterShotBuff(self.sim, self)
        self.buffs.wanderers_minuet = WanderersMinuetBuff(self.sim, self)

    def create_target_data(self):
        super().create_target_data()

        self.target_data.foe_requiem = FoeRequiemDebuff(self.sim, self)
        self.target_data.venomous_bite = VenomousBiteDebuff(self.sim, self)
        self.target_data.windbite = WindbiteDebuff(self.sim, self)

    def calculate_resources(self) -> Dict[Resource, Tuple[int, int]]:
        resources = super().calculate_resources()

        resources[Resource.REPERTOIRE] = (0, 0)

        return resources

    def decide(self) -> None:
        yield self.actions.shot

        current_mp, max_mp = self.resources[Resource.MP]
        current_rep, max_rep = self.resources[Resource.REPERTOIRE]

        yield self.actions.foe_requiem, lambda: not self.buffs.foe_requiem.up and current_mp == max_mp

        yield self.actions.windbite, lambda: not self.target_data.windbite.up
        yield self.actions.venomous_bite, lambda: not self.target_data.venomous_bite.up

        yield self.actions.iron_jaws, lambda: (
                self.actions.raging_strikes.cooldown_remains <= timedelta(seconds=5) and
                self.target_data.windbite.up and self.target_data.venomous_bite.up and (
                        self.target_data.windbite.remains <=
                        self.target_data.venomous_bite.remains <=
                        self.buffs.raging_strikes.duration
                )
        )

        yield self.actions.raging_strikes, lambda: not self.buffs.raging_strikes.up
        yield self.actions.barrage, lambda: (
                self.buffs.raging_strikes.up and
                (self.buffs.straighter_shot.up or self.buffs.raging_strikes.remains < timedelta(
                    seconds=3))
        )

        yield self.actions.straight_shot, lambda: self.buffs.straight_shot.remains < timedelta(
            seconds=3)

        yield self.actions.pitch_perfect, lambda: (
                current_rep == max_rep or self.buffs.wanderers_minuet.remains < timedelta(seconds=3)
        )

        yield self.actions.wanderers_minuet, lambda: not self.song
        yield self.actions.mages_ballad, lambda: not self.song
        yield self.actions.armys_paeon, lambda: not self.song

        yield self.actions.iron_jaws, lambda: (
                self.target_data.windbite.up and
                self.target_data.venomous_bite.up and (
                        self.target_data.windbite.remains <= timedelta(seconds=3) or
                        self.target_data.venomous_bite.remains <= timedelta(seconds=3)
                )
        )

        yield self.actions.barrage, lambda: self.buffs.straighter_shot.up and self.buffs.raging_strikes.up
        yield self.actions.refulgent_arrow
        yield self.actions.empyreal_arrow, lambda: (
                self.song is not self.buffs.wanderers_minuet or
                current_rep < max_rep or
                self.buffs.barrage.up
        )

        yield self.actions.empyreal_arrow, lambda: (
                self.actions.raging_strikes.cooldown_remains > self.actions.empyreal_arrow.recast_time
        )

        yield self.actions.bloodletter
        yield self.actions.miserys_end

        yield self.actions.sidewinder, lambda: self.target_data.windbite.up and self.target_data.venomous_bite.up

        yield self.actions.heavy_shot

        yield None

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
            self.schedule_damage_event()
            self.schedule_damage_event()
            self.sim.schedule(ConsumeAuraEvent(self.sim, self.source, self.source.buffs.barrage))

    def schedule_dot(self, dot: TickingAura):
        super().schedule_dot(dot)

        # TODO Find a better way to do this, or hook into the DotTickEvent.
        self.sim.unschedule(dot.tick_event)
        dot.tick_event = BardDotTickEvent(self.sim, self.source, self.source.target, self,
                                          dot.potency, dot, None,
                                          self._trait_multipliers, self._buff_multipliers)
        self.sim.schedule(dot.tick_event, timedelta(seconds=3))

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

        if self.source.target_data.foe_requiem.up:
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


class TargetData(BaseTargetData):
    def __init__(self, sim, source):
        self.foe_requiem = FoeRequiemDebuff()
        self.venomous_bite = VenomousBiteDebuff(source)
        self.windbite = WindbiteDebuff(source)


class StraighterShotBuff(Aura):
    duration = timedelta(seconds=10)
    name = 'Straighter Shot'


class HeavyShotAction(BardAction):
    affected_by_barrage = True
    cost = (Resource.TP, 50)
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
    cost = (Resource.TP, 50)
    name = 'Straight Shot'
    potency = 140

    @property
    def guarantee_crit(self):
        return self.source.buffs.straighter_shot.up

    def perform(self):
        super().perform()

        if self.source.buffs.straighter_shot.up:
            self.sim.schedule(
                ConsumeAuraEvent(self.sim, self.source, self.source.buffs.straighter_shot))

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
    cost = (Resource.TP, 60)

    @property
    def name(self):
        return '%s Bite' % ('Venomous' if self.source.level < 64 else 'Caustic')

    @property
    def potency(self):
        return 100 if self.source.level < 64 else 120

    def perform(self):
        super().perform()

        self.schedule_dot(self.source.target_data.venomous_bite)


# FIXME Animation time likely longer than default.
class MiserysEndAction(BardAction):
    base_recast_time = timedelta(seconds=12)
    is_off_gcd = True
    name = "Misery's End"
    potency = 190

    @property
    def ready(self):
        return super().ready and self.sim.in_execute


class BloodletterAction(BardAction):
    base_recast_time = timedelta(seconds=15)
    is_off_gcd = True
    name = 'Bloodletter'
    potency = 130

    def __init__(self, sim: Simulation, source: Actor):
        super().__init__(sim, source)

    @property
    def shares_recast_with(self):
        return self.source.actions.rain_of_death


class WindbiteDebuff(TickingAura):
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
    cost = (Resource.TP, 60)

    @property
    def name(self):
        return '%sbite' % ('Wind' if self.source.level < 64 else 'Storm')

    @property
    def potency(self):
        return 60 if self.source.level < 64 else 120

    def perform(self):
        super().perform()

        self.schedule_dot(self.source.target_data.windbite)


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
        super().perform()

        if self.source.song is not None:
            self.source.song.expire(self.source)
            self.sim.unschedule(self.source.song.expiration_event)
            self.source.song.expiration_event = None


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
    cost = (Resource.TP, 50)
    name = 'Iron Jaws'
    potency = 100

    def perform(self):
        super().perform()

        if self.source.target_data.windbite.up:
            self.schedule_dot(self.source.target_data.windbite)

        if self.source.target_data.venomous_bite.up:
            self.schedule_dot(self.source.target_data.venomous_bite)


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

    @property
    def ready(self):
        return super().ready and self.source.buffs.straighter_shot.up

    def perform(self):
        super().perform()

        if self.source.buffs.straighter_shot.up:
            self.sim.schedule(
                ConsumeAuraEvent(self.sim, self.source, self.source.buffs.straighter_shot))


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
        super().__init__(sim, target, Resource.MP, -1680)

    def execute(self) -> None:
        super().execute()

        current_mp, max_mp = self.target.resources[Resource.MP]

        if current_mp > 0:
            self.sim.schedule(FoeTickEvent(self.sim, self.target), timedelta(seconds=3))
        else:
            original_target = self.target.target

            for actor in self.sim.actors:
                if actor.race is Race.ENEMY:
                    self.target.target = actor

                    self.sim.schedule(
                        ExpireAuraEvent(self.sim, actor, self.target.target_data.foe_requiem),
                        timedelta(seconds=6))

            self.target.target = original_target

            self.sim.schedule(ExpireAuraEvent(self.sim, self.target, self.target.buffs.foe_requiem))


class FoeRequiemDebuff(Aura):
    name = "Foe's Requiem"


class FoeRequiemBuff(Aura):
    name = "Foe's Requiem"

    @property
    def up(self):
        return self in self.source.auras


class FoeRequiemAction(BardAction):
    base_cast_time = timedelta(seconds=1.5)
    hastened_by = None
    name = "Foe's Requiem"

    def perform(self):
        super().perform()

        self.sim.schedule(ApplyAuraEvent(self.sim, self.source, self.source.buffs.foe_requiem),
                          self.cast_time)

        delta = self.cast_time + timedelta(seconds=3)

        original_target = self.source.target

        for actor in self.sim.actors:
            if actor.race is Race.ENEMY:
                self.source.target = actor
                self.sim.schedule(
                    ApplyAuraEvent(self.sim, actor, self.source.target_data.foe_requiem), delta)

        self.source.target = original_target

        self.sim.schedule(FoeTickEvent(self.sim, self.source), delta)


class ArmysPaeonBuff(BardSongBuff):
    name = "Army's Paeon"

    def apply(self, target):
        super().apply(target)

        target.resources[Resource.REPERTOIRE] = (0, 4)

        target.actions.invalidate_speed_caches()

    def expire(self, target: Actor):
        super().expire(target)

        target.actions.invalidate_speed_caches()


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

    @property
    def ready(self):
        return super().ready and self.source.song is self.source.buffs.wanderers_minuet

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
    cost = (Resource.TP, 50)
    is_off_gcd = True
    name = 'Empyreal Arrow'
    potency = 230

    @property
    def recast_time(self):
        return self.speed(self.base_recast_time)

    def perform(self):
        super().perform()

        if self.source.song is not None:
            self.sim.schedule(ResourceEvent(self.sim, self.source, Resource.REPERTOIRE, 1))
