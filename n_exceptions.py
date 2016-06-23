class NoElementsToInteract(BaseException):
    message = "No elements present in state to interact"
    pass


class StruckInLoop(BaseException):
    message = "Struck in a loop"
    pass


class SoftResetEnvironment(BaseException):
    message = "Soft reset environment"
    pass

class HardResetEnvironment(BaseException):
    message = "Hard reset environment"
    pass
