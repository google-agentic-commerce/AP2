"""Regression tests for durable consume-once reservations."""

import multiprocessing
import sqlite3

from pathlib import Path

import pytest

from common.durable_reservation_store import (
    ReservationStoreError,
    reserve_once,
)


def _reserve_in_process(arguments: tuple[str, str]) -> bool:
    """Reserve a key from an independent process."""
    database_path, reservation_key = arguments
    return reserve_once(Path(database_path), reservation_key)


def test_sequential_replay_is_refused(tmp_path: Path):
    database_path = tmp_path / 'consumed.sqlite3'

    assert reserve_once(database_path, 'closed-mandate-hash')
    assert not reserve_once(database_path, 'closed-mandate-hash')


def test_concurrent_processes_allow_exactly_one_reservation(tmp_path: Path):
    database_path = tmp_path / 'consumed.sqlite3'
    arguments = [(str(database_path), 'shared-transaction') for _ in range(8)]

    context = multiprocessing.get_context('spawn')
    with context.Pool(processes=8) as pool:
        results = pool.map(_reserve_in_process, arguments)

    assert results.count(True) == 1
    assert results.count(False) == 7


def test_reservation_survives_a_new_store_instance(tmp_path: Path):
    database_path = tmp_path / 'consumed.sqlite3'

    assert reserve_once(database_path, 'checkout-hash')

    # A fresh call opens a fresh database connection, as a restarted service
    # would, and must still observe the durable reservation.
    assert not reserve_once(database_path, 'checkout-hash')


def test_corrupt_state_fails_closed(tmp_path: Path):
    database_path = tmp_path / 'consumed.sqlite3'
    database_path.write_bytes(b'not a sqlite database')

    with pytest.raises(ReservationStoreError):
        reserve_once(database_path, 'closed-mandate-hash')


def test_unreadable_state_fails_closed(tmp_path: Path):
    database_path = tmp_path / 'directory-instead-of-database'
    database_path.mkdir()

    with pytest.raises(ReservationStoreError):
        reserve_once(database_path, 'closed-mandate-hash')


def test_busy_state_fails_closed_when_lock_timeout_expires(tmp_path: Path):
    database_path = tmp_path / 'consumed.sqlite3'
    assert reserve_once(database_path, 'existing-reservation')

    locking_connection = sqlite3.connect(database_path, isolation_level=None)
    locking_connection.execute('BEGIN IMMEDIATE')
    try:
        with pytest.raises(ReservationStoreError):
            reserve_once(
                database_path,
                'new-reservation',
                timeout_seconds=0,
            )
    finally:
        locking_connection.rollback()
        locking_connection.close()
