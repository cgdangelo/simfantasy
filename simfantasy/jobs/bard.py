from datetime import timedelta
from typing import Dict, List

from simfantasy.enums import Attribute, Job, Race, Slot
from simfantasy.events import Action, DotTickEvent, Event
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

        if not self.actions.mages_ballad.on_cooldown:
            return self.actions.mages_ballad.perform()

        if not self.target_data.windbite.up or self.target_data.windbite.remains < timedelta(seconds=3):
            return self.actions.windbite.perform()

        if not self.target_data.venomous_bite.up or self.target_data.venomous_bite.remains < timedelta(seconds=3):
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
            self.sim.schedule_in(RepertoireEvent(sim=self.sim, bard=self.source))


class Actions:
    def __init__(self, sim: Simulation, source: Bard):
        self.bloodletter = BloodletterAction(sim, source)
        self.heavy_shot = HeavyShotAction(sim, source)
        self.mages_ballad = MagesBalladAction(sim, source)
        self.miserys_end = MiserysEndAction(sim, source)
        self.raging_strikes = RagingStrikesAction(sim, source)
        self.rain_of_death = RainOfDeathAction(sim, source)
        self.sidewinder = SidewinderAction(sim, source)
        self.straight_shot = StraightShotAction(sim, source)
        self.venomous_bite = VenomousBiteAction(sim, source)
        self.windbite = WindbiteAction(sim, source)


class Buffs:
    def __init__(self):
        self.mages_ballad = MagesBalladBuff()
        self.raging_strikes = RagingStrikesBuff()
        self.straight_shot = StraightShotBuff()


class TargetData:
    def __init__(self, source: Bard):
        self.venomous_bite = VenomousBiteDebuff(source=source)
        self.windbite = WindbiteDebuff(source=source)


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

        self.sim.schedule_in(tick_event)


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

        self.sim.schedule_in(tick_event)


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
