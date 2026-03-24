"""
Parser pour les données de ligues FootyStats.
"""

import hashlib
from datetime import datetime
from typing import Any, Optional
from backend.core.logging import get_logger

logger = get_logger(__name__)


def extraire_saisons(data: dict) -> list[dict]:
    """
    Normalise les différentes formes possibles du champ saison
    renvoyées par FootyStats.
    Accepte notamment:
    - une liste `season: [...]`
    - un objet `season: {...}`
    - une enveloppe `season: {data: [...]}`
    - des variantes `seasons` ou `current_season`
    """
    bruts = []
    for cle in ("season", "seasons", "current_season"):
        bruts.extend(_extraire_saisons_depuis_brut(data.get(cle)))

    saisons = []
    deja_vus = set()

    for brut in bruts:
        season_id = brut.get("id") or brut.get("season_id")
        if not season_id:
            continue

        cle = str(season_id)
        if cle in deja_vus:
            continue
        deja_vus.add(cle)

        saison = dict(brut)
        saison["id"] = season_id
        saison["year"] = extraire_annee_saison(saison)
        saison["name"] = formater_nom_saison(saison)
        saisons.append(saison)

    return saisons


def extraire_id_ligue(data: dict) -> Optional[int]:
    """
    Extrait un identifiant de ligue/compétition.
    Si FootyStats ne fournit pas d'ID stable au niveau ligue,
    génère un ID synthétique déterministe à partir du pays et du nom.
    """
    for cle in (
        "id",
        "league_id",
        "competition_id",
        "leagueID",
        "competitionID",
        "leagueId",
        "competitionId",
        "footystats_id",
    ):
        valeur = _coerce_int(data.get(cle))
        if valeur:
            return valeur

    for cle in ("league", "competition", "tournament"):
        valeur = data.get(cle)
        if isinstance(valeur, dict):
            identifiant = extraire_id_ligue(valeur)
            if identifiant:
                return identifiant

    nom = extraire_nom_ligue(data)
    if not nom:
        return None

    return _generer_id_ligue_synthetique(
        country=data.get("country", "Unknown"),
        name=nom,
    )


def extraire_nom_ligue(data: dict) -> str:
    """
    Normalise le nom de ligue pour rester stable même si l'API
    passe de `name` à `league_name` ou change légèrement la forme.
    """
    country = _nettoyer_texte(data.get("country")) or "Unknown"

    nom = (
        _nettoyer_texte(data.get("name"))
        or _nettoyer_texte(data.get("league_name"))
        or _nettoyer_texte(data.get("competition_name"))
        or _nettoyer_texte(data.get("league"))
    )

    if not nom:
        return ""

    if country != "Unknown" and country.lower() not in nom.lower():
        return f"{country} {nom}"
    return nom


def extraire_saison_principale(data: dict) -> Optional[dict]:
    """
    Retourne la saison la plus récente disponible pour une ligue.
    """
    saisons = extraire_saisons(data)
    if not saisons:
        return None
    return max(
        saisons,
        key=lambda saison: (
            saison.get("year", 0),
            int(saison.get("id", 0)),
        ),
    )


def extraire_annee_saison(data: dict) -> int:
    """
    Extrait l'année de début de la saison depuis plusieurs variantes de payload.
    """
    for cle in ("year", "starting_year", "start_year", "name", "season_name"):
        annee = _normaliser_annee(data.get(cle))
        if annee is not None:
            return annee
    return datetime.now().year


def formater_nom_saison(data: dict) -> str:
    """
    Construit un nom de saison lisible même si FootyStats change de forme.
    """
    for cle in ("name", "season_name"):
        valeur = data.get(cle)
        if isinstance(valeur, str) and valeur.strip():
            return valeur.strip()

    valeur_annee = data.get("year")
    digits = "".join(ch for ch in str(valeur_annee) if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}/{digits[4:8]}"

    debut = extraire_annee_saison(data)
    fin = _normaliser_annee(data.get("ending_year") or data.get("end_year"))
    if fin and fin != debut:
        return f"{debut}/{fin}"
    return str(debut)


def parser_ligue(data: dict) -> Optional[dict]:
    """
    Parse une ligue depuis la réponse FootyStats.
    """
    try:
        league_id = extraire_id_ligue(data)
        name = extraire_nom_ligue(data)

        if not league_id or not name:
            return None

        saison = extraire_saison_principale(data)

        return {
            "footystats_id": league_id,
            "name": name,
            "country": data.get("country", "Unknown"),
            "season_id": saison.get("id") if saison else None,
            "season_name": saison.get("name", "") if saison else "",
            "season_year": saison.get("year") if saison else None,
        }

    except Exception as e:
        logger.error_ctx(
            "Erreur parsing ligue",
            context={"erreur": str(e)},
        )
        return None


def parser_saison(data: dict, league_id: int) -> Optional[dict]:
    """
    Parse une saison depuis la réponse FootyStats.
    """
    try:
        season_id = data.get("id")
        if not season_id:
            return None

        return {
            "footystats_id": season_id,
            "league_id": league_id,
            "name": data.get("name", ""),
            "year": _extraire_annee(data.get("name", "")),
            "start_date": data.get("starting_year", "2024-01-01"),
            "end_date": data.get("ending_year", "2025-12-31"),
            "status": "active",
        }

    except Exception as e:
        logger.error_ctx(
            "Erreur parsing saison",
            context={"erreur": str(e)},
        )
        return None


def _extraire_annee(nom_saison: str) -> int:
    """
    Extrait l'année depuis un nom de saison.
    Exemple : '2024/2025' -> 2024
    """
    try:
        parts = nom_saison.split("/")
        return int(parts[0].strip())
    except (ValueError, IndexError):
        return datetime.now().year


def _extraire_saisons_depuis_brut(brut: Any) -> list[dict]:
    if brut is None:
        return []

    if isinstance(brut, list):
        saisons = []
        for item in brut:
            saisons.extend(_extraire_saisons_depuis_brut(item))
        return saisons

    if not isinstance(brut, dict):
        return []

    if brut.get("id") or brut.get("season_id"):
        return [brut]

    for cle in ("data", "season", "seasons", "current_season"):
        if cle in brut and brut[cle] is not brut:
            saisons = _extraire_saisons_depuis_brut(brut[cle])
            if saisons:
                return saisons

    saisons = []
    for valeur in brut.values():
        if isinstance(valeur, (dict, list)):
            saisons.extend(_extraire_saisons_depuis_brut(valeur))
    return saisons


def _normaliser_annee(valeur: Any) -> Optional[int]:
    if valeur is None:
        return None

    digits = "".join(ch for ch in str(valeur) if ch.isdigit())
    if len(digits) >= 8:
        return int(digits[:4])
    if len(digits) >= 4:
        return int(digits[:4])
    return None


def _nettoyer_texte(valeur: Any) -> str:
    if not isinstance(valeur, str):
        return ""
    return " ".join(valeur.split()).strip()


def _coerce_int(valeur: Any) -> Optional[int]:
    if valeur in (None, ""):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _generer_id_ligue_synthetique(country: str, name: str) -> int:
    brut = f"{country.strip().lower()}::{name.strip().lower()}".encode("utf-8")
    digest = hashlib.blake2b(brut, digest_size=8).digest()
    return int.from_bytes(digest, "big") & 0x7FFFFFFFFFFFFFFF
