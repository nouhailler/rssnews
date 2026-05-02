import os
from datetime import datetime

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")


class _Conn:
    """Wrapper psycopg2 → expose conn.execute() comme sqlite3."""
    def __init__(self, pg):
        self._pg = pg

    def execute(self, sql, params=None):
        cur = self._pg.cursor()
        cur.execute(sql, params)
        return cur

    def cursor(self):
        return self._pg.cursor()

    def commit(self):
        self._pg.commit()

    def close(self):
        self._pg.close()


def get_connection() -> _Conn:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL est requis (variable d'environnement).")
    pg = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return _Conn(pg)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    for stmt in [
        """CREATE TABLE IF NOT EXISTS users (
            id            SERIAL PRIMARY KEY,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at    TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS feeds (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            url         TEXT NOT NULL,
            category    TEXT NOT NULL DEFAULT 'Général',
            date_added  TEXT NOT NULL,
            last_fetch  TEXT,
            fetch_error TEXT,
            active      INTEGER NOT NULL DEFAULT 1,
            UNIQUE(user_id, url)
        )""",
        """CREATE TABLE IF NOT EXISTS articles (
            id             SERIAL PRIMARY KEY,
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
        )""",
        "CREATE INDEX IF NOT EXISTS idx_feeds_user        ON feeds(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_articles_feed     ON articles(feed_id)",
        "CREATE INDEX IF NOT EXISTS idx_articles_read     ON articles(read_status)",
        "CREATE INDEX IF NOT EXISTS idx_articles_favorite ON articles(favorite)",
        "CREATE INDEX IF NOT EXISTS idx_articles_date     ON articles(published_date DESC)",
    ]:
        cur.execute(stmt)
    conn.commit()
    conn.close()
    _migrate_if_needed()


def _migrate_if_needed():
    """Ajoute user_id si absent (migration depuis schéma pré-auth)."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_name='feeds' AND column_name='user_id'"""
        ).fetchone()
        if row:
            return
        conn.execute(
            "ALTER TABLE feeds ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_feeds_user ON feeds(user_id)"
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# UTILISATEURS
# ---------------------------------------------------------------------------

def create_user(username: str, password_hash: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (%s, %s, %s) RETURNING id",
            (username, password_hash, datetime.now().isoformat()),
        ).fetchone()
        conn.commit()
        return row["id"]
    finally:
        conn.close()


def get_user_by_username(username: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE username=%s", (username,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, created_at FROM users WHERE id=%s", (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count_users() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
    finally:
        conn.close()


def get_first_user_id() -> int | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def has_orphan_feeds() -> bool:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS cnt FROM feeds WHERE user_id IS NULL"
        ).fetchone()["cnt"] > 0
    finally:
        conn.close()


def assign_orphan_feeds(user_id: int):
    conn = get_connection()
    try:
        conn.execute("UPDATE feeds SET user_id=%s WHERE user_id IS NULL", (user_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# FLUX (feeds)
# ---------------------------------------------------------------------------

def add_feed(user_id: int, name: str, url: str, category: str = "Général") -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "INSERT INTO feeds (user_id, name, url, category, date_added) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (user_id, name, url, category, datetime.now().isoformat()),
        ).fetchone()
        conn.commit()
        return row["id"]
    finally:
        conn.close()


def update_feed(feed_id: int, name: str, url: str, category: str):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE feeds SET name=%s, url=%s, category=%s WHERE id=%s",
            (name, url, category, feed_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_feed(feed_id: int):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM feeds WHERE id=%s", (feed_id,))
        conn.commit()
    finally:
        conn.close()


def set_feed_active(feed_id: int, active: bool):
    conn = get_connection()
    try:
        conn.execute("UPDATE feeds SET active=%s WHERE id=%s", (1 if active else 0, feed_id))
        conn.commit()
    finally:
        conn.close()


def set_feed_fetch_result(feed_id: int, error: str | None = None):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE feeds SET last_fetch=%s, fetch_error=%s WHERE id=%s",
            (datetime.now().isoformat(), error, feed_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_feeds(user_id: int | None = None) -> list[dict]:
    conn = get_connection()
    try:
        if user_id is not None:
            rows = conn.execute(
                "SELECT * FROM feeds WHERE user_id=%s ORDER BY category, name", (user_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM feeds ORDER BY category, name").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_feed(feed_id: int, user_id: int | None = None) -> dict | None:
    conn = get_connection()
    try:
        if user_id is not None:
            row = conn.execute(
                "SELECT * FROM feeds WHERE id=%s AND user_id=%s", (feed_id, user_id)
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM feeds WHERE id=%s", (feed_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_categories(user_id: int) -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT category FROM feeds WHERE user_id=%s ORDER BY category",
            (user_id,),
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
        cur = conn.execute(
            """INSERT INTO articles
                (feed_id, title, link, summary, content, author, published_date, fetch_date)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (feed_id, link) DO NOTHING""",
            (feed_id, title, link, summary, content, author,
             published_date, datetime.now().isoformat()),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_articles(
    user_id: int,
    feed_id: int | None = None,
    only_unread: bool = False,
    only_favorites: bool = False,
    search: str = "",
    limit: int = 500,
) -> list[dict]:
    conditions = ["f.user_id = %s"]
    params: list = [user_id]

    if feed_id is not None:
        conditions.append("a.feed_id = %s")
        params.append(feed_id)

    if only_unread:
        conditions.append("a.read_status = 0")

    if only_favorites:
        conditions.append("a.favorite = 1")

    if search:
        conditions.append("(a.title ILIKE %s OR a.summary ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like])

    where = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT a.*, f.name AS feed_name, f.category
        FROM articles a
        JOIN feeds f ON f.id = a.feed_id
        {where}
        ORDER BY
            CASE WHEN a.published_date IS NULL OR a.published_date = '' THEN a.fetch_date
                 ELSE a.published_date END DESC
        LIMIT %s
    """
    params.append(limit)

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_article(article_id: int, user_id: int | None = None) -> dict | None:
    conn = get_connection()
    try:
        if user_id is not None:
            row = conn.execute(
                """SELECT a.*, f.name AS feed_name
                   FROM articles a JOIN feeds f ON f.id=a.feed_id
                   WHERE a.id=%s AND f.user_id=%s""",
                (article_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT a.*, f.name AS feed_name FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE a.id=%s",
                (article_id,),
            ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_article_read(article_id: int, read: bool):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE articles SET read_status=%s WHERE id=%s",
            (1 if read else 0, article_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_article_favorite(article_id: int, favorite: bool):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE articles SET favorite=%s WHERE id=%s",
            (1 if favorite else 0, article_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_all_read(feed_id: int | None = None, user_id: int | None = None):
    conn = get_connection()
    try:
        if feed_id is not None and user_id is not None:
            conn.execute(
                """UPDATE articles SET read_status=1
                   WHERE feed_id=%s
                   AND feed_id IN (SELECT id FROM feeds WHERE user_id=%s)""",
                (feed_id, user_id),
            )
        elif feed_id is not None:
            conn.execute("UPDATE articles SET read_status=1 WHERE feed_id=%s", (feed_id,))
        elif user_id is not None:
            conn.execute(
                "UPDATE articles SET read_status=1 WHERE feed_id IN (SELECT id FROM feeds WHERE user_id=%s)",
                (user_id,),
            )
        else:
            conn.execute("UPDATE articles SET read_status=1")
        conn.commit()
    finally:
        conn.close()


def get_unread_counts_by_feed(user_id: int | None = None) -> dict[int, int]:
    conn = get_connection()
    try:
        if user_id is not None:
            rows = conn.execute(
                """SELECT a.feed_id, COUNT(*) AS cnt
                   FROM articles a JOIN feeds f ON f.id=a.feed_id
                   WHERE a.read_status=0 AND f.user_id=%s
                   GROUP BY a.feed_id""",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT feed_id, COUNT(*) AS cnt FROM articles WHERE read_status=0 GROUP BY feed_id"
            ).fetchall()
        return {r["feed_id"]: r["cnt"] for r in rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# OPML import / export
# ---------------------------------------------------------------------------

def import_opml(feeds_list: list[dict], user_id: int) -> int:
    added = 0
    conn = get_connection()
    try:
        for f in feeds_list:
            try:
                cur = conn.execute(
                    """INSERT INTO feeds (user_id, name, url, category, date_added)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (user_id, url) DO NOTHING""",
                    (user_id, f["name"], f["url"], f.get("category", "Importé"),
                     datetime.now().isoformat()),
                )
                if cur.rowcount > 0:
                    added += 1
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()
    return added
