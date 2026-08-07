"""Une image récupérée est-elle vraiment la photo d'un bien ?

Trois signalements successifs ont montré la limite du raisonnement sur les
adresses : un drapeau (`FR.png`), une cloche (`bell.png`), puis l'étiquette
énergie d'immo-ray. Cette dernière a tranché le débat — elle est servie par
le MÊME script que les vraies photos :

    image-get.inc.php?f=1024x550&n=11837   ← le diagnostic de performance
    image-get.inc.php?f=1024x550&n=11838   ← la maison

Rien dans l'adresse ne les distingue. Il faut ouvrir l'image.

Deux questions, dans cet ordre :

1. **Se charge-t-elle ?** Beaucoup d'adresses trouvées dans les données
   structurées d'un site ne répondent pas : Groupe 123 Immo annonçait
   `/600xauto/images/1/…` là où ses vraies photos vivent sous
   `/580xauto/images/biens/1/…` — un segment manquant, une image morte, et
   une fiche sans illustration alors que la photo existait.

2. **Ressemble-t-elle à une photographie ?** Un diagramme réglementaire —
   étiquette DPE, graphique de consommation — n'emploie qu'une poignée de
   couleurs franches. Une photographie en compte des dizaines de milliers.
   C'est une différence de nature, pas de degré : elle se mesure sans
   ambiguïté et ne dépend d'aucun nom de fichier.
"""

from __future__ import annotations

import struct

# En-deçà, ce n'est pas la photo d'une maison : vignette, pictogramme, pixel
# de mesure. Les gabarits d'agences servent au moins du 400 px de large.
LARGEUR_MINIMALE = 380
HAUTEUR_MINIMALE = 200

# Un diagramme n'a que des aplats. Au-delà de ce nombre de teintes distinctes,
# on tient une vraie photographie. Le seuil est très bas devant les dizaines
# de milliers d'une photo, et très haut devant les quelques dizaines d'une
# étiquette DPE : la zone grise est pratiquement vide.
COULEURS_MINIMALES = 2000

# Repli quand Pillow n'est pas installé : le poids par pixel. Un aplat se
# comprime dix fois mieux qu'une photographie. Moins net que le comptage des
# couleurs, mais du même ordre d'idée.
OCTETS_PAR_PIXEL_MINIMAL = 0.04


def dimensions(donnees: bytes) -> tuple[int, int] | None:
    """Largeur et hauteur lues dans l'en-tête, sans décoder l'image."""
    if len(donnees) < 24:
        return None
    if donnees[:8] == b"\x89PNG\r\n\x1a\n":
        largeur, hauteur = struct.unpack(">II", donnees[16:24])
        return largeur, hauteur
    if donnees[:6] in (b"GIF87a", b"GIF89a"):
        largeur, hauteur = struct.unpack("<HH", donnees[6:10])
        return largeur, hauteur
    if donnees[:4] == b"RIFF" and donnees[8:12] == b"WEBP":
        return _dimensions_webp(donnees)
    if donnees[:2] == b"\xff\xd8":
        return _dimensions_jpeg(donnees)
    return None


def _dimensions_webp(donnees: bytes) -> tuple[int, int] | None:
    forme = donnees[12:16]
    try:
        if forme == b"VP8X":
            largeur = int.from_bytes(donnees[24:27], "little") + 1
            hauteur = int.from_bytes(donnees[27:30], "little") + 1
            return largeur, hauteur
        if forme == b"VP8 ":
            largeur = struct.unpack("<H", donnees[26:28])[0] & 0x3FFF
            hauteur = struct.unpack("<H", donnees[28:30])[0] & 0x3FFF
            return largeur, hauteur
        if forme == b"VP8L":
            bits = int.from_bytes(donnees[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    except (struct.error, IndexError):
        return None
    return None


def _dimensions_jpeg(donnees: bytes) -> tuple[int, int] | None:
    i = 2
    while i + 9 < len(donnees):
        if donnees[i] != 0xFF:
            i += 1
            continue
        marqueur = donnees[i + 1]
        # SOF0..SOF15, hors marqueurs qui ne décrivent pas une trame.
        if 0xC0 <= marqueur <= 0xCF and marqueur not in (0xC4, 0xC8, 0xCC):
            hauteur, largeur = struct.unpack(">HH", donnees[i + 5:i + 9])
            return largeur, hauteur
        if i + 4 > len(donnees):
            break
        taille = struct.unpack(">H", donnees[i + 2:i + 4])[0]
        if taille < 2:
            break
        i += 2 + taille
    return None


def compte_les_couleurs(donnees: bytes, plafond: int = COULEURS_MINIMALES) -> int | None:
    """Nombre de teintes distinctes, ou `plafond` s'il est dépassé.

    None si l'image n'a pas pu être ouverte (Pillow absent, format exotique) :
    l'appelant se rabat alors sur le poids par pixel.
    """
    try:
        import io

        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(io.BytesIO(donnees)) as image:
            image = image.convert("RGB")
            # On réduit avant de compter : une photo reste bariolée en petit,
            # un aplat reste un aplat, et le comptage devient instantané.
            image.thumbnail((200, 200))
            couleurs = image.getcolors(maxcolors=plafond)
            return plafond if couleurs is None else len(couleurs)
    except Exception:
        return None


def ressemble_a_une_photo(donnees: bytes) -> tuple[bool, str]:
    """Verdict et motif, pour que l'audit puisse dire POURQUOI c'est refusé."""
    if not donnees:
        return False, "vide"
    taille = dimensions(donnees)
    if taille is None:
        return False, "format d'image non reconnu"
    largeur, hauteur = taille
    if largeur < LARGEUR_MINIMALE or hauteur < HAUTEUR_MINIMALE:
        return False, f"trop petite ({largeur}×{hauteur})"

    couleurs = compte_les_couleurs(donnees)
    if couleurs is not None:
        if couleurs < COULEURS_MINIMALES:
            return False, f"aplats ({couleurs} teintes) — diagramme, pas une photo"
        return True, f"{largeur}×{hauteur}, {couleurs}+ teintes"

    par_pixel = len(donnees) / max(largeur * hauteur, 1)
    if par_pixel < OCTETS_PAR_PIXEL_MINIMAL:
        return False, f"trop lisse ({par_pixel:.3f} octet/pixel) — diagramme probable"
    return True, f"{largeur}×{hauteur}, {par_pixel:.2f} octet/pixel"
