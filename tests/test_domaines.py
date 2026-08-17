"""Retrouver le site d'une agence sans jamais l'attribuer à tort.

CBF Conseils vendait une maison au Creusot ; elle était dans nos données
depuis le recensement, avec son SIRET, et resta injoignable — le registre ne
donne pas d'adresse en ligne, et rien ne comblait ce chaînon. Vingt-six mille
quatre cent cinquante-deux agences de notre périmètre étaient dans ce cas :
connues, et hors d'atteinte.

Ces tests tiennent les deux sens, et le second compte davantage :

- trouver — savoir fabriquer les adresses plausibles d'un nom, y compris
  quand le registre l'enrobe de formes juridiques et de noms commerciaux ;
- ne pas se tromper — car un domaine mal attribué est bien pire qu'un domaine
  introuvable. Il ferait entrer les biens d'autrui sous le nom d'une agence,
  avec un lien qui trompe le visiteur, et la règle de sortie effacerait
  ensuite de vraies annonces en croyant avoir visité sa cible.

Les noms utilisés ici sont ceux du registre, relevés tels quels.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app import domaines  # noqa: E402

CBF = {"nom": "CBF CONSEILS", "commune": "Chalon-Sur-Saone",
       "siret": "89296570800035", "departement": "71"}


# --- trouver ---------------------------------------------------------------

def test_les_adresses_plausibles_d_un_nom_simple():
    trouvees = domaines.domaines_plausibles("CBF CONSEILS")
    assert "cbfconseils.fr" in trouvees
    assert "cbf-conseils.fr" in trouvees
    assert trouvees[0].endswith(".fr"), "le .fr d'abord : c'est le plus répandu"


def test_le_nom_commercial_est_essaye_autant_que_le_legal():
    """Le registre écrit « JANUS IMMOBILIER (GUY HOQUET L'IMMOBILIER) » : c'est
    souvent le nom entre parenthèses qui porte le domaine."""
    variantes = domaines.variantes_de_nom("C & M GESTION (CIMM GESTION - GEST'IN)")
    assert "C & M GESTION" in variantes
    assert "CIMM GESTION" in variantes
    assert "GEST'IN" in variantes


def test_les_formes_juridiques_ne_vont_pas_dans_un_domaine():
    assert domaines.variantes_de_nom("SARL IMMO PROST") == ["IMMO PROST"]
    assert "immoprost.fr" in domaines.domaines_plausibles("SARL IMMO PROST")


def test_une_tete_de_reseau_n_est_jamais_proposee():
    """« JANUS IMMOBILIER (GUY HOQUET L'IMMOBILIER) » ne doit pas nous envoyer
    sur guy-hoquet.com : on y collecterait les biens de toute la France, et le
    budget de collecte y passerait entier."""
    trouvees = domaines.domaines_plausibles("JANUS IMMOBILIER (GUY HOQUET L'IMMOBILIER)")
    assert "guy-hoquet.com" not in trouvees
    assert any("janus" in d for d in trouvees), "l'agence locale, elle, reste visée"


def test_le_nombre_d_adresses_reste_borne():
    """Chaque adresse est une requête chez un tiers. Un nom à rallonge ne doit
    pas en produire trente."""
    long = "CABINET EUROP GESTION IMMOBILIERE TRANSACTION (CEGIT) (EUROP GESTION)"
    assert len(domaines.domaines_plausibles(long, maxi=8)) <= 8


# --- ne pas se tromper -----------------------------------------------------

def test_la_bonne_page_est_reconnue():
    """Le nom distinctif ET la commune : deux concordances indépendantes."""
    page = ("CBF Conseils Immobilier — votre agence à Chalon-sur-Saône. "
            "Nos biens à vendre, estimation gratuite.")
    assert domaines.est_le_bon_site(CBF, page)


def test_le_siret_vaut_confirmation_sans_la_commune():
    """Beaucoup d'agences ne nomment pas leur ville en page d'accueil, mais
    publient leur SIRET en mentions légales."""
    page = "CBF Conseils — SIRET 892 965 708 00035 — nos annonces"
    assert domaines.est_le_bon_site(CBF, page)


def test_le_nom_seul_ne_suffit_jamais():
    """LE garde-fou. Une page qui porte le nom sans rien d'autre peut être un
    homonyme : un cabinet de conseil, une association, un autre CBF."""
    page = "CBF Conseils — cabinet de conseil en stratégie et organisation."
    assert not domaines.est_le_bon_site(CBF, page)


def test_le_vocabulaire_immobilier_seul_ne_confirme_rien():
    """Il y a des milliers de sites d'agences. Celui qu'on tient doit être
    celui-là, pas « une agence »."""
    page = ("Agence immobilière — maisons et appartements à vendre, "
            "estimation, mandat, honoraires.")
    assert domaines.confiance(CBF, page) == 0, "sans le nom distinctif, rien"


def test_un_mot_generique_ne_designe_personne():
    """« Conseils » ne distingue pas CBF Conseils d'un autre : exiger le mot
    générique ferait correspondre n'importe quelle page."""
    assert domaines.mots_distinctifs("CBF CONSEILS") == ["cbf"]
    page = "Conseils immobiliers à Chalon-sur-Saône — nos biens à vendre"
    assert not domaines.est_le_bon_site(CBF, page)


def test_un_domaine_parque_ne_se_confirme_pas_tout_seul():
    """Piège en boucle : la page d'un domaine en vente affiche le domaine, donc
    le nom qui a servi à le fabriquer. Elle se validerait elle-même."""
    page = ("cbfconseils.fr — ce domaine est à vendre. Achetez ce domaine. "
            "Chalon-sur-Saone. Vente immédiate.")
    assert domaines.confiance(CBF, page) == 0


def test_un_site_en_construction_ne_compte_pas():
    page = "CBF Conseils — site en cours de construction. Chalon-sur-Saône."
    assert domaines.confiance(CBF, page) == 0


def test_une_agence_homonyme_dans_une_autre_ville_est_ecartee():
    """Même nom, autre commune, autre SIRET : c'est une autre entreprise. La
    confondre importerait ses biens sous notre étiquette."""
    page = ("CBF Conseils Immobilier — votre agence à Bordeaux. "
            "Nos biens à vendre, estimation gratuite.")
    assert not domaines.est_le_bon_site(CBF, page)


def test_une_variante_purement_generique_n_est_pas_sondee():
    """« C & M GESTION » perd ses initiales d'une lettre et ne laisserait que
    « gestion.fr » — le domaine de personne en particulier. On passe aux
    autres appellations du même nom plutôt que d'aller frapper là."""
    trouvees = domaines.domaines_plausibles("C & M GESTION (CIMM GESTION - GEST'IN)")
    assert "gestion.fr" not in trouvees
    assert "cimmgestion.fr" in trouvees, "les variantes distinctives restent"


def test_une_agence_sans_aucun_mot_distinctif_ne_produit_rien():
    """Mieux vaut zéro adresse qu'une adresse au hasard : elle coûterait une
    requête chez un tiers et pourrait ramener le site de quelqu'un d'autre."""
    assert domaines.domaines_plausibles("AGENCE IMMOBILIERE") == []
