"""Durable, single-host consume-once reservations."""

import sqlite3

from pathlib import Path


class ReservationStoreError(RuntimeError):
    """Raised when replay state cannot be read or durably updated."""


def reserve_once(
    database_path: Path,
    reservation_key: str,
    *,
    timeout_seconds: float = 5.0,
) -> bool:
    """Atomically reserve ``reservation_key`` in durable local state.

    A separate SQLite connection is used for every call so independent threads
    and processes on one host share the same transaction boundary.
    ``BEGIN IMMEDIATE`` serializes contenders before the existence check, and
    ``synchronous=FULL`` asks SQLite to synchronize the commit before a
    successful return.

    Args:
      database_path: SQLite database holding permanent reservations.
      reservation_key: Presenter-invariant mandate or transaction identifier.
      timeout_seconds: Maximum time to wait for another writer.

    Returns:
      ``True`` only for the caller that created the reservation, or ``False``
      when the key was already reserved.

    Raises:
      ValueError: If the key or timeout is invalid.
      ReservationStoreError: If state is corrupt, unreadable, locked beyond the
        timeout, or cannot be committed. Callers must treat this as a refusal.
    """
    if not reservation_key:
        raise ValueError('reservation_key must not be empty')
    if timeout_seconds < 0:
        raise ValueError('timeout_seconds must not be negative')

    connection: sqlite3.Connection | None = None
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            database_path,
            timeout=timeout_seconds,
            isolation_level=None,
        )
        connection.execute('PRAGMA synchronous = FULL')
        connection.execute('BEGIN IMMEDIATE')

        integrity_result = connection.execute('PRAGMA quick_check').fetchall()
        if integrity_result != [('ok',)]:
            raise ReservationStoreError(
                'reservation state failed integrity check'
            )

        connection.execute(
            """
        CREATE TABLE IF NOT EXISTS reservations (
          reservation_key TEXT PRIMARY KEY,
          reserved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) WITHOUT ROWID
        """
        )
        existing = connection.execute(
            'SELECT 1 FROM reservations WHERE reservation_key = ?',
            (reservation_key,),
        ).fetchone()
        if existing:
            connection.rollback()
            return False

        connection.execute(
            'INSERT INTO reservations (reservation_key) VALUES (?)',
            (reservation_key,),
        )
        connection.commit()
        return True
    except ReservationStoreError:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise ReservationStoreError(
            f'reservation state unavailable at {database_path}'
        ) from exc
    finally:
        if connection is not None:
            connection.close()
