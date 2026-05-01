"""
Module de gestion de la base de données SQLite pour le lecteur RSS.
Toutes les opérations de lecture/écriture passent par cette classe.
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime


_db_path_env = os.environ.get("RSS_DB_PATH")
if _db_path_env:
    DB_PATH = Path(_db_path_env)
    DB_DIR  = DB_PATH.parent
else:
    DB_DIR  = Path.home() / ".local" / "share" / "rss-reader"
    DB_PATH = DB_DIR / "rss_reader.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS feeds (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            url         TEXT NOT NULL UNIQUE,
            category    TEXT NOT NULL DEFAULT 'Général',
            date_added  TEXT NOT NULL,
            last_fetch  TEXT,
            fetch_error TEXT,
            active      INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS articles (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            feed_id        INTEGER NOT NULL,
            title          TEXT,
            link           TEXT,
            summary        TEXT,
            content        TEXT,
            author         TEXT,
            published_date TEXT,
            fetch_date     TEXT NOT NULL,
            read_status    INTEGER NOT NULL DEFAULT 0,
            favorite       INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (feed_id) REFERENCES feeds(id) ON DELETE CASCADE,
            UNIQUE(feed_id, link)
        );

        CREATE INDEX IF NOT EXISTS idx_articles_feed     ON articles(feed_id);
        CREATE INDEX IF NOT EXISTS idx_articles_read     ON articles(read_status);
        CREATE INDEX IF NOT EXISTS idx_articles_favorite ON articles(favorite);
        CREATE INDEX IF NOT EXISTS idx_articles_date     ON articles(published_date DESC);
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# FLUX (feeds)
# ---------------------------------------------------------------------------

def add_feed(name: str, url: str, category: str = "Général") -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO feeds (name, url, category, date_added) VALUES (?, ?, ?, ?)",
            (name, url, category, datetime.now().isoformat()),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_feed(feed_id: int, name: str, url: str, category: str):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE feeds SET name=?, url=?, category=? WHERE id=?",
            (name, url, category, feed_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_feed(feed_id: int):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM feeds WHERE id=?", (feed_id,))
        conn.commit()
    finally:
        conn.close()


def set_feed_active(feed_id: int, active: bool):
    conn = get_connection()
    try:
        conn.execute("UPDATE feeds SET active=? WHERE id=?", (1 if active else 0, feed_id))
        conn.commit()
    finally:
        conn.close()


def set_feed_fetch_result(feed_id: int, error: str | None = None):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE feeds SET last_fetch=?, fetch_error=? WHERE id=?",
            (datetime.now().isoformat(), error, feed_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_feeds() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM feeds ORDER BY category, name"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_feed(feed_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM feeds WHERE id=?", (feed_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_categories() -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT category FROM feeds ORDER BY category"
        ).fetchall()
        return [r["category"] for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# ARTICLES
# ---------------------------------------------------------------------------

def upsert_article(
    feed_id: int,
    title: str,
    link: str,
    summary: str,
    content: str,
    author: str,
    published_date: str,
) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO articles
                (feed_id, title, link, summary, content, author, published_date, fetch_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feed_id, title, link, summary, content, author,
                published_date, datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_articles(
    feed_id: int | None = None,
    only_unread: bool = False,
    only_favorites: bool = False,
    search: str = "",
    limit: int = 500,
) -> list[dict]:
    conditions = []
    params: list = []

    if feed_id is not None:
        conditions.append("a.feed_id = ?")
        params.append(feed_id)

    if only_unread:
        conditions.append("a.read_status = 0")

    if only_favorites:
        conditions.append("a.favorite = 1")

    if search:
        conditions.append("(a.title LIKE ? OR a.summary LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT a.*, f.name AS feed_name, f.category
        FROM articles a
        JOIN feeds f ON f.id = a.feed_id
        {where}
        ORDER BY
            CASE WHEN a.published_date IS NULL OR a.published_date = '' THEN a.fetch_date
                 ELSE a.published_date END DESC
        LIMIT ?
    """
    params.append(limit)

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_article(article_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT a.*, f.name AS feed_name FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE a.id=?",
            (article_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_article_read(article_id: int, read: bool):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE articles SET read_status=? WHERE id=?",
            (1 if read else 0, article_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_article_favorite(article_id: int, favorite: bool):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE articles SET favorite=? WHERE id=?",
            (1 if favorite else 0, article_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_all_read(feed_id: int | None = None):
    conn = get_connection()
    try:
        if feed_id is not None:
            conn.execute(
                "UPDATE articles SET read_status=1 WHERE feed_id=?", (feed_id,)
            )
        else:
            conn.execute("UPDATE articles SET read_status=1")
        conn.commit()
    finally:
        conn.close()


def count_unread(feed_id: int | None = None) -> int:
    conn = get_connection()
    try:
        if feed_id is not None:
            row = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE feed_id=? AND read_status=0",
                (feed_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE read_status=0"
            ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def get_unread_counts_by_feed() -> dict[int, int]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT feed_id, COUNT(*) AS cnt FROM articles WHERE read_status=0 GROUP BY feed_id"
        ).fetchall()
        return {r["feed_id"]: r["cnt"] for r in rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# OPML import / export
# ---------------------------------------------------------------------------

def import_opml(feeds_list: list[dict]) -> int:
    added = 0
    conn = get_connection()
    try:
        for f in feeds_list:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO feeds (name, url, category, date_added) VALUES (?,?,?,?)",
                    (f["name"], f["url"], f.get("category", "Importé"), datetime.now().isoformat()),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    added += 1
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()
    return added
