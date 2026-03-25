"""
Migration 011 — Fusion des ligues orphelines vers leurs nouvelles entrées.

FootyStats a changé ses noms et IDs internes entre versions API, créant des
doublons : anciennes entrées désactivées + nouvelles entrées actives pour la
même compétition. Les matchs historiques pointent vers les anciens league_id.

Cette migration :
1. Redirige tous les matchs et saisons des anciens IDs vers les nouveaux
2. Supprime les entrées orphelines devenues vides
"""

import sqlite3

DESCRIPTION = "Fusion ligues orphelines FootyStats (anciens IDs → nouveaux IDs)"

# Paires connues : (ancien_league_id, nouveau_league_id)
# Identifiées par comparaison manuelle des noms dans la base
FUSIONS = [
    (1,  9),   # "Premier League"  → "England Premier League"
    (2,  10),  # "La Liga"         → "Spain La Liga"
    (3,  12),  # "Serie A"         → "Italy Serie A"
    (4,  7),   # "Bundesliga"      → "Germany Bundesliga"
    (5,  11),  # "Ligue 1"         → "France Ligue 1"
]


def appliquer(conn: sqlite3.Connection) -> None:
    for ancien_id, nouveau_id in FUSIONS:
        # Vérifier que les deux entrées existent
        ancien = conn.execute(
            "SELECT id, name FROM leagues WHERE id = ?", (ancien_id,)
        ).fetchone()
        nouveau = conn.execute(
            "SELECT id, name FROM leagues WHERE id = ?", (nouveau_id,)
        ).fetchone()

        if not ancien or not nouveau:
            continue

        # Migrer les matchs
        conn.execute(
            "UPDATE matches SET league_id = ? WHERE league_id = ?",
            (nouveau_id, ancien_id),
        )

        # Migrer les saisons
        conn.execute(
            "UPDATE seasons SET league_id = ? WHERE league_id = ?",
            (nouveau_id, ancien_id),
        )

        # Supprimer les entrées user_leagues qui pointent vers l'ancien ID
        # (l'utilisateur a déjà les nouvelles entrées créées à l'inscription)
        conn.execute(
            "DELETE FROM user_leagues WHERE league_id = ?",
            (ancien_id,),
        )

        # Supprimer l'ancienne entrée ligue devenue vide
        conn.execute(
            "DELETE FROM leagues WHERE id = ?",
            (ancien_id,),
        )

    conn.commit()
