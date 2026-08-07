"""Les identifiants d'autrui ne doivent jamais atteindre le dépôt.

Cas réel : la première collecte chez IAD a rapporté une clé d'accès Mapbox —
le site s'en sert pour ses cartes — captée dans le texte visible de la page.
GitHub a refusé le dépôt, et il a eu raison : republier la clé d'un tiers
dans un dépôt public, c'est l'exposer à qui voudra s'en servir à ses frais.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.caviardage import (  # noqa: E402
    MARQUE, caviarder, caviarder_annonce, identifiants_restants)

# Formes réalistes, fabriquées pour le test — aucune n'est un vrai identifiant.
MAPBOX = ("pk.eyJ1IjoiZXhlbXBsZS1kZS10ZXN0IiwiYSI6ImNrZXhlbXBsZSJ9."
          "AbCdEfGhIjKlMnOpQrStUv")
JWT = ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJleGVtcGxlIn0."
       "ZXhlbXBsZS1kZS1zaWduYXR1cmU")


def test_le_jeton_mapbox_est_efface():
    """Celui qui a fait refuser le dépôt."""
    texte = f"Maison avec cave. mapboxgl.accessToken = '{MAPBOX}'; carte"
    propre = caviarder(texte)
    assert MAPBOX not in propre
    assert MARQUE in propre
    assert "Maison avec cave" in propre, "le texte utile doit survivre"


def test_les_familles_courantes_sont_couvertes():
    for jeton in (JWT, "AIza" + "b" * 35, "AKIA" + "C" * 16,
                  "sk_live_" + "d" * 24, "ghp_" + "e" * 36,
                  "xoxb-1234567890-abcdefghij"):
        assert jeton not in caviarder(f"texte {jeton} suite"), jeton


def test_le_texte_de_detection_reste_exploitable():
    """Le caviardage ne doit rien coûter au score : personne ne cherche
    « cave » dans un jeton."""
    texte = (f"Belle longère : cave voûtée, puits, poêle à bois, verger. "
             f"accessToken={MAPBOX}")
    propre = caviarder(texte)
    for mot in ("cave", "puits", "poêle", "verger"):
        assert mot in propre


def test_les_champs_libres_d_une_annonce_sont_nettoyes():
    annonce = {"titre": f"Maison {MAPBOX}", "description": f"Vue. {JWT}",
               "texte": f"cave {MAPBOX}", "url": "https://iad.fr/annonce/x"}
    propre = caviarder_annonce(annonce)
    assert MAPBOX not in propre["titre"]
    assert JWT not in propre["description"]
    assert MAPBOX not in propre["texte"]
    assert propre["url"] == "https://iad.fr/annonce/x", "l'adresse reste intacte"


def test_le_garde_fou_nomme_les_champs_fautifs():
    assert identifiants_restants({"texte": f"clé {MAPBOX}"}) == ["texte"]
    assert identifiants_restants({"texte": "cave voûtée", "prix": 200000}) == []


def test_une_annonce_ordinaire_n_est_pas_abimee():
    """Aucun faux positif sur un texte d'annonce normal — les références
    d'agences ressemblent parfois à des jetons."""
    annonce = {
        "titre": "Longère 4 chambres à Bellême — réf. LR-2026-00817",
        "description": "Maison de 140 m² sur 6 000 m² de terrain, DPE D.",
        "texte": "Cave voûtée, puits, poêle à bois. Référence 71510-AB12. "
                 "Contact : 03 85 00 00 00 — contact@agence-exemple.fr",
    }
    assert caviarder_annonce(annonce) == annonce
    assert identifiants_restants(annonce) == []


def test_le_caviardage_agit_des_l_entree_en_base():
    """Le nettoyage doit avoir lieu avant l'écriture, pas seulement à l'export."""
    from app.chargement import preparer_annonce

    prepare = preparer_annonce({
        "titre": "Longère à Bellême", "texte": f"cave voûtée {MAPBOX}",
        "prix": 245000, "surface_m2": 140, "code_postal": "61130",
    })
    assert MAPBOX not in prepare["texte"]
    assert prepare["features"].get("cave"), "la détection doit encore marcher"


def test_le_garde_fou_regarde_dans_les_listes_et_les_dictionnaires():
    """Le dépôt a été refusé une seconde fois parce que le garde-fou ne
    regardait que les valeurs texte de premier niveau : `photos` est une
    LISTE d'adresses, `risques` un dictionnaire."""
    assert identifiants_restants(
        {"photos": ["https://cdn.fr/a.jpg", f"https://cdn.fr/b.jpg?t={MAPBOX}"]}
    ) == ["photos[1]"]
    assert identifiants_restants({"risques": {"note": f"clé {JWT}"}}) == ["risques.note"]
    assert identifiants_restants(
        {"photos": ["https://cdn.fr/a.jpg"], "risques": {"inondation": True},
         "prix": 200000}) == []


def test_une_photo_signee_est_retiree_sans_perdre_l_annonce():
    """Cas réel : les images d'Immo Côte d'Opale portent un `access-token=`.
    C'est l'IMAGE qui pose problème, pas la maison — six annonces valides
    auraient disparu du catalogue pour cette seule raison."""
    from app.caviardage import preparer_pour_publication

    signee = "https://cdn.agence.fr/photo-9.jpg?access-token=" + "z" * 40
    propre, retires = preparer_pour_publication({
        "id": "x1", "url": "https://agence.fr/bien/9", "photo": signee,
        "photos": [signee, "https://cdn.agence.fr/photo-10.jpg"],
        "titre": "Maison 5 pièces à Berck", "prix": 245000,
    })
    assert propre["photos"] == ["https://cdn.agence.fr/photo-10.jpg"]
    assert propre["photo"] == "https://cdn.agence.fr/photo-10.jpg", "on prend la suivante"
    assert identifiants_restants(propre) == []
    assert retires, "le retrait doit être signalé"


def test_sans_candidate_propre_l_annonce_reste_mais_sans_image():
    from app.caviardage import preparer_pour_publication

    signee = "https://cdn.agence.fr/p.jpg?access-token=" + "z" * 40
    propre, _ = preparer_pour_publication(
        {"id": "x2", "url": "https://agence.fr/bien/2", "photo": signee,
         "photos": [signee], "titre": "Longère"})
    assert propre["photo"] is None
    assert identifiants_restants(propre) == []
