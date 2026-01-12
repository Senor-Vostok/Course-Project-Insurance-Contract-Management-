import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

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
        # -------------------------
        # Applications
        # -------------------------
        conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        # данные клиента/объекта (вводит клиент)
        _ensure_column(conn, "applications", "client_fio", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "applications", "insured_object", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "applications", "request_text", "TEXT NOT NULL DEFAULT ''")

        # оценка андеррайтера: риск + ОДИН вид страхования
        _ensure_column(conn, "applications", "risk_percent", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "applications", "insurance_type_id", "INTEGER")
        _ensure_column(conn, "applications", "underwriter_updated_at", "TEXT")

        # решение администратора: страховая сумма + тарифная ставка + рассчитанный тариф
        _ensure_column(conn, "applications", "insurance_sum", "REAL")
        _ensure_column(conn, "applications", "tariff_rate", "REAL")   # в процентах
        _ensure_column(conn, "applications", "tariff_amount", "REAL") # сумма к оплате (можем считать)
        _ensure_column(conn, "applications", "admin_updated_at", "TEXT")

        # -------------------------
        # Branches (филиалы)
        # -------------------------
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
        _ensure_column(conn, "branches", "address", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "branches", "phone", "TEXT NOT NULL DEFAULT ''")

        # -------------------------
        # Insurance types (справочник видов страхования)
        # -------------------------
        conn.execute("""
        CREATE TABLE IF NOT EXISTS insurance_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """)

        # seed видов страхования (если пусто)
        cur = conn.execute("SELECT COUNT(*) as c FROM insurance_types")
        if int(cur.fetchone()["c"]) == 0:
            default_types = [
                "Страхование автотранспорта от угона",
                "Страхование домашнего имущества",
                "Добровольное медицинское страхование",
            ]
            for n in default_types:
                conn.execute("INSERT INTO insurance_types(name, is_active) VALUES (?, 1)", (n,))

        # -------------------------
        # Contracts (договоры)
        # -------------------------
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
        # поля договора по предметной области
        _ensure_column(conn, "contracts", "contract_date", "TEXT")         # дата заключения
        _ensure_column(conn, "contracts", "insurance_sum", "REAL")
        _ensure_column(conn, "contracts", "insurance_type_id", "INTEGER")
        _ensure_column(conn, "contracts", "tariff_rate", "REAL")
        _ensure_column(conn, "contracts", "tariff_amount", "REAL")
        _ensure_column(conn, "contracts", "branch_id", "INTEGER")
        _ensure_column(conn, "contracts", "draft_text", "TEXT")

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


def get_insurance_type(type_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute("SELECT id, name, is_active FROM insurance_types WHERE id = ?", (type_id,))
        row = cur.fetchone()
        return dict(row) if row else None


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
        cur = conn.execute("SELECT * FROM applications ORDER BY id DESC")
        return [dict(r) for r in cur.fetchall()]


def get_application(app_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
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


def set_underwriter_assessment(app_id: int, *, risk_percent: int, insurance_type_id: int):
    now = _now_iso()
    with _connect() as conn:
        conn.execute("""
            UPDATE applications
            SET risk_percent = ?, insurance_type_id = ?, underwriter_updated_at = ?, updated_at = ?
            WHERE id = ?
        """, (int(risk_percent), int(insurance_type_id), now, now, app_id))
        conn.commit()


def set_admin_decision(app_id: int, *, insurance_sum: float, tariff_rate: float) -> float:
    """
    Сохраняет страховую сумму и тарифную ставку (%).
    Возвращает рассчитанный тариф (сумма к оплате).
    """
    now = _now_iso()
    insurance_sum = float(insurance_sum)
    tariff_rate = float(tariff_rate)
    tariff_amount = insurance_sum * (tariff_rate / 100.0)

    with _connect() as conn:
        conn.execute("""
            UPDATE applications
            SET insurance_sum = ?, tariff_rate = ?, tariff_amount = ?, admin_updated_at = ?, updated_at = ?
            WHERE id = ?
        """, (insurance_sum, tariff_rate, tariff_amount, now, now, app_id))
        conn.commit()

    return tariff_amount


# -------------------------
# Contracts
# -------------------------

def create_contract_from_application(application_id: int, *, branch_id: int, draft_text: str) -> int:
    """
    Создаёт договор, копируя ключевые данные из заявки:
    дата заключения, страховая сумма, вид страхования, ставка, тариф, филиал.
    """
    app = get_application(application_id)
    if not app:
        raise ValueError("Заявка не найдена")

    now = _now_iso()

    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO contracts(
                application_id, status,
                client_signed, director_signed, archived,
                contract_date, insurance_sum, insurance_type_id, tariff_rate, tariff_amount,
                branch_id, draft_text,
                created_at, updated_at
            )
            VALUES (?, ?, 0, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            application_id, "prepared",
            now,
            app.get("insurance_sum"),
            app.get("insurance_type_id"),
            app.get("tariff_rate"),
            app.get("tariff_amount"),
            int(branch_id),
            draft_text or "",
            now, now
        ))
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
    status=None
):
    current = get_contract_by_application(application_id)
    if not current:
        raise ValueError("Договор для этой заявки не найден в БД")

    new_client = current["client_signed"] if client_signed is None else int(bool(client_signed))
    new_director = current["director_signed"] if director_signed is None else int(bool(director_signed))
    new_archived = current["archived"] if archived is None else int(bool(archived))
    new_status = current["status"] if status is None else str(status)

    now = _now_iso()
    with _connect() as conn:
        conn.execute("""
            UPDATE contracts
            SET client_signed=?, director_signed=?, archived=?, status=?, updated_at=?
            WHERE application_id=?
        """, (new_client, new_director, new_archived, new_status, now, application_id))
        conn.commit()


# -------------------------
# Branches
# -------------------------

def create_branch_request(branch_name: str, address: str, phone: str, created_by: str) -> int:
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO branches(branch_name, address, phone, status, confirmed_by_director, approved_by_lawyer, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, 0, ?, ?, ?)
        """, (branch_name, address, phone, BranchStatus.PENDING.name, created_by, now, now))
        conn.commit()
        return int(cur.lastrowid)


def list_branches() -> List[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute("""
            SELECT *
            FROM branches
            ORDER BY id DESC
        """)
        return [dict(r) for r in cur.fetchall()]


def list_approved_branches() -> List[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute("""
            SELECT id, branch_name, address, phone
            FROM branches
            WHERE status = ? AND approved_by_lawyer = 1
            ORDER BY branch_name
        """, (BranchStatus.APPROVED.name,))
        return [dict(r) for r in cur.fetchall()]


def get_branch(branch_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute("SELECT * FROM branches WHERE id = ?", (branch_id,))
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
