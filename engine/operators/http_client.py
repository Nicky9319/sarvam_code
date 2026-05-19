from classes.Logger.logger import LogAgent


class HTTPAPIClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        logger: LogAgent,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._logger = logger