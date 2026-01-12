import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Iterable

from core.enums import ApplicationStatus, BranchStatus

DB_PATH = Path("insurance.db")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [r["name"] for r in cur.fetchall()]
    return column in cols


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str):
    if not _table_has_column(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def db_init():
    with _connect() as conn:
        # Applications
        conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        # миграция: новые поля по ТЗ
        _ensure_column(conn, "applications", "client_fio", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "applications", "insured_object", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "applications", "request_text", "TEXT NOT NULL DEFAULT ''")

        _ensure_column(conn, "applications", "risk_percent", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "applications", "tariff_amount", "REAL")
        _ensure_column(conn, "applications", "underwriter_updated_at", "TEXT")
        _ensure_column(conn, "applications", "admin_updated_at", "TEXT")

        # Contracts
        conn.execute("""
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL UNIQUE,
            status TEXT NOT NULL,
            client_signed INTEGER NOT NULL DEFAULT 0,
            director_signed INTEGER NOT NULL DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(application_id) REFERENCES applications(id) ON DELETE CASCADE
        )
        """)
        _ensure_column(conn, "contracts", "branch_id", "INTEGER")
        _ensure_column(conn, "contracts", "draft_text", "TEXT")

        # Branches
        conn.execute("""
        CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            branch_name TEXT NOT NULL,
            status TEXT NOT NULL,
            confirmed_by_director INTEGER NOT NULL DEFAULT 1,
            approved_by_lawyer INTEGER NOT NULL DEFAULT 0,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        # Insurance types (отдельная таблица)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS insurance_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS application_insurance_types (
            application_id INTEGER NOT NULL,
            type_id INTEGER NOT NULL,
            PRIMARY KEY(application_id, type_id),
            FOREIGN KEY(application_id) REFERENCES applications(id) ON DELETE CASCADE,
            FOREIGN KEY(type_id) REFERENCES insurance_types(id) ON DELETE CASCADE
        )
        """)

        # seed insurance types (если пусто)
        cur = conn.execute("SELECT COUNT(*) as c FROM insurance_types")
        if int(cur.fetchone()["c"]) == 0:
            default_types = [
                "Пожар",
                "Затопление",
                "Кража",
                "Ущерб третьим лицам",
                "Стихийные бедствия",
            ]
            for n in default_types:
                conn.execute("INSERT INTO insurance_types(name, is_active) VALUES (?, 1)", (n,))

        conn.commit()


# -------------------------
# Applications
# -------------------------

def create_application(client_user: str, *, client_fio: str, insured_object: str, request_text: str) -> int:
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO applications(client_name, client_fio, insured_object, request_text, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (client_user, client_fio, insured_object, request_text, ApplicationStatus.CREATED.name, now, now))
        conn.commit()
        return int(cur.lastrowid)


def list_applications() -> List[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute("""
            SELECT *
            FROM applications
            ORDER BY id DESC
        """)
        return [dict(r) for r in cur.fetchall()]


def get_application(app_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute("""
            SELECT *
            FROM applications
            WHERE id = ?
        """, (app_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def set_application_status(app_id: int, status: ApplicationStatus):
    now = _now_iso()
    with _connect() as conn:
        conn.execute("""
            UPDATE applications
            SET status = ?, updated_at = ?
            WHERE id = ?
        """, (status.name, now, app_id))
        conn.commit()


def set_underwriter_assessment(app_id: int, *, risk_percent: int, type_ids: Iterable[int]):
    now = _now_iso()
    with _connect() as conn:
        conn.execute("""
            UPDATE applications
            SET risk_percent = ?, underwriter_updated_at = ?, updated_at = ?
            WHERE id = ?
        """, (int(risk_percent), now, now, app_id))

        conn.execute("DELETE FROM application_insurance_types WHERE application_id = ?", (app_id,))
        for tid in type_ids:
            conn.execute(
                "INSERT OR IGNORE INTO application_insurance_types(application_id, type_id) VALUES (?, ?)",
                (app_id, int(tid))
            )
        conn.commit()


def get_application_type_ids(app_id: int) -> List[int]:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT type_id FROM application_insurance_types WHERE application_id = ? ORDER BY type_id",
            (app_id,)
        )
        return [int(r["type_id"]) for r in cur.fetchall()]


def set_admin_decision(app_id: int, *, tariff_amount: float):
    now = _now_iso()
    with _connect() as conn:
        conn.execute("""
            UPDATE applications
            SET tariff_amount = ?, admin_updated_at = ?, updated_at = ?
            WHERE id = ?
        """, (float(tariff_amount), now, now, app_id))
        conn.commit()


# -------------------------
# Insurance types
# -------------------------

def list_insurance_types(active_only: bool = True) -> List[Dict[str, Any]]:
    with _connect() as conn:
        if active_only:
            cur = conn.execute("SELECT id, name, is_active FROM insurance_types WHERE is_active = 1 ORDER BY name")
        else:
            cur = conn.execute("SELECT id, name, is_active FROM insurance_types ORDER BY name")
        return [dict(r) for r in cur.fetchall()]


# -------------------------
# Contracts
# -------------------------

def create_contract(application_id: int, *, branch_id: Optional[int], draft_text: Optional[str]) -> int:
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO contracts(application_id, status, client_signed, director_signed, archived, branch_id, draft_text, created_at, updated_at)
            VALUES (?, ?, 0, 0, 0, ?, ?, ?, ?)
        """, (application_id, "prepared", branch_id, draft_text or "", now, now))
        conn.commit()
        return int(cur.lastrowid)


def get_contract_by_application(application_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute("SELECT * FROM contracts WHERE application_id = ?", (application_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def set_contract_flags(
    application_id: int,
    *,
    client_signed=None,
    director_signed=None,
    archived=None,
    status=None,
    branch_id=None,
    draft_text=None
):
    current = get_contract_by_application(application_id)
    if not current:
        raise ValueError("Договор для этой заявки не найден в БД")

    new_client = current["client_signed"] if client_signed is None else int(bool(client_signed))
    new_director = current["director_signed"] if director_signed is None else int(bool(director_signed))
    new_archived = current["archived"] if archived is None else int(bool(archived))
    new_status = current["status"] if status is None else str(status)
    new_branch = current["branch_id"] if branch_id is None else branch_id
    new_draft = current["draft_text"] if draft_text is None else (draft_text or "")

    now = _now_iso()
    with _connect() as conn:
        conn.execute("""
            UPDATE contracts
            SET client_signed=?, director_signed=?, archived=?, status=?, branch_id=?, draft_text=?, updated_at=?
            WHERE application_id=?
        """, (new_client, new_director, new_archived, new_status, new_branch, new_draft, now, application_id))
        conn.commit()


# -------------------------
# Branches
# -------------------------

def create_branch_request(branch_name: str, created_by: str) -> int:
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO branches(branch_name, status, confirmed_by_director, approved_by_lawyer, created_by, created_at, updated_at)
            VALUES (?, ?, 1, 0, ?, ?, ?)
        """, (branch_name, BranchStatus.PENDING.name, created_by, now, now))
        conn.commit()
        return int(cur.lastrowid)


def list_branches() -> List[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute("""
            SELECT id, branch_name, status, confirmed_by_director, approved_by_lawyer, created_by, created_at, updated_at
            FROM branches
            ORDER BY id DESC
        """)
        return [dict(r) for r in cur.fetchall()]


def list_approved_branches() -> List[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute("""
            SELECT id, branch_name
            FROM branches
            WHERE status = ? AND approved_by_lawyer = 1
            ORDER BY branch_name
        """, (BranchStatus.APPROVED.name,))
        return [dict(r) for r in cur.fetchall()]


def get_branch(branch_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute("""
            SELECT id, branch_name, status, confirmed_by_director, approved_by_lawyer, created_by, created_at, updated_at
            FROM branches
            WHERE id = ?
        """, (branch_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def approve_branch_by_lawyer(branch_id: int):
    branch = get_branch(branch_id)
    if not branch:
        raise ValueError("Заявка на филиал не найдена")

    now = _now_iso()
    with _connect() as conn:
        conn.execute("""
            UPDATE branches
            SET approved_by_lawyer = 1,
                status = ?,
                updated_at = ?
            WHERE id = ?
        """, (BranchStatus.APPROVED.name, now, branch_id))
        conn.commit()
