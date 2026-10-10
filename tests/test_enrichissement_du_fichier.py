"""Le rattrapage des risques sur le fichier publié.

L'enrichissement de la collecte ne regarde que la base du jour, recréée à
chaque passage : un bien dont l'appel a échoué n'est jamais retenté. Mesuré
le 9 octobre 2026 : 6 139 biens servis sur 9 396 sans risques officiels, et
le barème leur donne le maximum du pilier. Le même jour à 17 h, l'API a
répondu pour 39 biens après quinze jours de silence.

Ces tests exercent le vrai script sur un fichier jetable et une API factice.
Les biens témoins ont chacun leur titre et leur prix : le chargement replie
les doublons, et douze copies d'un même bien n'en feraient qu'un.
"""

import importlib.util
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import georisques  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "enrichir_fichier_test", RACINE / "scripts" / "enrichir_fichier.py")
rattrapage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rattrapage)

REPONSE = {"inondation_commune": True, "argile_commune": True, "feu_foret_commune": False,
           "seisme_commune": True, "radon_commune": True, "seveso_km": None,
           "icpe_commune": False, "portee": "commune", "source": "georisques"}


def _bien(ident, **champs):
    """Un bien servi, distinct des autres par son titre et son prix."""
    n = sum(ord(c) for c in ident) % 50
    b = {"id": ident, "source": "agence-test", "type_bien": "maison",
         "titre": f"Maison {ident} 5 pièces à Bellême", "agence": "Agence Test",
         "agence_url": "https://agence-test.fr", "url": f"https://agence-test.fr/bien/{ident}",
         "prix": 90000 + n * 1000, "surface_m2": 100 + n, "terrain_m2": 900, "pieces": 5,
         "commune": "Bellême", "code_postal": "61130", "departement": "61",
         "lat": 48.373, "lon": 0.561}
    b.update(champs)
    return b


def test_les_servis_sans_risques_les_plus_recents_d_abord():
    biens = [
        _bien("ancien", revue_le="2026-10-01"),
        _bien("recent", revue_le="2026-10-09", risques={"nucleaire_km": 42.0}),
        _bien("deja", revue_le="2026-10-09", risques={**REPONSE, "argile": 1}),
        _bien("hors-terroir", revue_le="2026-10-09", departement=None, code_postal=None, commune=None),
        _bien("sans-point", revue_le="2026-10-09", lat=None, lon=None),
    ]
    assert [b["id"] for b in rattrapage.a_rattraper(biens)] == ["recent", "ancien"]


def test_le_rattrapage_ecrit_les_risques_et_garde_la_centrale():
    biens = [_bien("a", revue_le="2026-10-09", risques={"nucleaire_km": 42.0, "nucleaire_nom": "Belleville"}),
             _bien("b", revue_le="2026-10-08")]
    appels = []
    faits, echecs = rattrapage.enrichir(
        biens, maxi=10, minutes_max=1.0,
        interroger=lambda lat, lon: (appels.append(lat), dict(REPONSE))[1],
        argile=lambda lat, lon: 2, dormir=lambda s: None)
    assert (faits, echecs) == (2, 0) and len(appels) == 2
    assert biens[0]["risques"]["source"] == "georisques" and biens[0]["risques"]["argile"] == 2
    assert biens[0]["risques"]["nucleaire_km"] == 42.0, "ce qu'on calcule chez nous reste"
    assert biens[1]["risques"]["inondation_commune"] is True


def test_dix_echecs_d_affilee_suffisent():
    biens = [_bien(f"b{i}", revue_le="2026-10-09") for i in range(12)]
    appels = []

    def muette(lat, lon):
        appels.append(lat)
        georisques.DERNIERE_ERREUR = "ConnectTimeout"
        return None

    faits, echecs = rattrapage.enrichir(biens, 200, 1.0, interroger=muette,
                                        argile=lambda *a: None, dormir=lambda s: None)
    assert (faits, echecs) == (0, 10) and len(appels) == 10
    assert all(not b.get("risques") for b in biens), "rien n'est inventé"


def test_le_fichier_n_est_recrit_que_si_quelque_chose_a_change(tmp_path, monkeypatch, capsys):
    fichier = tmp_path / "annonces.json"
    fichier.write_text(json.dumps([_bien("a", revue_le="2026-10-09")], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["enrichir_fichier.py", "--fichier", str(fichier), "--max", "5"])
    monkeypatch.setattr(georisques, "risques_pour", lambda lat, lon, timeout=10: None)
    georisques.DERNIERE_ERREUR = "ReadTimeout"
    avant = fichier.read_text(encoding="utf-8")
    rattrapage.main()
    assert fichier.read_text(encoding="utf-8") == avant, "un échec ne récrit pas le fichier"
    assert "0 bien(s) rattrapé(s)" in capsys.readouterr().out

    monkeypatch.setattr(georisques, "risques_pour", lambda lat, lon, timeout=10: dict(REPONSE))
    monkeypatch.setattr(georisques, "exposition_argile", lambda lat, lon, timeout=10: 3)
    monkeypatch.setattr(rattrapage.time, "sleep", lambda s: None)
    rattrapage.main()
    ecrit = json.loads(fichier.read_text(encoding="utf-8"))
    assert ecrit[0]["risques"]["argile"] == 3 and ecrit[0]["risques"]["source"] == "georisques"
    assert "1 bien(s) rattrapé(s)" in capsys.readouterr().out
