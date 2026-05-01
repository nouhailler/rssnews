import os
import tempfile
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

import database as db
import rss_fetcher as fetcher
import auth

app = FastAPI(title="RSS Reader API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db.init_db()
    # Assign feeds with no user_id (migrated from pre-auth schema) to a default user.
    if db.has_orphan_feeds():
        if db.count_users() == 0:
            default_pwd = os.environ.get("DEFAULT_ADMIN_PASSWORD", "changeme123")
            user_id = db.create_user("admin", auth.hash_password(default_pwd))
        else:
            user_id = db.get_first_user_id()
        db.assign_orphan_feeds(user_id)


@app.get("/")
def root():
    return {"status": "ok", "app": "RSS Reader API"}


# ---------------------------------------------------------------------------
# Modèles Pydantic
# ---------------------------------------------------------------------------

class FeedIn(BaseModel):
    name: str
    url: str
    category: str = "Général"


class ActiveIn(BaseModel):
    active: bool


class DiscoverIn(BaseModel):
    url: str


class ArticlePatch(BaseModel):
    read_status: Optional[bool] = None
    favorite: Optional[bool] = None


class RegisterIn(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/auth/register", status_code=201)
def register(body: RegisterIn):
    if len(body.username) < 3:
        raise HTTPException(400, "Le nom d'utilisateur doit faire au moins 3 caractères.")
    if len(body.password) < 6:
        raise HTTPException(400, "Le mot de passe doit faire au moins 6 caractères.")
    if db.get_user_by_username(body.username):
        raise HTTPException(409, "Ce nom d'utilisateur est déjà pris.")
    user_id = db.create_user(body.username, auth.hash_password(body.password))
    token = auth.create_token(user_id, body.username)
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": user_id, "username": body.username}}


@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = db.get_user_by_username(form.username)
    if not user or not auth.verify_password(form.password, user["password_hash"]):
        raise HTTPException(401, "Nom d'utilisateur ou mot de passe incorrect.")
    token = auth.create_token(user["id"], user["username"])
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": user["id"], "username": user["username"]}}


@app.get("/auth/me")
def me(current_user: dict = Depends(auth.get_current_user)):
    user = db.get_user_by_id(current_user["id"])
    if not user:
        raise HTTPException(404, "Utilisateur introuvable.")
    return user


# ---------------------------------------------------------------------------
# Flux — routes LITTÉRALES en premier
# ---------------------------------------------------------------------------

@app.get("/feeds")
def list_feeds(current_user: dict = Depends(auth.get_current_user)):
    feeds = db.get_all_feeds(user_id=current_user["id"])
    unread = db.get_unread_counts_by_feed(user_id=current_user["id"])
    for f in feeds:
        f["unread_count"] = unread.get(f["id"], 0)
    return feeds


@app.post("/feeds", status_code=201)
def create_feed(body: FeedIn, current_user: dict = Depends(auth.get_current_user)):
    try:
        feed_id = db.add_feed(current_user["id"], body.name, body.url, body.category)
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(409, "Ce flux existe déjà dans votre liste.")
        raise HTTPException(500, str(e))
    feed = db.get_feed(feed_id)
    feed["unread_count"] = 0
    return feed


@app.post("/feeds/discover")
def discover_feed(body: DiscoverIn, current_user: dict = Depends(auth.get_current_user)):
    try:
        feed_url, feed_title = fetcher.discover_feed_url(body.url)
        return {"url": feed_url, "title": feed_title}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/feeds/{feed_id}")
def get_feed(feed_id: int, current_user: dict = Depends(auth.get_current_user)):
    feed = db.get_feed(feed_id, user_id=current_user["id"])
    if not feed:
        raise HTTPException(404, "Flux introuvable.")
    unread = db.get_unread_counts_by_feed(user_id=current_user["id"])
    feed["unread_count"] = unread.get(feed_id, 0)
    return feed


@app.put("/feeds/{feed_id}")
def update_feed(feed_id: int, body: FeedIn, current_user: dict = Depends(auth.get_current_user)):
    if not db.get_feed(feed_id, user_id=current_user["id"]):
        raise HTTPException(404, "Flux introuvable.")
    db.update_feed(feed_id, body.name, body.url, body.category)
    feed = db.get_feed(feed_id)
    unread = db.get_unread_counts_by_feed(user_id=current_user["id"])
    feed["unread_count"] = unread.get(feed_id, 0)
    return feed


@app.delete("/feeds/{feed_id}", status_code=204)
def delete_feed(feed_id: int, current_user: dict = Depends(auth.get_current_user)):
    if not db.get_feed(feed_id, user_id=current_user["id"]):
        raise HTTPException(404, "Flux introuvable.")
    db.delete_feed(feed_id)


@app.patch("/feeds/{feed_id}/active")
def set_feed_active(feed_id: int, body: ActiveIn, current_user: dict = Depends(auth.get_current_user)):
    if not db.get_feed(feed_id, user_id=current_user["id"]):
        raise HTTPException(404, "Flux introuvable.")
    db.set_feed_active(feed_id, body.active)
    return db.get_feed(feed_id)


@app.post("/feeds/{feed_id}/refresh")
def refresh_feed(feed_id: int, current_user: dict = Depends(auth.get_current_user)):
    if not db.get_feed(feed_id, user_id=current_user["id"]):
        raise HTTPException(404, "Flux introuvable.")
    result = fetcher.fetch_single_feed(feed_id)
    return {
        "success": result.success,
        "new_articles": result.new_articles,
        "error_message": result.error_message,
    }


@app.post("/refresh")
def refresh_all(current_user: dict = Depends(auth.get_current_user)):
    """Rafraîchit tous les flux actifs de l'utilisateur."""
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
# Articles — route littérale AVANT les routes paramétrées
# ---------------------------------------------------------------------------

@app.get("/articles")
def list_articles(
    feed_id: Optional[int] = Query(None),
    smart: Optional[str] = Query(None),
    search: str = Query(""),
    limit: int = Query(500, le=2000),
    current_user: dict = Depends(auth.get_current_user),
):
    only_unread    = smart == "unread"
    only_favorites = smart == "favorites"
    return db.get_articles(
        user_id=current_user["id"],
        feed_id=feed_id,
        only_unread=only_unread,
        only_favorites=only_favorites,
        search=search,
        limit=limit,
    )


@app.post("/articles/mark-all-read")
def mark_all_read(
    feed_id: Optional[int] = Query(None),
    current_user: dict = Depends(auth.get_current_user),
):
    db.mark_all_read(feed_id=feed_id, user_id=current_user["id"])
    return {"ok": True}


@app.get("/articles/{article_id}")
def get_article(article_id: int, current_user: dict = Depends(auth.get_current_user)):
    art = db.get_article(article_id, user_id=current_user["id"])
    if not art:
        raise HTTPException(404, "Article introuvable.")
    return art


@app.patch("/articles/{article_id}")
def patch_article(article_id: int, body: ArticlePatch, current_user: dict = Depends(auth.get_current_user)):
    art = db.get_article(article_id, user_id=current_user["id"])
    if not art:
        raise HTTPException(404, "Article introuvable.")
    if body.read_status is not None:
        db.set_article_read(article_id, body.read_status)
    if body.favorite is not None:
        db.set_article_favorite(article_id, body.favorite)
    return db.get_article(article_id)


# ---------------------------------------------------------------------------
# OPML import / export
# ---------------------------------------------------------------------------

@app.post("/opml/import")
def import_opml(
    file: UploadFile = File(...),
    current_user: dict = Depends(auth.get_current_user),
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".opml") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        feeds = fetcher.parse_opml(tmp_path)
        added = db.import_opml(feeds, user_id=current_user["id"])
        return {"found": len(feeds), "added": added}
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        os.unlink(tmp_path)


@app.get("/opml/export")
def export_opml(current_user: dict = Depends(auth.get_current_user)):
    tmp_path = tempfile.mktemp(suffix=".opml")
    fetcher.export_opml(tmp_path, user_id=current_user["id"])
    return FileResponse(
        tmp_path,
        media_type="application/xml",
        filename="flux_rss.opml",
        background=None,
    )
