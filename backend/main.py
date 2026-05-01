"""
API REST RSS Reader — FastAPI
"""

import os
import tempfile
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import database as db
import rss_fetcher as fetcher

app = FastAPI(title="RSS Reader API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db.init_db()


# ---------------------------------------------------------------------------
# Flux (feeds)
# ---------------------------------------------------------------------------

class FeedIn(BaseModel):
    name: str
    url: str
    category: str = "Général"


class ActiveIn(BaseModel):
    active: bool


@app.get("/feeds")
def list_feeds():
    feeds = db.get_all_feeds()
    unread = db.get_unread_counts_by_feed()
    for f in feeds:
        f["unread_count"] = unread.get(f["id"], 0)
    return feeds


@app.post("/feeds", status_code=201)
def create_feed(body: FeedIn):
    try:
        feed_id = db.add_feed(body.name, body.url, body.category)
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(409, "Ce flux existe déjà dans votre liste.")
        raise HTTPException(500, str(e))
    feed = db.get_feed(feed_id)
    feed["unread_count"] = 0
    return feed


@app.put("/feeds/{feed_id}")
def update_feed(feed_id: int, body: FeedIn):
    if not db.get_feed(feed_id):
        raise HTTPException(404, "Flux introuvable.")
    db.update_feed(feed_id, body.name, body.url, body.category)
    feed = db.get_feed(feed_id)
    unread = db.get_unread_counts_by_feed()
    feed["unread_count"] = unread.get(feed_id, 0)
    return feed


@app.delete("/feeds/{feed_id}", status_code=204)
def delete_feed(feed_id: int):
    if not db.get_feed(feed_id):
        raise HTTPException(404, "Flux introuvable.")
    db.delete_feed(feed_id)


@app.patch("/feeds/{feed_id}/active")
def set_feed_active(feed_id: int, body: ActiveIn):
    if not db.get_feed(feed_id):
        raise HTTPException(404, "Flux introuvable.")
    db.set_feed_active(feed_id, body.active)
    return db.get_feed(feed_id)


@app.post("/feeds/{feed_id}/refresh")
def refresh_feed(feed_id: int):
    if not db.get_feed(feed_id):
        raise HTTPException(404, "Flux introuvable.")
    result = fetcher.fetch_single_feed(feed_id)
    return {
        "success": result.success,
        "new_articles": result.new_articles,
        "error_message": result.error_message,
    }


@app.post("/refresh")
def refresh_all():
    """Rafraîchit tous les flux actifs. Peut prendre du temps selon le nombre de flux."""
    report = fetcher.fetch_all_feeds()
    return {
        "total_new": report.total_new,
        "results": [
            {
                "feed_id": r.feed_id,
                "feed_name": r.feed_name,
                "success": r.success,
                "new_articles": r.new_articles,
                "error_message": r.error_message,
            }
            for r in report.results
        ],
    }


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------

class ArticlePatch(BaseModel):
    read_status: Optional[bool] = None
    favorite: Optional[bool] = None


@app.get("/articles")
def list_articles(
    feed_id: Optional[int] = Query(None),
    smart: Optional[str] = Query(None),
    search: str = Query(""),
    limit: int = Query(500, le=2000),
):
    only_unread    = smart == "unread"
    only_favorites = smart == "favorites"
    return db.get_articles(
        feed_id=feed_id,
        only_unread=only_unread,
        only_favorites=only_favorites,
        search=search,
        limit=limit,
    )


@app.get("/articles/{article_id}")
def get_article(article_id: int):
    art = db.get_article(article_id)
    if not art:
        raise HTTPException(404, "Article introuvable.")
    return art


@app.patch("/articles/{article_id}")
def patch_article(article_id: int, body: ArticlePatch):
    if body.read_status is not None:
        db.set_article_read(article_id, body.read_status)
    if body.favorite is not None:
        db.set_article_favorite(article_id, body.favorite)
    art = db.get_article(article_id)
    if not art:
        raise HTTPException(404, "Article introuvable.")
    return art


@app.post("/articles/mark-all-read")
def mark_all_read(feed_id: Optional[int] = Query(None)):
    db.mark_all_read(feed_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Découverte de flux
# ---------------------------------------------------------------------------

class DiscoverIn(BaseModel):
    url: str


@app.post("/feeds/discover")
def discover_feed(body: DiscoverIn):
    try:
        feed_url, feed_title = fetcher.discover_feed_url(body.url)
        return {"url": feed_url, "title": feed_title}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------------------
# OPML import / export
# ---------------------------------------------------------------------------

@app.post("/opml/import")
def import_opml(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".opml") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        feeds = fetcher.parse_opml(tmp_path)
        added = db.import_opml(feeds)
        return {"found": len(feeds), "added": added}
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        os.unlink(tmp_path)


@app.get("/opml/export")
def export_opml():
    tmp_path = tempfile.mktemp(suffix=".opml")
    fetcher.export_opml(tmp_path)
    return FileResponse(
        tmp_path,
        media_type="application/xml",
        filename="flux_rss.opml",
        background=None,
    )
