"""Create outbox row when a vaccination is saved.

Call this from your EHR vaccination-save code inside the same transaction.
"""

from __future__ import annotations

import pyodbc


def save_vaccination_with_outbox(
    connection: pyodbc.Connection,
    vaccination_sql: str,
    vaccination_params: tuple,
) -> tuple[int, int]:
    """Insert vaccination and create matching CAIR outbox row atomically.

    Returns (vaccination_id, outbox_id).
    """
    cursor = connection.cursor()
    try:
        cursor.execute(vaccination_sql, vaccination_params)
        cursor.execute("SELECT CAST(SCOPE_IDENTITY() AS BIGINT)")
        vaccination_id = int(cursor.fetchone()[0])

        cursor.execute(
            """
            INSERT INTO cair_outbox (vaccination_id, status, attempt_count)
            OUTPUT INSERTED.id
            VALUES (?, 'PENDING', 0)
            """,
            vaccination_id,
        )
        outbox_id = int(cursor.fetchone()[0])
        connection.commit()
        return vaccination_id, outbox_id
    except Exception:
        connection.rollback()
        raise


def enqueue_vaccination_resubmit(connection: pyodbc.Connection, vaccination_id: int) -> int:
    """Create a new outbox row when an already-sent vaccination is edited."""
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO cair_outbox (vaccination_id, status, attempt_count)
        OUTPUT INSERTED.id
        VALUES (?, 'PENDING', 0)
        """,
        vaccination_id,
    )
    outbox_id = int(cursor.fetchone()[0])
    connection.commit()
    return outbox_id
