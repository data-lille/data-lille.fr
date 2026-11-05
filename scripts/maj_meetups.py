"""Met à jour les meetups de data-lille.fr depuis meetup.com/data-lille.

- lit les meetups à venir et les plus récents passés sur meetup.com (sans navigateur) ;
- ajoute les nouveaux meetups dans meetups.json, met à jour titre et inscrits des récents ;
- ne touche jamais au lieu d'un meetup déjà connu (les corrections faites à la main sont gardées) ;
- réécrit dans index.html les blocs entre les repères <!-- auto:... --> et les chiffres clés.

Usage : python3 scripts/maj_meetups.py   (aucune dépendance, Python 3.10+)
"""

import html
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_JSON = RACINE / "meetups.json"
FICHIER_HTML = RACINE / "index.html"
GROUPE = "https://www.meetup.com/data-lille"
# Les inscrits d'un meetup peuvent encore bouger quelques jours après : on les rafraîchit sur cette période.
FENETRE_RAFRAICHISSEMENT = timedelta(days=30)
# Les années plus anciennes que (année courante - 2) vont dans l'accordéon.
ANNEES_VISIBLES = 3
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def telecharger(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (data-lille.fr meetups bot)"})
    with urllib.request.urlopen(req, timeout=30) as rep:
        return rep.read().decode("utf-8")


def etat_apollo(page: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', page, re.S)
    if not m:
        raise RuntimeError("Structure de page Meetup inattendue (__NEXT_DATA__ absent)")
    return json.loads(m.group(1))["props"]["pageProps"].get("__APOLLO_STATE__", {})


def evenements_liste(type_: str) -> list[dict]:
    etat = etat_apollo(telecharger(f"{GROUPE}/events/?type={type_}"))
    return [v for k, v in etat.items() if k.startswith("Event:")]


def details_evenement(id_: str) -> dict:
    etat = etat_apollo(telecharger(f"{GROUPE}/events/{id_}/"))
    ev = etat[f"Event:{id_}"]
    inscrits = ev.get('rsvps({"filter":{"rsvpStatus":["YES"]}})', {}).get("totalCount")
    lieu = "En ligne"
    ref = (ev.get("venue") or {}).get("__ref")
    if ref and ev.get("eventType") != "ONLINE":
        v = etat.get(ref, {})
        nom, ville = (v.get("name") or "").strip(), (v.get("city") or "").strip()
        lieu = f"{nom}, {ville}" if nom and ville and nom != ville else (nom or ville or "Lille")
    debut = datetime.fromisoformat(ev["dateTime"])
    return {
        "id": id_,
        "date": debut.date().isoformat(),
        "time": debut.strftime("%H:%M"),
        "title": ev["title"].strip(),
        "venue": lieu,
        "inscrits": inscrits,
        "url": f"{GROUPE}/events/{id_}/",
    }


def mettre_a_jour_donnees(meetups: list[dict], aujourdhui: date) -> list[dict]:
    connus = {m["id"]: m for m in meetups}
    en_ligne = evenements_liste("upcoming") + evenements_liste("past")
    for ev in en_ligne:
        id_ = ev["id"]
        if ev.get("status") == "CANCELLED":
            connus.pop(id_, None)
            continue
        debut = datetime.fromisoformat(ev["dateTime"]).date()
        if id_ in connus and debut < aujourdhui - FENETRE_RAFRAICHISSEMENT:
            continue  # meetup ancien : figé
        frais = details_evenement(id_)
        if id_ in connus:
            # on garde le lieu corrigé à la main, on rafraîchit le reste
            frais["venue"] = connus[id_]["venue"]
        connus[id_] = frais
    return sorted(connus.values(), key=lambda m: (m["date"], m["time"]), reverse=True)


def e(texte: str) -> str:
    return html.escape(texte, quote=True)


def bloc_prochain(a_venir: list[dict]) -> str:
    if not a_venir:
        return (
            '      <p class="empty">Pas de meetup programmé pour l\'instant. '
            '<a href="https://www.meetup.com/data-lille/" target="_blank" rel="noopener">Rejoignez le groupe Meetup</a> '
            "pour être prévenu du prochain.</p>\n"
        )
    sortie = []
    for m in a_venir:
        a, mo, j = map(int, m["date"].split("-"))
        inscrits = f" · {m['inscrits']} inscrits" if m["inscrits"] else ""
        sortie.append(
            f'      <a class="next" href="{m["url"]}" target="_blank" rel="noopener">\n'
            f'        <div class="next-date"><strong>{j}</strong><span>{MOIS[mo - 1]} {a}</span></div>\n'
            f'        <div class="next-body">\n'
            f'          <h4>{e(m["title"])}</h4>\n'
            f'          <p>{m["time"].replace(":", "h")} · {e(m["venue"])}{inscrits}</p>\n'
            f'          <span class="btn">S\'inscrire sur Meetup</span>\n'
            f"        </div>\n"
            f"      </a>\n"
        )
    return "".join(sortie)


def lignes_tableau(passes: list[dict], indent: str) -> str:
    sortie, annee = [], None
    for m in passes:
        a, mo, j = m["date"].split("-")
        if a != annee:
            if annee:
                sortie.append(f"{indent}  </tbody>")
            du_lot = [x for x in passes if x["date"].startswith(a)]
            n, total = len(du_lot), sum(x["inscrits"] or 0 for x in du_lot)
            sortie.append(
                f'{indent}  <tbody>\n{indent}    <tr class="year"><th colspan="4" scope="rowgroup">{a} '
                f'<span>{n} meetup{"s" if n > 1 else ""} · {total} inscrits</span></th></tr>'
            )
            annee = a
        sortie.append(
            f'{indent}    <tr><td>{j}/{mo}</td><td><a href="{m["url"]}" target="_blank" rel="noopener">{e(m["title"])}</a>'
            f'</td><td>{e(m["venue"])}</td><td>{m["inscrits"] if m["inscrits"] is not None else ""}</td></tr>'
        )
    if annee:
        sortie.append(f"{indent}  </tbody>")
    return "\n".join(sortie) + "\n"


ENTETE = '<thead><tr><th scope="col">Date</th><th scope="col">Meetup</th><th scope="col">Lieu</th><th scope="col">Inscrits</th></tr></thead>'


def bloc_passes(passes: list[dict], aujourdhui: date) -> str:
    limite = str(aujourdhui.year - ANNEES_VISIBLES + 1)
    recents = [m for m in passes if m["date"][:4] >= limite]
    anciens = [m for m in passes if m["date"][:4] < limite]
    sortie = f'      <table class="past">\n        {ENTETE}\n' + lignes_tableau(recents, "      ") + "      </table>\n"
    if anciens:
        premiere, derniere = anciens[-1]["date"][:4], anciens[0]["date"][:4]
        total = sum(m["inscrits"] or 0 for m in anciens)
        sortie += (
            '\n      <details class="older">\n'
            f"        <summary>Voir les meetups de {premiere} à {derniere} "
            f"<span>{len(anciens)} meetups · {total:,} inscrits</span></summary>\n".replace(",", " ")
            + f'        <table class="past">\n        {ENTETE}\n'
            + lignes_tableau(anciens, "      ")
            + "        </table>\n      </details>\n"
        )
    return sortie


def remplacer_bloc(page: str, nom: str, contenu: str) -> str:
    motif = re.compile(rf"(<!-- auto:{nom}[^>]*-->\n)(.*?)(\s*<!-- /auto:{nom} -->)", re.S)
    if not motif.search(page):
        raise RuntimeError(f"Repère auto:{nom} introuvable dans index.html")
    return motif.sub(lambda m: m.group(1) + contenu.rstrip("\n") + m.group(3), page, count=1)


def remplacer_chiffre(page: str, id_: str, valeur: str) -> str:
    return re.sub(rf'(<strong id="{id_}">)[^<]*(</strong>)', rf"\g<1>{valeur}\g<2>", page, count=1)


def main() -> int:
    aujourdhui = date.today()
    meetups = json.loads(FICHIER_JSON.read_text(encoding="utf-8"))
    try:
        meetups = mettre_a_jour_donnees(meetups, aujourdhui)
    except Exception as err:  # Meetup injoignable ou page modifiée : on ne touche à rien
        print(f"Échec de la lecture de meetup.com, aucune modification : {err}", file=sys.stderr)
        return 1

    FICHIER_JSON.write_text(json.dumps(meetups, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    a_venir = sorted([m for m in meetups if m["date"] >= aujourdhui.isoformat()], key=lambda m: m["date"])
    passes = [m for m in meetups if m["date"] < aujourdhui.isoformat()]
    total_inscrits = sum(m["inscrits"] or 0 for m in meetups)

    page = FICHIER_HTML.read_text(encoding="utf-8")
    page = remplacer_bloc(page, "prochain", bloc_prochain(a_venir))
    page = remplacer_bloc(page, "passes", bloc_passes(passes, aujourdhui))
    page = remplacer_chiffre(page, "stat-meetups", str(len(meetups)))
    page = remplacer_chiffre(page, "stat-inscrits", f"{total_inscrits // 100 * 100:,}+".replace(",", " "))
    FICHIER_HTML.write_text(page, encoding="utf-8")
    print(f"{len(meetups)} meetups, {len(a_venir)} à venir, {total_inscrits} inscriptions au total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
