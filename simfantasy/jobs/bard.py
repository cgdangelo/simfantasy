from datetime import timedelta
from typing import Dict, List

import numpy

from simfantasy.enums import Attribute, Job, Race, Resource, Role, Slot
from simfantasy.events import Action, ApplyAuraEvent, ConsumeAuraEvent, DamageEvent, DotTickEvent, Event, \
    ExpireAuraEvent, ResourceEvent
from simfantasy.simulator import Actor, Aura, Item, Simulation, TickingAura


class Bard(Actor):
    job = Job.BARD
    role = Role.DPS

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
        self.buffs = Buffs(sim, self)

    def decide(self):
        current_mp, max_mp = self.resources[Resource.MANA]

        if not self.buffs.foe_requiem.up and current_mp == max_mp:
            return self.actions.foe_requiem.perform()

        if not self.buffs.raging_strikes.up and not self.actions.raging_strikes.on_cooldown:
            return self.actions.raging_strikes.perform()

        if self.buffs.straight_shot.remains < timedelta(seconds=3):
            return self.actions.straight_shot.perform()

        if not self.actions.mages_ballad.on_cooldown:
            return self.actions.mages_ballad.perform()

        if self.target_data.windbite.up and self.target_data.venomous_bite.up:
            if self.target_data.windbite.remains <= timedelta(seconds=3) or \
                    self.target_data.venomous_bite.remains <= timedelta(seconds=3):
                return self.actions.iron_jaws.perform()

        if self.buffs.straighter_shot.up:
            if not self.actions.barrage.on_cooldown:
                return self.actions.barrage.perform()

            return self.actions.refulgent_arrow.perform()

        if not self.target_data.windbite.up:
            return self.actions.windbite.perform()

        if not self.target_data.venomous_bite.up:
            return self.actions.venomous_bite.perform()

        if not self.actions.bloodletter.on_cooldown:
            return self.actions.bloodletter.perform()

        if self.sim.in_execute and not self.actions.miserys_end.on_cooldown:
            return self.actions.miserys_end.perform()

        if not self.actions.sidewinder.on_cooldown:
            return self.actions.sidewinder.perform()

        self.actions.heavy_shot.perform()

    @property
    def song(self):
        if self.buffs.mages_ballad.up:
            return self.buffs.mages_ballad

        return None


class BardAction(Action):
    affected_by_barrage: bool = False
    hastened_by = Attribute.SKILL_SPEED
    powered_by = Attribute.ATTACK_POWER
    source: Bard

    def perform(self):
        super().perform()

        if self.source.buffs.barrage.up and self.affected_by_barrage:
            self.sim.schedule(
                DamageEvent(sim=self.sim, source=self.source, target=self.source.target, action=self,
                            potency=self.potency, trait_multipliers=self._trait_multipliers,
                            buff_multipliers=self._buff_multipliers, guarantee_crit=self.guarantee_crit),
                delta=self.cast_time
            )

            self.sim.schedule(
                DamageEvent(sim=self.sim, source=self.source, target=self.source.target, action=self,
                            potency=self.potency, trait_multipliers=self._trait_multipliers,
                            buff_multipliers=self._buff_multipliers, guarantee_crit=self.guarantee_crit),
                delta=self.cast_time
            )

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

        # TODO Make this possible.
        # if self.source.target_data.foe_requiem.up:
        #     yield 1.1

        if self.source.target_data.foe_requiem in self.source.target.auras:
            yield 1.1

        if self.source.buffs.raging_strikes.up:
            yield 1.1


class RepertoireEvent(Event):
    def __init__(self, sim: Simulation, bard: Bard):
        super().__init__(sim)

        self.bard = bard

    def execute(self) -> None:
        super().execute()

        if self.bard.buffs.mages_ballad.up:
            self.bard.actions.bloodletter.can_recast_at = self.sim.current_time + self.bard.actions.bloodletter.animation
            self.bard.actions.rain_of_death.can_recast_at = self.sim.current_time + self.bard.actions.rain_of_death.animation

    def __str__(self):
        return '<{cls} song={song}>'.format(
            cls=self.__class__.__name__,
            song=self.bard.song.__class__.__name__,
        )


class BardDotTickEvent(DotTickEvent):
    source: Bard

    def execute(self) -> None:
        super().execute()

        if self.source.song is not None and self.is_critical_hit:
            self.sim.schedule(RepertoireEvent(sim=self.sim, bard=self.source))


class Actions:
    def __init__(self, sim: Simulation, source: Bard):
        self.barrage = BarrageAction(sim, source)
        self.bloodletter = BloodletterAction(sim, source)
        self.foe_requiem = FoeRequiemAction(sim, source)
        self.heavy_shot = HeavyShotAction(sim, source)
        self.iron_jaws = IronJawsAction(sim, source)
        self.mages_ballad = MagesBalladAction(sim, source)
        self.miserys_end = MiserysEndAction(sim, source)
        self.raging_strikes = RagingStrikesAction(sim, source)
        self.rain_of_death = RainOfDeathAction(sim, source)
        self.refulgent_arrow = RefulgentArrowAction(sim, source)
        self.sidewinder = SidewinderAction(sim, source)
        self.straight_shot = StraightShotAction(sim, source)
        self.venomous_bite = VenomousBiteAction(sim, source)
        self.windbite = WindbiteAction(sim, source)


class Buffs:
    def __init__(self, sim: Simulation, source: Bard):
        self.barrage = BarrageBuff()
        self.foe_requiem = FoeRequiemBuff(source)
        self.mages_ballad = MagesBalladBuff()
        self.raging_strikes = RagingStrikesBuff()
        self.straight_shot = StraightShotBuff()
        self.straighter_shot = StraighterShotBuff()


class TargetData:
    def __init__(self, source: Bard):
        self.foe_requiem = FoeRequiemDebuff()
        self.venomous_bite = VenomousBiteDebuff(source=source)
        self.windbite = WindbiteDebuff(source=source)


class StraighterShotBuff(Aura):
    duration = timedelta(seconds=10)


class HeavyShotAction(BardAction):
    affected_by_barrage = True
    potency = 150

    def perform(self):
        super().perform()

        if numpy.random.uniform() < 0.2:
            self.schedule_aura_events(self.source, self.source.buffs.straighter_shot)


class StraightShotBuff(Aura):
    duration = timedelta(seconds=30)

    def apply(self, target):
        super().apply(target)

        target.stats[Attribute.CRITICAL_HIT] *= 1.1

    def expire(self, target):
        super().expire(target)

        target.stats[Attribute.CRITICAL_HIT] /= 1.1


class StraightShotAction(BardAction):
    affected_by_barrage = True
    potency = 140

    @property
    def guarantee_crit(self):
        if self.source.buffs.straighter_shot.up:
            return True

    def perform(self):
        super().perform()

        if self.source.buffs.straighter_shot.up:
            self.sim.schedule(ConsumeAuraEvent(sim=self.sim,
                                               target=self.source,
                                               aura=self.source.buffs.straighter_shot))

        self.schedule_aura_events(self.source, self.source.buffs.straight_shot)


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
    affected_by_barrage = True

    @property
    def potency(self):
        return 100 if self.source.level < 64 else 120

    def perform(self):
        super().perform()

        self.schedule_aura_events(self.source.target, self.source.target_data.venomous_bite)

        dot = self.source.target_data.venomous_bite

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

        self.sim.schedule(tick_event)


class MiserysEndAction(BardAction):
    base_recast_time = timedelta(seconds=12)
    potency = 190


class BloodletterAction(BardAction):
    base_recast_time = timedelta(seconds=8)
    is_off_gcd = True
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
    def potency(self):
        return 50 if self.source.level < 64 else 55

    @property
    def duration(self):
        return timedelta(seconds=15 if self.source.level < 64 else 30)


class WindbiteAction(BardAction):
    affected_by_barrage = True

    @property
    def potency(self):
        return 60 if self.source.level < 64 else 120

    def perform(self):
        super().perform()

        self.schedule_aura_events(aura=self.source.target_data.windbite, target=self.source.target)

        dot = self.source.target_data.windbite

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

        self.sim.schedule(tick_event)


class BardSongBuff(Aura):
    duration = timedelta(seconds=30)

    def apply(self, target):
        super().apply(target)

        target.stats[Attribute.CRITICAL_HIT] *= 1.02

    def expire(self, target):
        super().expire(target)

        target.stats[Attribute.CRITICAL_HIT] /= 1.02


class MagesBalladBuff(BardSongBuff):
    pass


class MagesBalladAction(BardAction):
    base_recast_time = timedelta(seconds=80)
    potency = 100

    def perform(self):
        super().perform()

        self.schedule_aura_events(aura=self.source.buffs.mages_ballad, target=self.source)


class RainOfDeathAction(BardAction):
    is_off_gcd = True
    potency = 100

    @property
    def shares_recast_with(self):
        return self.source.actions.bloodletter


class IronJawsAction(BardAction):
    affected_by_barrage = True
    potency = 100

    def perform(self):
        super().perform()

        if self.source.target_data.windbite.up:
            self.schedule_aura_events(target=self.source.target, aura=self.source.target_data.windbite)

        if self.source.target_data.venomous_bite.up:
            self.schedule_aura_events(target=self.source.target, aura=self.source.target_data.venomous_bite)


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


class RefulgentArrowAction(BardAction):
    affected_by_barrage = True
    potency = 300

    def perform(self):
        super().perform()

        if self.source.buffs.straighter_shot.up:
            self.sim.schedule(ConsumeAuraEvent(sim=self.sim,
                                               target=self.source,
                                               aura=self.source.buffs.straighter_shot))


class BarrageBuff(Aura):
    duration = timedelta(seconds=10)


class BarrageAction(BardAction):
    base_recast_time = timedelta(seconds=80)

    def perform(self):
        super().perform()

        self.schedule_aura_events(self.source, self.source.buffs.barrage)


class FoeTickEvent(ResourceEvent):
    def __init__(self, sim: Simulation, target: Actor):
        super().__init__(sim=sim, target=target, resource=Resource.MANA, amount=-1680)

    def execute(self) -> None:
        super().execute()

        current_mp, max_mp = self.target.resources[Resource.MANA]

        if current_mp > 0:
            self.sim.schedule(FoeTickEvent(sim=self.sim, target=self.target), delta=timedelta(seconds=3))
        else:
            original_target = self.target.target

            for actor in self.sim.actors:
                if actor.race is Race.ENEMY:
                    self.target.target = actor

                    self.sim.schedule(
                        event=ExpireAuraEvent(sim=self.sim, target=actor, aura=self.target.target_data.foe_requiem),
                        delta=timedelta(seconds=6)
                    )

            self.target.target = original_target

            self.sim.schedule(
                event=ExpireAuraEvent(sim=self.sim, target=self.target, aura=self.target.buffs.foe_requiem),
            )


class FoeRequiemDebuff(Aura):
    pass


class FoeRequiemBuff(Aura):
    def __init__(self, source: Bard) -> None:
        super().__init__()

        self.source = source

    @property
    def up(self):
        return self in self.source.auras


class FoeRequiemAction(BardAction):
    base_cast_time = timedelta(seconds=1.5)

    def perform(self):
        super().perform()

        original_target = self.source.target

        for actor in self.sim.actors:
            if actor.race is Race.ENEMY:
                self.source.target = actor
                self.sim.schedule(
                    event=ApplyAuraEvent(sim=self.sim, target=actor, aura=self.source.target_data.foe_requiem),
                    delta=self.cast_time,
                )

        self.source.target = original_target

        delta = self.cast_time + timedelta(seconds=3)

        self.sim.schedule(
            event=FoeTickEvent(sim=self.sim, target=self.source),
            delta=delta
        )

        self.sim.schedule(
            event=ApplyAuraEvent(sim=self.sim, target=self.source, aura=self.source.buffs.foe_requiem),
        )
