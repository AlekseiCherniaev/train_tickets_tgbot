import psycopg2
import structlog
from psycopg2.extras import DictCursor

logger = structlog.get_logger(__name__)


class PostgresDatabaseConnection:
    def __init__(
        self, dbname: str, dbuser: str, dbpassword: str, dbhost: str, dbport: int = 5432
    ) -> None:
        self._dbname = dbname
        self._user = dbuser
        self._password = dbpassword
        self._host = dbhost
        self._port = dbport
        self._connection: psycopg2.extensions.connection | None = None

    def connect(self) -> None:
        try:
            self._connection = psycopg2.connect(
                dbname=self._dbname,
                user=self._user,
                password=self._password,
                host=self._host,
                port=self._port,
                cursor_factory=DictCursor,
            )
            logger.info("Database connection established successfully")
        except psycopg2.Error as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def disconnect(self) -> None:
        if self._connection:
            self._connection.close()
            logger.info("Database connection closed successfully")

    @property
    def connection(self) -> psycopg2.extensions.connection:
        if not self._connection:
            raise ConnectionError("Database is not connected")
        return self._connection
