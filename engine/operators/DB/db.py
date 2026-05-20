from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database


class DBDatabase:
    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        logger,
    ) -> None:
        self._host = host
        self._port = port
        self._database = database
        self._logger = logger
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None

    def initialize(self) -> None:
        self._client = MongoClient(
            host=self._host,
            port=self._port,
        )
        self._db = self._client[self._database]

    async def initialize_async(self) -> None:
        self.initialize()

    def cleanup(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._db = None

    @property
    def is_initialized(self) -> bool:
        return self._client is not None

    @property
    def db(self) -> Database:
        if not self._db:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._db