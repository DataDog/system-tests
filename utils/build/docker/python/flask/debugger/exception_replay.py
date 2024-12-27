class ExceptionReplayRock(Exception):
    def __init__(self):
        super().__init__("rock exception")


class ExceptionReplayPaper(Exception):
    def __init__(self):
        super().__init__("paper exception")


class ExceptionReplayScissors(Exception):
    def __init__(self):
        super().__init__("scissors exception")
