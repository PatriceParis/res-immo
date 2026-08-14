"""Un lien qui promet un filtre doit l'appliquer.

Les pages servies par le serveur envoient vers la carte avec une sélection
dans l'adresse : `/?region=Normandie` depuis les six pages de terroir,
`/?prix_max=100000` depuis la page des petits prix. Rien ne les lisait — on
arrivait sur le catalogue entier et l'on devait refaire à la main la
sélection qu'on venait de faire. Les liens terroir étaient dans ce cas depuis
leur création.

C'est le même défaut que le lien « voir chez l'agence » qui menait à une page
d'accueil : une promesse dans le libellé, autre chose au bout.

Ce test EXÉCUTE la fonction avec des doublures plutôt que de la relire — un
`includes` sur une liste d'objets se relit très bien et ne marche jamais.
"""

import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

APP_JS = RACINE / "app" / "static" / "app.js"

# On extrait la fonction et on l'exécute seule, avec un DOM et un état
# factices : ni navigateur, ni réseau, ni carte.
BANC = """
const fs = require("fs");
// argv[0] = node, argv[1] = ce banc, argv[2] = app.js, argv[3] = les adresses.
const src = fs.readFileSync(process.argv[2], "utf8");
const bloc = src.slice(src.indexOf("function appliquerParametresUrl"));
const corps = bloc.slice(0, bloc.indexOf("\\n}") + 2);
const resultats = {};
for (const recherche of JSON.parse(process.argv[3])) {
  const champs = { "#f-prix": { value: 2000000, max: 2000000 } };
  const etat = { region: null, cadre: true,
                 regions: [{ region: "Normandie" }, { region: "Perche" }] };
  let majAppele = 0;
  const $ = (s) => champs[s];
  const majTerroirs = () => majAppele++;
  const location = { search: recherche };
  eval(corps + "; appliquerParametresUrl();");
  resultats[recherche] = { prix: +champs["#f-prix"].value, region: etat.region,
                           cadre: etat.cadre, maj: majAppele };
}
console.log(JSON.stringify(resultats));
"""


def _executer(recherches: list[str]) -> dict:
    banc = RACINE / "tests" / "_banc_filtres_url.js"
    banc.write_text(BANC, encoding="utf-8")
    try:
        sortie = subprocess.run(
            ["node", str(banc), str(APP_JS), json.dumps(recherches)],
            capture_output=True, text=True, check=True).stdout
    finally:
        banc.unlink(missing_ok=True)
    return json.loads(sortie)


def test_le_plafond_de_prix_est_applique():
    """Le lien de la page des petits prix."""
    r = _executer(["?prix_max=100000"])["?prix_max=100000"]
    assert r["prix"] == 100000


def test_un_plafond_au_dela_du_curseur_vaut_tous_prix():
    """On borne plutôt que d'ignorer : un lien un peu large doit rester
    utilisable, pas devenir sans effet."""
    r = _executer(["?prix_max=9000000"])["?prix_max=9000000"]
    assert r["prix"] == 2000000


def test_le_terroir_est_selectionne_et_la_carte_recentree():
    """Le lien des six pages de terroir."""
    r = _executer(["?region=Normandie"])["?region=Normandie"]
    assert r["region"] == "Normandie"
    assert r["cadre"] is False, "la carte doit se recentrer sur le terroir"
    assert r["maj"] == 1, "les pastilles doivent refléter la sélection"


def test_une_region_inconnue_est_ignoree():
    """`etat.regions` contient des OBJETS : comparer une chaîne à la liste
    renverrait toujours faux, silencieusement, et le filtre ne s'appliquerait
    jamais. C'est le piège que ce test garde fermé."""
    r = _executer(["?region=Atlantide"])["?region=Atlantide"]
    assert r["region"] is None and r["maj"] == 0


def test_sans_parametre_rien_ne_bouge():
    r = _executer([""])[""]
    assert r == {"prix": 2000000, "region": None, "cadre": True, "maj": 0}
