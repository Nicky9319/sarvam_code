from typing import List, Optional

import aiomysql
from pydantic import BaseModel, Field


class DBExecuteRequest(BaseModel):
    query: str
    params: Optional[tuple] = None


class DBRowResponse(BaseModel):
    row: Optional[dict] = None
    success: bool = True
    error: Optional[str] = None


class DBRowsResponse(BaseModel):
    rows: List[dict] = Field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class DBTransactionRequest(BaseModel):
    queries: List[tuple]


class DBTransactionResponse(BaseModel):
    success: bool = True
    results: Optional[List[dict]] = None
    error: Optional[str] = None


class DBDatabase:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        logger,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._logger = logger
        self._pool: Optional[aiomysql.Pool] = None

    async def initialize(self) -> None:
        self._pool = await aiomysql.create_pool(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            db=self._database,
            minsize=10,
            maxsize=20,
            autocommit=True,
        )

    async def cleanup(self) -> None:
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    @property
    def is_initialized(self) -> bool:
        return self._pool is not None