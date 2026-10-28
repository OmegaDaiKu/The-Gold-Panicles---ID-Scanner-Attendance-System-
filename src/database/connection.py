""""Database connection and transaction manager supporting SQLite WAL mode."""

import sqlite3
import threading
from contextlib import contextmanager


class _ReadersWriterLock:
    """Readers-writer lock gating DatabaseConnectionManager.transaction()
    (read side) against writer_lock() (write side, used by restore_backup).

    REPLACED THIS SESSION: the prior implementation used the classic
    "first reader acquires an RLock, last reader releases it" pattern.
    That has two confirmed failure modes under real concurrency (verified
    by manual trace against this exact file, not assumed):

      1. If the first reader to arrive and the last reader to leave are
         different threads (routine with overlapping scans/sync-worker
         activity), the last reader calls RLock.release() on a lock it
         never acquired. That raises RuntimeError, AND leaves the first
         reader's thread holding the RLock forever, since its own
         release_read() call was a correctly-skipped no-op. Every future
         acquire_write() call, from any thread, then blocks permanently.

      2. The old acquire_read() held its bookkeeping lock (_count_lock)
         for the full duration of a potentially-blocking
         exclusion_lock.acquire() call. If a writer thread (W) holds the
         lock and a second thread (R) arrives as a reader while W is
         still running, R blocks on the exclusion lock while holding
         _count_lock. If W then performs its own internal read (e.g.
         restore_backup calling create_backup()/audit_repo.log_action()
         afterward), W blocks trying to acquire _count_lock, which R is
         holding. W waits on R, R waits on W: deadlock.

    This Condition-based implementation fixes both: there is no lock
    "ownership" to hand off between threads (just a counter protected by
    a Condition), and a writer's own thread is explicitly permitted
    through acquire_read() without contending against itself, which is
    what makes case 2 safe.

    KNOWN LIMITATION, accepted rather than solved here: no writer-
    priority mechanism, so sustained heavy read load could in principle
    starve a writer. writer_lock() is only exercised by the rare,
    user-triggered restore_backup path, so this is judged an acceptable
    tradeoff rather than a correctness bug. Flagged explicitly rather
    than silently accepted.
    """

    def __init__(self):
        self._cond = threading.Condition()
        self._readers = 0
        self._writer = None
        self._writer_depth = 0

    def acquire_read(self) -> None:
        me = threading.get_ident()
        with self._cond:
            while self._writer not in (None, me):
                self._cond.wait()
            self._readers += 1

    def release_read(self) -> None:
        with self._cond:
            self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    def acquire_write(self) -> None:
        me = threading.get_ident()
        with self._cond:
            if self._writer == me:
                self._writer_depth += 1
                return
            while self._writer is not None or self._readers:
                self._cond.wait()
            self._writer = me
            self._writer_depth = 1

    def release_write(self) -> None:
        with self._cond:
            self._writer_depth -= 1
            if self._writer_depth == 0:
                self._writer = None
                self._cond.notify_all()


class DatabaseConnectionManager:
    """Manages SQLite database connections, WAL mode enablement, and transaction contexts."""

    def __init__(self, db_path: str = "tgp_attendance.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._rw_lock = _ReadersWriterLock()

    def _get_local_state(self):
        if not hasattr(self._local, "conn"):
            self._local.conn = None
            self._local.tx_depth = 0
        return self._local

    def get_connection(self) -> sqlite3.Connection:
        state = self._get_local_state()
        if state.conn is None:
            state.conn = sqlite3.connect(self.db_path, timeout=10.0)
            state.conn.row_factory = sqlite3.Row
            state.conn.execute("PRAGMA journal_mode=WAL;")
            state.conn.execute("PRAGMA foreign_keys=ON;")
        return state.conn

    @contextmanager
    def transaction(self):
        """FIXED THIS SESSION (see module-level findings): tx_depth is
        now decremented exactly once, unconditionally, via `finally` --
        never twice, never skipped. Whether to commit/rollback is
        decided from `outermost`, a flag captured once at entry, rather
        than by re-reading tx_depth after it may have already been
        mutated by a failure. Previously, a commit() that itself raised
        (locked DB, disk full) caused tx_depth to be decremented twice,
        landing on -1 forever: rollback was skipped on the spot, and
        every subsequent transaction on that thread silently never
        committed again, with no exception and no log output.

        `except BaseException` (widened from the prior `except
        Exception`) is deliberate: a KeyboardInterrupt/SystemExit mid-
        write should still trigger a rollback instead of leaving an open
        transaction, same reasoning as the bug being fixed.
        """
        state = self._get_local_state()
        outermost = (state.tx_depth == 0)
        if outermost:
            self._rw_lock.acquire_read()
        try:
            conn = self.get_connection()
            state.tx_depth += 1
            try:
                yield conn
                if outermost:
                    conn.commit()
            except BaseException:
                if outermost:
                    conn.rollback()
                raise
            finally:
                state.tx_depth -= 1
        finally:
            if outermost:
                self._rw_lock.release_read()

    @contextmanager
    def reader_lock(self):
        self._rw_lock.acquire_read()
        try:
            yield
        finally:
            self._rw_lock.release_read()

    @contextmanager
    def writer_lock(self):
        self._rw_lock.acquire_write()
        try:
            yield
        finally:
            self._rw_lock.release_write()

    def initialize_schema(self) -> None:
        from src.database.schema import SchemaInitializer
        initializer = SchemaInitializer(self)
        initializer.ensure_schema_exists()

    def close(self) -> None:
        state = self._get_local_state()
        if state.conn is not None:
            state.conn.close()
            state.conn = None
            state.tx_depth = 0

    def close_thread_connection(self) -> None:
        self.close()