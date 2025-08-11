import structlog
from psycopg2 import sql

from app.db.database_connection import PostgresDatabaseConnection

logger = structlog.getLogger(__name__)


class TicketRequestRepository:
    def __init__(self, db_connection: PostgresDatabaseConnection) -> None:
        self._db = db_connection
        self._db.connect()

    def create_table(self) -> None:
        with self._db.connection.cursor() as cursor:
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS ticket_requests
                           (
                               id SERIAL PRIMARY KEY,
                               departure_station VARCHAR(100) NOT NULL,
                               arrival_station VARCHAR(100) NOT NULL,
                               travel_date DATE NOT NULL,
                               travel_time TIME NOT NULL,
                               chat_id BIGINT NOT NULL,
                               user_id BIGINT NOT NULL,
                               user_name VARCHAR(200),
                               is_active BOOLEAN DEFAULT FALSE,
                               created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                               updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                               )
                           """)
            self._db.connection.commit()
            logger.info(
                f"Table ticket_requests created successfully in database {self._db.connection.dsn}"
            )

    def add_request(
        self,
        departure: str,
        arrival: str,
        date: str,
        time: str,
        chat_id: int,
        user_id: int,
        user_name: str,
    ) -> tuple | None:  # type: ignore
        query = sql.SQL("""
                        INSERT INTO ticket_requests
                        (departure_station, arrival_station, travel_date, travel_time, chat_id, user_id, user_name)
                        VALUES (%s, %s, %s, %s, %s) ON CONFLICT
                        ON CONSTRAINT unique_request DO
                        UPDATE
                            SET updated_at = NOW()
                            RETURNING id
                        """)

        with self._db.connection.cursor() as cursor:
            cursor.execute(
                query, (departure, arrival, date, time, chat_id, user_id, user_name)
            )
            self._db.connection.commit()
            logger.info(
                f"Request: Departure {departure} Arrival {arrival} Date {date} Time {time}"
                f"Chat_id {chat_id} User_id {user_id} User_name {user_name} added successfully"
            )
            return cursor.fetchone()

    def get_active_requests(self) -> list[dict]:  # type: ignore
        query = sql.SQL("""SELECT id,
                                  departure_station,
                                  arrival_station,
                                  travel_date,
                                  travel_time,
                                  chat_id,
                                  user_id,
                                  user_name
                           FROM ticket_requests
                           WHERE is_active = TRUE""")
        with self._db.connection.cursor() as cursor:
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def set_request_inactive(
        self,
        departure: str,
        arrival: str,
        date: str,
        time: str,
        chat_id: int,
        user_id: int,
        user_name: str,
    ) -> None:
        query = sql.SQL("""
                        UPDATE ticket_requests
                        SET is_active = FALSE
                        WHERE departure_station = %s AND arrival_station = %s AND travel_date = %s AND travel_time = %s AND chat_id = %s AND user_id = %s AND user_name = %s
                        """)
        with self._db.connection.cursor() as cursor:
            cursor.execute(
                query, (departure, arrival, date, time, chat_id, user_id, user_name)
            )
            self._db.connection.commit()
            logger.info(
                f"Request: Departure {departure} Arrival {arrival} Date {date} Time {time} set inactive successfully"
            )
