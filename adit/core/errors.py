from datetime import timedelta


class RetriableTaskError(Exception):
    def __init__(self, message: str, long_delay: bool = False) -> None:
        if long_delay:
            self.delay = timedelta(hours=24)
        else:
            self.delay = timedelta(minutes=10)

        super().__init__(message)
