class FailedActionAttemptError(Exception):
    pass


class ActionOnCooldownError(FailedActionAttemptError):
    def __init__(self, sim, source, action, *args: object, **kwargs: object) -> None:
        super().__init__('%s tried to use %s, but on cooldown for %.3f' %
                         (source, action, action.cooldown_remains.total_seconds()), *args, **kwargs)

        self.source = source


class ActorAnimationLockedError(FailedActionAttemptError):
    def __init__(self, sim, source, action, *args: object, **kwargs: object) -> None:
        super().__init__('%s tried to use %s, but animation locked for %.3f' %
                         (source, action, (source.animation_unlock_at - sim.current_time).total_seconds()), *args,
                         **kwargs)


class ActorGCDLockedError(FailedActionAttemptError):
    def __init__(self, sim, source, action, *args: object, **kwargs: object) -> None:
        super().__init__('%s tried to use %s, but GCD locked for %.3f' %
                         (source, action, (source.gcd_unlock_at - sim.current_time).total_seconds()), *args,
                         **kwargs)
