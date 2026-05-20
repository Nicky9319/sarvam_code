from classes.Logger.logger import LogSidecar


class ClassificationChannel:
    """Runtime channel for ticket classification."""

    def __init__(self, logger: LogSidecar) -> None:
        self._logger = logger

    async def initialize(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass
