class RejectMessage(Exception):
    """Signal that a message should be dropped."""

    pass


class RetryMessage(Exception):
    """Signal that a message should be retried after a delay."""

    def __init__(self, delay: float = 0.0, message: str = "") -> None:
        self.delay = delay
        super().__init__(message)
