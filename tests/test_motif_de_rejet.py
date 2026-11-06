"""Refuser un bien, c'est bien ; dire par quelle règle, c'est utilisable.

Le 20 août, le déroulé a livré son verdict sur Safti : 212 pages visitées,
212 écartées, ZÉRO illisible. Les pages se lisent donc parfaitement — c'est le
filtre qualité qui dit non, cent fois sur cent. Et le catalogue ne contient pas
une seule annonce Safti depuis l'origine, quand IAD en a mille cent
trente-trois.

Neuf règles peuvent refuser un bien. Laquelle ? Le total ne le dit pas, et
c'est toute la différence entre corriger et deviner — j'ai déjà deviné trois
fois cette semaine, à chaque fois faux.

Le point délicat est ailleurs que dans la mesure : il fallait nommer les
règles SANS en faire une seconde copie. Ce projet a payé trois fois la
divergence de deux copies d'une même règle — cinquante-six annonces
Century 21, dix jours de rotation en Saône-et-Loire, un test qui validait une
fiction. `est_bien_valide` délègue donc à `motif_de_rejet` au lieu de la
doubler, et ces tests le vérifient sur un corpus plutôt que sur ma parole.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import qualite  # noqa: E402


def bien(**champs) -> dict:
    base = {"titre": "Maison de village 4 pièces à Autun",
            "url": "https://www.safti.fr/annonces/achat/maison-autun-71400/12",
            "surface_m2": 120, "pieces": 4, "prix": 150000}
    base.update(champs)
    return base


def test_un_bien_valide_n_a_pas_de_motif():
    assert qualite.motif_de_rejet(bien()) is None
    assert qualite.est_bien_valide(bien()) is True


def test_chaque_regle_se_nomme():
    """Un motif par règle, et le bon — sans quoi la mesure désignerait la
    mauvaise coupable et je corrigerais à côté une quatrième fois."""
    cas = [
        ("titre_indigent", bien(titre="389")),
        # `est_vendu` lit la disponibilité schema.org et le TEXTE, pas le
        # titre — mon premier cas de test se trompait de champ.
        ("vendu", bien(vendu=True)),
        ("vendu", bien(texte="Ce bien est vendu.")),
        ("location", bien(titre="Maison à louer à Autun 4 pièces")),
        ("type_bien", bien(type_bien="parking")),
        ("ni_surface_ni_prix_credible", bien(surface_m2=None, prix=3480)),
        ("prix_trop_haut", bien(prix=1_200_000)),
    ]
    for attendu, a in cas:
        assert qualite.motif_de_rejet(a) == attendu, (
            f"attendu « {attendu} », obtenu « {qualite.motif_de_rejet(a)} » "
            f"pour {a['titre']!r}")


def test_un_titre_hors_cible_nomme_le_fragment_fautif():
    """Ces deux expressions comptent une soixantaine d'alternatives. Savoir que
    « le titre est hors cible » ne dit rien d'exploitable — c'est ce qui manque
    pour comprendre pourquoi 217 pages Safti sur 257 tombent là, et aucune
    page IAD."""
    cas = [("Appartement T3 à Autun", "appartement"),
           ("Nos biens à vendre", "nos biens"),
           # Le fragment porte désormais le PLURIEL, parce que c'est lui qui
           # distingue le catalogue de l'annonce — voir test_titre_de_safti.
           ("Vente de maisons et villas | Agence du Centre", "vente de maisons"),
           ("Terrain à bâtir à Autun", "terrain a batir")]
    for titre, fragment in cas:
        motif = qualite.motif_de_rejet(bien(titre=titre, type_bien="maison"))
        assert motif == f"titre_hors_cible:{fragment}", (
            f"pour {titre!r} : obtenu « {motif} », attendu le fragment "
            f"« {fragment} »")


def test_le_fragment_ne_casse_pas_le_decoupage_du_collecteur():
    """Le collecteur découpe « ecarte:<motif> » sur le PREMIER deux-points.
    Un motif qui en contient un lui-même doit rester lisible."""
    motif = qualite.motif_de_rejet(bien(titre="Appartement T3 à Autun"))
    etat, _, reste = f"ecarte:{motif}".partition(":")
    assert etat == "ecarte" and reste == motif


def test_la_decision_et_son_explication_ne_peuvent_pas_diverger():
    """LE test. `est_bien_valide` doit être exactement « aucun motif ».

    C'est la garantie qui manquait aux trois divergences passées : ici la
    seconde fonction ne redit pas les règles, elle appelle la première.
    """
    cas = [bien(),
           bien(titre="389"),
           bien(titre="Maison à Autun — sous compromis"),
           bien(titre="Appartement à louer Autun"),
           bien(type_bien="terrain"),
           bien(surface_m2=None, pieces=None, prix=None),
           bien(surface_m2=None, prix=3480),
           bien(prix=900_000),
           bien(url="https://www.safti.fr/annonces/location/maison-autun/12"),
           bien(titre=""),
           bien(titre="Maison", surface_m2=0, prix=0)]
    for a in cas:
        assert qualite.est_bien_valide(a) == (qualite.motif_de_rejet(a) is None), (
            f"les deux fonctions ne disent pas la même chose pour {a!r}")


def test_le_catalogue_publie_passe_toujours_le_filtre():
    """Le corpus réel, et non mes exemples : les biens déjà servis doivent
    rester valides et sans motif. Un refactoring qui les rejetterait viderait
    le site au prochain export.
    """
    import json
    biens = json.loads((RACINE / "data" / "annonces_reel.json")
                       .read_text(encoding="utf-8"))
    rejetes = [(b.get("titre"), qualite.motif_de_rejet(b))
               for b in biens[:1500] if qualite.motif_de_rejet(b) is not None]
    # Le fichier contient plus que ce qui est servi (pages de catalogue, biens
    # hors terroir) : on n'exige pas zéro, mais que décision et motif concordent.
    for b in biens[:1500]:
        assert qualite.est_bien_valide(b) == (qualite.motif_de_rejet(b) is None)
    assert len(rejetes) < len(biens[:1500]), "tout le catalogue serait rejeté"


def test_le_collecteur_consigne_le_motif():
    """La mesure doit remonter jusqu'au déroulé, sinon elle ne sert à rien."""
    source = (RACINE / "scripts" / "collecter_mandataires.py").read_text(
        encoding="utf-8")
    assert 'return f"ecarte:{motif}"' in source, (
        "le collecteur écarte sans dire pourquoi")
    appel = source[source.index('etape("departement"'):]
    assert "motifs=" in appel[:appel.index(")\n")], (
        "les motifs ne sont pas consignés dans le déroulé")


def test_un_bien_d_outre_mer_est_ecarte_meme_place_chez_nous():
    """La maison de Rivière-du-Mât-les-Bas, à La Réunion : lue « Rivière » par
    son adresse, géolocalisée dans le Pas-de-Calais, elle était servie le
    30 octobre 2026 sous « IAD France (37) ». Son titre disait (97440). Un
    prix collé à l'euro n'est pas un code postal."""
    reunion = bien(titre="Maison traditionnelle 4 pièces de 100 m² à RIVIERE du mat "
                         "les bas (97440)", departement="37", code_postal="62173",
                   lat=50.234953, lon=2.695074)
    assert qualite.motif_de_rejet(reunion) == "outre_mer"
    assert qualite.est_bien_valide(reunion) is False
    assert qualite.motif_de_rejet(bien(
        titre="Vente de maison 4 pièces à La Trinite 97220 : 95m², prix 361 000 €. "
              "Réf : 1638170")) == "outre_mer"
    for titre in ("Maison 4 pièces de 79 m² à Berny-Rivière (02290)",
                  "Maison 3 pièces à Givry, 97000 €",
                  "Maison 3 pièces à Givry, 98500 euros"):
        assert qualite.motif_de_rejet(bien(titre=titre)) != "outre_mer", titre


def test_un_appartement_au_titre_coupe_ou_mal_ecrit_reste_un_appartement():
    """Servis comme des maisons le 1er novembre 2026 : le titre de Bon'Appart
    était coupé en plein mot, celui de PBH Immo écrit avec une faute."""
    for titre in ("Rare sur le marché ! Situé au-dessus de la Poste en plein centre-ville "
                  "de Fameck, découvrez ce grand apparteme",
                  "appartemenet atypique F2 - centre ville de LA BOURBOULE"):
        motif = qualite.motif_de_rejet(bien(titre=titre))
        assert motif and motif.startswith("titre_hors_cible:appartem"), (titre, motif)
    assert qualite.motif_de_rejet(bien(titre="Maison qui appartient à la même famille "
                                             "depuis 1900")) is None


def test_un_appartement_qui_ne_dit_que_son_etage_est_ecarte():
    """Servis comme des maisons le 6 novembre 2026 : le titre ne disait pas
    « appartement », l'étage le disait pour lui."""
    for titre in ("REMIREMONT - Bel F3 au 1er étage avec garage",
                  "Deauville centre 3 pièces de 50m² au dernier étage.",
                  "Les docks, dernier étage",
                  "Nouveauté Saint - Etienne les Rt : Plateau situé au 2 ème étage à aménager",
                  "Proche Senlis – 3 pièces en étage",
                  "Vente T3 au 5e Etage Place Leclerc"):
        motif = qualite.motif_de_rejet(bien(titre=titre))
        assert motif == "titre_hors_cible:etage", (titre, motif)


def test_une_maison_qui_parle_de_son_etage_reste_une_maison():
    """La « maison bel étage » du Nord était au fichier ce jour-là, servie à
    juste titre ; les chambres d'une maison sont à l'étage, ou au premier."""
    for titre in ("LARGE MAISON BEL ETAGE - DOUBLE GARAGE ET ATELIER PERENCHIES 59840",
                  "Maison de ville, trois chambres au 1er étage",
                  "Longère rénovée, suite parentale au dernier étage",
                  "Belle 4 pièces avec deux chambres à l'étage"):
        assert qualite.motif_de_rejet(bien(titre=titre)) is None, titre


def test_la_rubrique_numerotee_dit_le_type_du_bien():
    """« /2-appartement/ », « /21-immeuble/ » : le numéro cachait la rubrique,
    et trente biens de ce gabarit étaient servis comme des maisons le
    6 novembre 2026 — l'adresse prime sur le titre, ici « maison »."""
    for url in ("https://www.bienchezsoi-immo.com/vente/10-aube/1-troyes/2-appartement/t3/"
                "781-a-vendre-centre-de-troyes-duplex-",
                "https://www.creilimmo.fr/vente/60-oise/10-montataire/21-immeuble/"
                "485-rare-immeuble-de-6-logements/",
                "https://www.agence-berry-immobilier.fr/vente/36-indre/39-neuvy-pailloux/"
                "5-terrain/3119-exclusivite-terrain-de-",
                "https://www.bon-appart.fr/vente/54-meurthe-et-moselle/557-val-de-briey/"
                "20-autre/6096-hangar-100m2-1-piece-100m"):
        motif = qualite.motif_de_rejet(bien(url=url))
        assert motif == "url_type_exclu", (url, motif)
    maison = ("https://www.bienchezsoi-immo.com/vente/10-aube/264-plancy-l-abbaye/1-maison/t5/"
              "836-achat-maison-98m2-sur-746m2-de-terrain-et-sous-sol/")
    assert qualite.motif_de_rejet(bien(url=maison)) is None
