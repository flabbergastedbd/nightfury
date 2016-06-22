class NoElementsToInteract(BaseException):
    message = "No elements present in state to interact"
    pass


class StruckInLoop(BaseException):
    message = "Struck in a loop"
    pass


class ResetEnvironment(BaseException):
    message = "Reset environment"
    pass
