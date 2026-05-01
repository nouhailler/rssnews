"""
Module de récupération et d'analyse des flux RSS/Atom.

C'est le cœur de l'application. Il gère :
  - le téléchargement HTTP avec timeout et User-Agent correct
  - la détection et l'analyse des formats RSS 0.9x / RSS 2.0 / Atom
  - des messages d'erreur clairs et détaillés pour chaque type de problème
  - la déduplication des articles avant insertion en base
"""

from __future__ import annotations

import socket
import ssl
import logging
from dataclasses import dataclass, field
from typing import Callable
from datetime import datetime

import feedparser
import requests
import requests.exceptions

import database as db

logger = logging.getLogger(__name__)

# Délai maximum pour une requête HTTP (connexion + lecture)
REQUEST_TIMEOUT = (10, 20)   # (connect_timeout, read_timeout) en secondes

# User-Agent présenté aux serveurs
USER_AGENT = (
    "RSSReader/1.0 (Linux; Python; compatible Feedreader) "
    "+https://github.com/rss-reader"
)


# ---------------------------------------------------------------------------
# Structures de résultat
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    """Résultat de la récupération d'un flux."""
    feed_id: int
    feed_name: str
    success: bool
    new_articles: int = 0
    error_code: str = ""          # code court machine-lisible
    error_message: str = ""       # message lisible par l'utilisateur
    error_detail: str = ""        # détail technique (pour les logs)


@dataclass
class FetchReport:
    """Rapport global d'une session de rafraîchissement."""
    results: list[FetchResult] = field(default_factory=list)

    @property
    def total_new(self) -> int:
        return sum(r.new_articles for r in self.results)

    @property
    def failures(self) -> list[FetchResult]:
        return [r for r in self.results if not r.success]

    @property
    def successes(self) -> list[FetchResult]:
        return [r for r in self.results if r.success]


# ---------------------------------------------------------------------------
# Traduction des codes d'erreur HTTP
# ---------------------------------------------------------------------------

_HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "Requête invalide (400 Bad Request) — l'URL du flux est peut-être mal formée.",
    401: "Accès non autorisé (401 Unauthorized) — ce flux nécessite une authentification.",
    403: "Accès interdit (403 Forbidden) — le serveur refuse l'accès à ce flux.",
    404: "Flux introuvable (404 Not Found) — l'URL n'existe plus ou a changé.",
    408: "Délai d'attente dépassé côté serveur (408 Request Timeout).",
    410: "Flux supprimé définitivement (410 Gone) — pensez à le supprimer de votre liste.",
    429: "Trop de requêtes (429 Too Many Requests) — le serveur limite l'accès, réessayez plus tard.",
    500: "Erreur interne du serveur (500 Internal Server Error) — problème côté serveur, réessayez plus tard.",
    502: "Passerelle incorrecte (502 Bad Gateway) — le serveur est peut-être temporairement indisponible.",
    503: "Service indisponible (503 Service Unavailable) — le serveur est surchargé ou en maintenance.",
    504: "Délai de la passerelle dépassé (504 Gateway Timeout) — le serveur met trop de temps à répondre.",
}


def _http_error_message(status_code: int) -> str:
    return _HTTP_ERROR_MESSAGES.get(
        status_code,
        f"Erreur HTTP {status_code} — réponse inattendue du serveur.",
    )


# ---------------------------------------------------------------------------
# Récupération d'un flux
# ---------------------------------------------------------------------------

def fetch_feed(feed: dict) -> FetchResult:
    """
    Télécharge et analyse un flux RSS/Atom.

    Paramètre
    ---------
    feed : dict  (lignes de la table 'feeds')

    Retourne
    --------
    FetchResult avec les métriques et un message d'erreur clair si besoin.
    """
    feed_id   = feed["id"]
    feed_name = feed["name"]
    url       = feed["url"].strip()

    result = FetchResult(feed_id=feed_id, feed_name=feed_name, success=False)

    # --- Vérification basique de l'URL ----------------------------------
    if not url.startswith(("http://", "https://")):
        result.error_code    = "INVALID_URL"
        result.error_message = (
            f"URL invalide : « {url} »\n"
            "L'URL doit commencer par http:// ou https://."
        )
        db.set_feed_fetch_result(feed_id, result.error_message)
        logger.warning("[%s] URL invalide : %s", feed_name, url)
        return result

    # --- Téléchargement HTTP --------------------------------------------
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
            verify=True,         # vérification SSL activée
        )
        response.raise_for_status()

    except requests.exceptions.SSLError as exc:
        result.error_code    = "SSL_ERROR"
        result.error_message = (
            f"Erreur de certificat SSL pour « {url} ».\n"
            "Le certificat du serveur est invalide, expiré ou auto-signé.\n"
            "Conseil : vérifiez que l'URL est correcte et que le site est accessible."
        )
        result.error_detail = str(exc)
        db.set_feed_fetch_result(feed_id, result.error_message)
        logger.warning("[%s] SSL error : %s", feed_name, exc)
        return result

    except requests.exceptions.ConnectionError as exc:
        # On distingue les erreurs DNS des erreurs réseau génériques
        msg_lower = str(exc).lower()
        if "name or service not known" in msg_lower or "nodename nor servname" in msg_lower or "getaddrinfo" in msg_lower:
            result.error_code    = "DNS_ERROR"
            result.error_message = (
                f"Impossible de résoudre le nom de domaine pour « {url} ».\n"
                "Vérifiez :\n"
                "  • que l'adresse est correctement orthographiée\n"
                "  • que votre connexion Internet fonctionne\n"
                "  • que le site existe toujours"
            )
        elif "connection refused" in msg_lower:
            result.error_code    = "CONNECTION_REFUSED"
            result.error_message = (
                f"Connexion refusée par le serveur « {url} ».\n"
                "Le serveur distant n'accepte pas les connexions sur ce port."
            )
        elif "network is unreachable" in msg_lower or "no route to host" in msg_lower:
            result.error_code    = "NETWORK_UNREACHABLE"
            result.error_message = (
                f"Réseau inaccessible pour « {url} ».\n"
                "Vérifiez votre connexion Internet."
            )
        else:
            result.error_code    = "CONNECTION_ERROR"
            result.error_message = (
                f"Impossible de se connecter à « {url} ».\n"
                f"Détail : {_short_error(exc)}"
            )
        result.error_detail = str(exc)
        db.set_feed_fetch_result(feed_id, result.error_message)
        logger.warning("[%s] Connection error : %s", feed_name, exc)
        return result

    except requests.exceptions.Timeout:
        result.error_code    = "TIMEOUT"
        result.error_message = (
            f"Le serveur « {url} » n'a pas répondu dans les délais impartis\n"
            f"(connexion : {REQUEST_TIMEOUT[0]} s, lecture : {REQUEST_TIMEOUT[1]} s).\n"
            "Le serveur est peut-être surchargé. Réessayez plus tard."
        )
        db.set_feed_fetch_result(feed_id, result.error_message)
        logger.warning("[%s] Timeout", feed_name)
        return result

    except requests.exceptions.TooManyRedirects as exc:
        result.error_code    = "TOO_MANY_REDIRECTS"
        result.error_message = (
            f"Boucle de redirections détectée pour « {url} ».\n"
            "L'URL redirige trop de fois. Vérifiez l'adresse du flux."
        )
        result.error_detail = str(exc)
        db.set_feed_fetch_result(feed_id, result.error_message)
        logger.warning("[%s] Too many redirects", feed_name)
        return result

    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else 0
        result.error_code    = f"HTTP_{code}"
        result.error_message = _http_error_message(code)
        result.error_detail  = str(exc)
        db.set_feed_fetch_result(feed_id, result.error_message)
        logger.warning("[%s] HTTP error %d", feed_name, code)
        return result

    except requests.exceptions.RequestException as exc:
        result.error_code    = "REQUEST_ERROR"
        result.error_message = (
            f"Erreur inattendue lors du téléchargement de « {url} ».\n"
            f"Détail : {_short_error(exc)}"
        )
        result.error_detail = str(exc)
        db.set_feed_fetch_result(feed_id, result.error_message)
        logger.error("[%s] RequestException : %s", feed_name, exc)
        return result

    # --- Vérification du Content-Type -----------------------------------
    content_type = response.headers.get("Content-Type", "").lower()
    _acceptable_types = (
        "application/rss+xml",
        "application/atom+xml",
        "application/xml",
        "text/xml",
        "application/x-rss+xml",
        "application/rdf+xml",
        "text/html",   # certains serveurs renvoient text/html pour des flux valides
    )
    if content_type and not any(t in content_type for t in _acceptable_types):
        logger.debug(
            "[%s] Content-Type inhabituel : %s (on tente quand même le parsing)",
            feed_name, content_type,
        )

    # --- Analyse (parsing) du contenu RSS/Atom --------------------------
    raw_content = response.content
    if not raw_content.strip():
        result.error_code    = "EMPTY_RESPONSE"
        result.error_message = (
            f"Le serveur a retourné une réponse vide pour « {url} ».\n"
            "Le flux est peut-être temporairement indisponible."
        )
        db.set_feed_fetch_result(feed_id, result.error_message)
        logger.warning("[%s] Réponse vide", feed_name)
        return result

    parsed = feedparser.parse(raw_content)

    # feedparser signale les erreurs de parsing via 'bozo'
    if parsed.bozo:
        bozo_exc = parsed.get("bozo_exception")
        # Certains flux valides déclenchent bozo (encodage, etc.) mais contiennent
        # quand même des entrées exploitables — on les accepte avec un warning.
        if not parsed.entries:
            result.error_code    = "PARSE_ERROR"
            result.error_message = _parse_error_message(url, bozo_exc)
            result.error_detail  = str(bozo_exc)
            db.set_feed_fetch_result(feed_id, result.error_message)
            logger.warning("[%s] Parse error (bozo) : %s", feed_name, bozo_exc)
            return result
        else:
            logger.debug(
                "[%s] Bozo flag mais %d entrées disponibles : %s",
                feed_name, len(parsed.entries), bozo_exc,
            )

    # Vérification minimale : le feed doit avoir au moins une entrée OU un titre
    if not parsed.entries and not parsed.feed.get("title"):
        result.error_code    = "NOT_A_FEED"
        result.error_message = (
            f"L'URL « {url} » ne semble pas être un flux RSS ou Atom valide.\n"
            "Conseils :\n"
            "  • Vérifiez que l'URL pointe bien vers le fichier RSS (souvent /feed, /rss ou /atom)\n"
            "  • Certains sites proposent un lien RSS dans le code source de leur page\n"
            "  • Essayez d'ajouter /feed ou /rss à l'URL du site"
        )
        db.set_feed_fetch_result(feed_id, result.error_message)
        logger.warning("[%s] Aucune entrée ni titre de feed", feed_name)
        return result

    # --- Insertion des nouveaux articles --------------------------------
    new_count = 0
    for entry in parsed.entries:
        title = _clean_text(entry.get("title", "(sans titre)"))
        link  = entry.get("link", "") or entry.get("id", "")

        if not link:
            # Article sans lien — on le saute, impossible de le dédupliquer
            continue

        summary = _clean_text(
            entry.get("summary", "")
            or entry.get("description", "")
        )
        content = _extract_content(entry)
        author  = _clean_text(entry.get("author", ""))
        pub_date = _parse_date(entry)

        inserted = db.upsert_article(
            feed_id=feed_id,
            title=title,
            link=link,
            summary=summary,
            content=content,
            author=author,
            published_date=pub_date,
        )
        if inserted:
            new_count += 1

    # --- Succès ---------------------------------------------------------
    db.set_feed_fetch_result(feed_id, None)   # efface l'erreur précédente
    result.success      = True
    result.new_articles = new_count
    logger.info("[%s] OK — %d nouveaux articles", feed_name, new_count)
    return result


# ---------------------------------------------------------------------------
# Récupération de tous les flux actifs
# ---------------------------------------------------------------------------

def fetch_all_feeds(
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> FetchReport:
    """
    Récupère tous les flux actifs en séquence.

    Le callback reçoit (current, total, feed_name) pour afficher la progression.
    """
    feeds = [f for f in db.get_all_feeds() if f["active"]]
    report = FetchReport()
    total = len(feeds)

    for i, feed in enumerate(feeds, start=1):
        if progress_callback:
            progress_callback(i, total, feed["name"])
        result = fetch_feed(feed)
        report.results.append(result)

    return report


def fetch_single_feed(feed_id: int) -> FetchResult:
    """Raccourci pour rafraîchir un seul flux."""
    feed = db.get_feed(feed_id)
    if feed is None:
        return FetchResult(
            feed_id=feed_id,
            feed_name="Inconnu",
            success=False,
            error_code="NOT_FOUND",
            error_message=f"Flux id={feed_id} introuvable en base de données.",
        )
    return fetch_feed(feed)


# ---------------------------------------------------------------------------
# Détection automatique du flux RSS d'une page web
# ---------------------------------------------------------------------------

def discover_feed_url(page_url: str) -> tuple[str, str]:
    """
    Tente de trouver l'URL d'un flux RSS/Atom dans une page HTML.

    Retourne (feed_url, feed_title).
    Lève ValueError si aucun flux n'est trouvé.
    """
    try:
        response = requests.get(
            page_url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise ValueError(
            f"Impossible de charger la page « {page_url} » : {_short_error(exc)}"
        ) from exc

    # Recherche de liens <link rel="alternate" type="application/rss+xml">
    from html.parser import HTMLParser

    class LinkFinder(HTMLParser):
        def __init__(self):
            super().__init__()
            self.feeds: list[tuple[str, str]] = []

        def handle_starttag(self, tag, attrs):
            if tag != "link":
                return
            attrs_dict = dict(attrs)
            rel  = attrs_dict.get("rel", "")
            type_ = attrs_dict.get("type", "")
            href  = attrs_dict.get("href", "")
            if "alternate" in rel and ("rss" in type_ or "atom" in type_) and href:
                title = attrs_dict.get("title", href)
                self.feeds.append((href, title))

    finder = LinkFinder()
    try:
        finder.feed(response.text[:50_000])   # on ne parse que le début
    except Exception:
        pass

    if not finder.feeds:
        raise ValueError(
            f"Aucun flux RSS ou Atom trouvé dans la page « {page_url} ».\n"
            "Essayez d'entrer directement l'URL du fichier RSS."
        )

    href, title = finder.feeds[0]
    # L'URL peut être relative
    if href.startswith("/"):
        from urllib.parse import urlparse
        parsed = urlparse(page_url)
        href = f"{parsed.scheme}://{parsed.netloc}{href}"
    elif not href.startswith("http"):
        from urllib.parse import urljoin
        href = urljoin(page_url, href)

    return href, title


# ---------------------------------------------------------------------------
# Import OPML
# ---------------------------------------------------------------------------

def parse_opml(file_path: str) -> list[dict]:
    """
    Parse un fichier OPML et retourne une liste de flux.
    Chaque entrée : {'name': str, 'url': str, 'category': str}
    """
    import xml.etree.ElementTree as ET

    try:
        tree = ET.parse(file_path)
    except ET.ParseError as exc:
        raise ValueError(f"Fichier OPML invalide : {exc}") from exc

    root = tree.getroot()
    feeds: list[dict] = []
    current_category = "Importé"

    def _walk(node, category):
        for outline in node.findall("outline"):
            xml_url = outline.get("xmlUrl", "")
            title   = outline.get("title") or outline.get("text", "")
            if xml_url:
                feeds.append({"name": title, "url": xml_url, "category": category})
            else:
                # C'est un dossier/catégorie
                sub_cat = title or category
                _walk(outline, sub_cat)

    body = root.find("body")
    if body is not None:
        _walk(body, current_category)
    else:
        _walk(root, current_category)

    return feeds


# ---------------------------------------------------------------------------
# Export OPML
# ---------------------------------------------------------------------------

def export_opml(file_path: str):
    """Exporte tous les flux vers un fichier OPML."""
    import xml.etree.ElementTree as ET

    root = ET.Element("opml", version="2.0")
    head = ET.SubElement(root, "head")
    ET.SubElement(head, "title").text = "RSS Reader — Export OPML"
    ET.SubElement(head, "dateCreated").text = datetime.now().strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )
    body = ET.SubElement(root, "body")

    feeds   = db.get_all_feeds()
    by_cat: dict[str, list] = {}
    for f in feeds:
        by_cat.setdefault(f["category"], []).append(f)

    for cat, cat_feeds in sorted(by_cat.items()):
        folder = ET.SubElement(body, "outline", text=cat, title=cat)
        for f in cat_feeds:
            ET.SubElement(
                folder,
                "outline",
                type="rss",
                text=f["name"],
                title=f["name"],
                xmlUrl=f["url"],
            )

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(file_path, encoding="utf-8", xml_declaration=True)


# ---------------------------------------------------------------------------
# Helpers privés
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Supprime les espaces superflus."""
    if not text:
        return ""
    return " ".join(text.split())


def _extract_content(entry) -> str:
    """Extrait le contenu HTML le plus riche disponible dans une entrée."""
    # feedparser normalise le contenu dans entry.content (liste)
    content_list = entry.get("content", [])
    for c in content_list:
        if c.get("type", "") in ("text/html", "application/xhtml+xml"):
            return c.get("value", "")
    if content_list:
        return content_list[0].get("value", "")
    # Fallback sur summary_detail
    sd = entry.get("summary_detail")
    if sd:
        return sd.get("value", "")
    return entry.get("summary", "")


def _parse_date(entry) -> str:
    """Extrait et normalise la date de publication."""
    # feedparser fournit published_parsed ou updated_parsed (time.struct_time)
    import time
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entry.get(attr)
        if t:
            try:
                dt = datetime(*t[:6])
                return dt.isoformat()
            except Exception:
                pass
    # Fallback sur la chaîne brute
    return entry.get("published", "") or entry.get("updated", "") or ""


def _parse_error_message(url: str, exc) -> str:
    """Construit un message d'erreur lisible pour une erreur de parsing feedparser."""
    exc_str = str(exc) if exc else "erreur inconnue"
    exc_lower = exc_str.lower()

    if "not well-formed" in exc_lower or "syntax error" in exc_lower:
        msg = (
            "Le XML du flux est mal formé et ne peut pas être analysé.\n"
            "Le flux contient probablement des caractères spéciaux non encodés\n"
            "ou une structure XML invalide."
        )
    elif "encoding" in exc_lower or "codec" in exc_lower:
        msg = (
            "Problème d'encodage du flux.\n"
            "Le fichier déclare un encodage qui ne correspond pas à son contenu."
        )
    elif "charref" in exc_lower or "entity" in exc_lower:
        msg = (
            "Le flux contient des entités HTML ou XML non reconnues."
        )
    else:
        msg = (
            f"Impossible d'analyser le contenu de « {url} ».\n"
            f"Détail : {exc_str[:200]}"
        )

    return msg


def _short_error(exc: Exception) -> str:
    """Retourne un message d'erreur court sans stacktrace."""
    msg = str(exc)
    # Supprime le chemin Python interne s'il est présent
    if "\n" in msg:
        msg = msg.split("\n")[-1].strip() or msg.split("\n")[0].strip()
    return msg[:300]
