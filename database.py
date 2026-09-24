import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime

DB_PATH = "studsmena.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Таблица пользователей
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        role TEXT NOT NULL, -- 'student' или 'employer'
        full_name TEXT,
        username TEXT,
        phone TEXT,
        institution TEXT DEFAULT 'СКУ им. М. Козыбаева',
        campus TEXT DEFAULT 'ул. Интернациональная 26',
        status TEXT DEFAULT 'busy', -- 'free' или 'busy'
        free_from TEXT DEFAULT '17:00',
        free_to TEXT DEFAULT '21:00',
        rating REAL DEFAULT 5.0,
        completed_shifts INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Таблица смен
    cur.execute("""
    CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employer_id INTEGER NOT NULL,
        employer_name TEXT,
        raw_text TEXT,
        title TEXT NOT NULL,
        category TEXT,
        location_name TEXT NOT NULL,
        address TEXT,
        duration_hours INTEGER DEFAULT 3,
        pay_amount INTEGER NOT NULL,
        time_window TEXT,
        status TEXT DEFAULT 'open', -- 'open', 'matched', 'completed'
        assigned_student_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Таблица откликов
    cur.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shift_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending', -- 'pending', 'accepted', 'completed'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(shift_id, student_id)
    );
    """)

    conn.commit()
    conn.close()

def upsert_user(telegram_id: int, role: str, full_name: str, username: Optional[str] = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO users (telegram_id, role, full_name, username)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(telegram_id) DO UPDATE SET
        role = excluded.role,
        full_name = excluded.full_name,
        username = excluded.username;
    """, (telegram_id, role, full_name, username))
    conn.commit()
    conn.close()

def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def set_student_status(telegram_id: int, status: str, free_from: str = "17:00", free_to: str = "21:00", full_name: str = "", username: str = ""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO users (telegram_id, role, full_name, username, status, free_from, free_to)
    VALUES (?, 'student', ?, ?, ?, ?, ?)
    ON CONFLICT(telegram_id) DO UPDATE SET
        status = excluded.status,
        free_from = excluded.free_from,
        free_to = excluded.free_to,
        full_name = CASE WHEN excluded.full_name != '' THEN excluded.full_name ELSE users.full_name END,
        username = CASE WHEN excluded.username != '' THEN excluded.username ELSE users.username END;
    """, (telegram_id, full_name, username, status, free_from, free_to))
    conn.commit()
    conn.close()

def set_student_institution(telegram_id: int, institution: str, campus: str, full_name: str = "", username: str = ""):
    conn = get_connection()
    cur = conn.cursor()
    # Ensure columns exist if table was created earlier
    try:
        cur.execute("ALTER TABLE users ADD COLUMN institution TEXT DEFAULT 'СКУ им. М. Козыбаева'")
    except sqlite3.OperationalError:
        pass
    cur.execute("""
    INSERT INTO users (telegram_id, role, full_name, username, institution, campus)
    VALUES (?, 'student', ?, ?, ?, ?)
    ON CONFLICT(telegram_id) DO UPDATE SET
        institution = excluded.institution,
        campus = excluded.campus,
        full_name = CASE WHEN excluded.full_name != '' THEN excluded.full_name ELSE users.full_name END,
        username = CASE WHEN excluded.username != '' THEN excluded.username ELSE users.username END;
    """, (telegram_id, full_name, username, institution, campus))
    conn.commit()
    conn.close()

def set_student_campus(telegram_id: int, campus: str):
    set_student_institution(telegram_id, "СКУ им. М. Козыбаева", campus)

def get_free_students() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE role = 'student' AND status = 'free'")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_shift(employer_id: int, employer_name: str, raw_text: str, parsed: Dict[str, Any]) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO shifts (
        employer_id, employer_name, raw_text, title, category,
        location_name, address, duration_hours, pay_amount, time_window
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        employer_id,
        employer_name,
        raw_text,
        parsed.get("title", "Экспресс-подработка"),
        parsed.get("category", "Разное"),
        parsed.get("location_name", "Петропавловск"),
        parsed.get("address", ""),
        parsed.get("duration_hours", 3),
        parsed.get("pay_amount", 5000),
        parsed.get("time_window", "17:00 - 20:00")
    ))
    shift_id = cur.lastrowid
    conn.commit()
    conn.close()
    return shift_id

def get_shift(shift_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_open_shifts() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM shifts WHERE status = 'open' ORDER BY id DESC LIMIT 5")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def assign_shift_to_student(shift_id: int, student_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    # Проверяем, что смена еще открыта
    cur.execute("SELECT status FROM shifts WHERE id = ?", (shift_id,))
    row = cur.fetchone()
    if not row or row["status"] != "open":
        conn.close()
        return False

    cur.execute("""
    UPDATE shifts 
    SET status = 'matched', assigned_student_id = ?
    WHERE id = ?
    """, (student_id, shift_id))

    cur.execute("""
    INSERT OR REPLACE INTO applications (shift_id, student_id, status)
    VALUES (?, ?, 'accepted')
    """, (shift_id, student_id))

    # Обновляем счетчик студента
    cur.execute("""
    UPDATE users 
    SET status = 'busy', completed_shifts = completed_shifts + 1
    WHERE telegram_id = ?
    """, (student_id,))

    conn.commit()
    conn.close()
    return True

def get_student_total_earned(student_id: int) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT COALESCE(SUM(pay_amount), 0) as total 
    FROM shifts 
    WHERE assigned_student_id = ? AND status IN ('matched', 'completed')
    """, (student_id,))
    row = cur.fetchone()
    conn.close()
    return int(row["total"]) if row else 0

def get_employer_shifts(employer_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT s.*, u.full_name as student_name, u.username as student_username, u.institution as student_institution
    FROM shifts s
    LEFT JOIN users u ON s.assigned_student_id = u.telegram_id
    WHERE s.employer_id = ?
    ORDER BY s.id DESC
    LIMIT 10
    """, (employer_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def complete_shift(shift_id: int, employer_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM shifts WHERE id = ? AND employer_id = ?", (shift_id, employer_id))
    row = cur.fetchone()
    if not row or row["status"] != "matched":
        conn.close()
        return None

    cur.execute("UPDATE shifts SET status = 'completed' WHERE id = ?", (shift_id,))

    student_id = row["assigned_student_id"]
    if student_id:
        cur.execute("UPDATE users SET status = 'free' WHERE telegram_id = ?", (student_id,))
        cur.execute("UPDATE applications SET status = 'completed' WHERE shift_id = ? AND student_id = ?", (shift_id, student_id))

    conn.commit()
    cur.execute("""
    SELECT s.*, u.full_name as student_name, u.username as student_username
    FROM shifts s
    LEFT JOIN users u ON s.assigned_student_id = u.telegram_id
    WHERE s.id = ?
    """, (shift_id,))
    updated_row = cur.fetchone()
    conn.close()
    return dict(updated_row) if updated_row else None

def cancel_shift(shift_id: int, employer_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM shifts WHERE id = ? AND employer_id = ?", (shift_id, employer_id))
    row = cur.fetchone()
    if not row or row["status"] != "open":
        conn.close()
        return False
    cur.execute("UPDATE shifts SET status = 'cancelled' WHERE id = ? AND employer_id = ?", (shift_id, employer_id))
    conn.commit()
    conn.close()
    return True

