"""
Nettoyage de texte HTML/RSS pour la synthèse vocale.

Utilise BeautifulSoup si disponible, sinon un fallback regex.
"""

from __future__ import annotations

import re


def clean_to_text(html_or_text: str) -> str:
    """
    Convertit du HTML ou du texte RSS en texte brut propre pour TTS.

    - Supprime les balises HTML
    - Supprime les URLs brutes (peu intelligibles à l'oral)
    - Normalise les espaces et sauts de ligne
    """
    if not html_or_text:
        return ""

    text = _strip_html(html_or_text)

    # Supprime les URLs brutes (http://... ou https://...)
    text = re.sub(r"https?://\S+", "", text)

    # Normalise les espaces
    text = re.sub(r"[ \t]+", " ", text)
    # Réduit les sauts de ligne multiples
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" +\n", "\n", text)

    return text.strip()


def _strip_html(html: str) -> str:
    """Retire les balises HTML du texte."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Supprime les éléments non-textuels
        for tag in soup(["script", "style", "img", "figure", "figcaption", "iframe"]):
            tag.decompose()
        # Conserve les sauts de ligne pour <p>, <br>, <li>
        for tag in soup.find_all(["p", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
            tag.insert_before("\n")
        return soup.get_text(separator=" ", strip=True)
    except ImportError:
        # Fallback : regex simple
        html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html,
                      flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"</(p|div|li|h[1-6])>", "\n", html, flags=re.IGNORECASE)
        return re.sub(r"<[^>]+>", " ", html)
