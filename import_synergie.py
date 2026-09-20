# -*- coding: utf-8 -*-
"""
import_synergie.py — Import initial des données depuis le fichier Excel SYNERGIE.

Recrée la base à zéro depuis schema.sql puis y injecte :
    - Les créneaux récurrents détectés dans Feuil3 (lundi 11h, lundi 12h30, mardi 19h, vend 12h30)
    - Les clients (Feuil3) avec leur pack initial (forfait) + historique NEW_ACCOUNT
    - Une inscription par client vers son créneau récurrent
    - Un CHECK-IN par date de séance effectuée (cols 'cours 1..20' de Feuil3)
    - Les cours annulés détectés dans SUIVI COURS (col J = 'annulé')
    - Les previsions (cellules vertes theme:8 sur cours à venir) dans SUIVI COURS

Usage :
    python import_synergie.py

⚠ Écrase TOUTES les données actuelles. Demande confirmation avant.
"""

import sqlite3
import openpyxl
import re
import unicodedata
from datetime import datetime, date
from pathlib import Path

# ============================================================
# Configuration
# ============================================================

ROOT = Path(__file__).parent
DB_PATH = ROOT / 'database_clients.db'
SCHEMA_PATH = ROOT / 'schema.sql'
XLSX_PATH = ROOT / 'data_maman' / 'SYNERGIE CYSOING (2).xlsx'

# Année de référence pour les dates courtes comme "31/08" (pas d'année dans le fichier)
ANNEE_REF = 2026

# Type de séance par défaut pour tous les créneaux importés
TYPE_SEANCE_DEFAULT = 'Pilates'
DUREE_DEFAULT = 60  # min

# Palette Excel du fichier :
#   theme:6 = orange (#F0AE1E) = présent (cours passé)
#   theme:8 = vert olive (#88AC2E) = prévu (cours futur)
THEME_PRESENT = 6
THEME_PREVU = 8

JOURS_STR_TO_INT = {
    'lundi': 0, 'lun': 0,
    'mardi': 1, 'mar': 1,
    'mercredi': 2, 'mer': 2,
    'jeudi': 3, 'jeu': 3,
    'vendredi': 4, 'vend': 4, 'ven': 4,
    'samedi': 5, 'sam': 5,
    'dimanche': 6, 'dim': 6,
}

# Alias de noms (fautes de frappe / orthographes multiples) — sur le NOM en MAJUSCULES
NOM_ALIASES = {
    'PETIPREZ': 'PETITPREZ',
    'BAURE': 'BRAURE',
    'DERYCKE': 'DE RYCKE',
}


# ============================================================
# Utilitaires
# ============================================================

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def normalize_prenom(p):
    """Nettoie un prénom : trim, retire suffixes 'Yoga'/'Pilates', title case."""
    if not p:
        return ''
    p = str(p).strip()
    # Suffixes ajoutés par la maman pour disambiguer (ex: "Charlotte Yoga")
    p = re.sub(r'\s+(Yoga|Pilates)$', '', p, flags=re.IGNORECASE)
    return p.title()


def normalize_nom(n):
    """Nettoie un nom : trim, uppercase, applique aliases."""
    if not n:
        return ''
    n = str(n).strip().upper()
    return NOM_ALIASES.get(n, n)


def parse_creneau_recurrent(text):
    """
    Parse 'lundi 12h30' → {'jour': 0, 'heure': '12:30'}
    Retourne None si non parsable.
    """
    if not text:
        return None
    text = str(text).strip().lower()
    m = re.match(r'^(\w+)\s+(\d{1,2})h(\d{0,2})', text)
    if not m:
        return None
    jour_str = m.group(1)
    if jour_str not in JOURS_STR_TO_INT:
        return None
    h = int(m.group(2))
    mn = int(m.group(3)) if m.group(3) else 0
    return {'jour': JOURS_STR_TO_INT[jour_str], 'heure': f"{h:02d}:{mn:02d}"}


def parse_creneau_dated(text):
    """
    Parse 'lundi 31/08 11h' → {'jour': 0, 'date': '2026-08-31', 'heure': '11:00'}
    Retourne None si non parsable.
    """
    if not text:
        return None
    text = str(text).strip().lower()
    m = re.match(r'^(\w+)\s+(\d{1,2})/(\d{1,2})(?:/\d{2,4})?\s+(\d{1,2})h(\d{0,2})', text)
    if not m:
        return None
    jour_str = m.group(1)
    if jour_str not in JOURS_STR_TO_INT:
        return None
    day = int(m.group(2))
    month = int(m.group(3))
    h = int(m.group(4))
    mn = int(m.group(5)) if m.group(5) else 0
    return {
        'jour': JOURS_STR_TO_INT[jour_str],
        'date': f"{ANNEE_REF:04d}-{month:02d}-{day:02d}",
        'heure': f"{h:02d}:{mn:02d}",
    }


def extract_client_from_cell(text):
    """
    Extrait (prenom, nom) d'une cellule comme "Katia DURAN 1/20" ou "Sophie PETIPREZ (essai)".
    Retourne None si impossible.
    """
    if not text:
        return None
    text = str(text).strip()
    # Retirer annulé/absent en fin
    text = re.sub(r'\s+(annul[éeée]{1,2}|absent[eée]{1,2}|excus[eée]{1,2}|essai|unit[ée])\s*.*$', '', text, flags=re.IGNORECASE)
    # Retirer parenthèses commentaires
    text = re.sub(r'\s*\(.*?\)\s*', ' ', text).strip()
    # Retirer les chiffres finaux (ex: "1/20", "2 semaine/2")
    text = re.sub(r'\s+\d.*$', '', text).strip()

    # Prénom = premier(s) mot(s) en Title Case, nom = mots en UPPER CASE
    # Ex: "Katia DURAN" → prenom=Katia, nom=DURAN
    # Ex: "Marie-Claire DE RYCKE" → prenom=Marie-Claire, nom=DE RYCKE
    # Ex: "Anne Claire DEBARBIEUX" → prenom=Anne Claire, nom=DEBARBIEUX
    m = re.match(
        r'^([A-ZÀÉÈÊÎÏÔÙÛÇ][\wàáâãäåéèêëíìîïóòôõöúùûüç]+(?:[\s\-][A-ZÀÉÈÊÎÏÔÙÛÇ][\wàáâãäåéèêëíìîïóòôõöúùûüç]+)*)'
        r'\s+'
        r'([A-ZÀÉÈÊÎÏÔÙÛÇ][A-ZÀÉÈÊÎÏÔÙÛÇ\s\-]+?)$',
        text
    )
    if m:
        return (normalize_prenom(m.group(1)), normalize_nom(m.group(2)))
    # Fallback : prénom + nom même si nom pas en full upper
    m = re.match(r'^(\S+(?:\s+\S+)?)\s+(\S+(?:\s+\S+)?)$', text)
    if m:
        return (normalize_prenom(m.group(1)), normalize_nom(m.group(2)))
    return None


def parse_pack(pack_str):
    """
    Parse le pack acheté depuis Feuil3 → (forfait, nombre)
    '10' → ('10', 10)  ·  '20' → ('20', 20)  ·  'essai' → ('essai', 1)  ·  'unité' → ('unite', 1)
    """
    if pack_str is None:
        return (None, 0)
    s = str(pack_str).strip().lower()
    if s in ('10', '20'):
        return (s, int(s))
    if 'essai' in s:
        return ('essai', 1)
    if 'unit' in s:
        return ('unite', 1)
    m = re.search(r'(\d+)', s)
    if m:
        return ('autre', int(m.group(1)))
    return (None, 0)


def match_client(prenom, nom, client_ids):
    """
    Tente de matcher un client parmi ceux déjà importés.
    Ordre : match exact → prénom unique → nom unique → prénom + nom similaire.
    """
    # 1. Exact
    key = (prenom, nom)
    if key in client_ids:
        return client_ids[key]
    # 2. Prénom unique
    cands = [(p, n, cid) for (p, n), cid in client_ids.items() if p == prenom]
    if len(cands) == 1:
        return cands[0][2]
    # 3. Nom unique
    cands = [(p, n, cid) for (p, n), cid in client_ids.items() if n == nom]
    if len(cands) == 1:
        return cands[0][2]
    # 4. Similarité : même prénom + nom commence par les 4 mêmes lettres
    norm = lambda s: strip_accents(s).upper()
    for (p, n), cid in client_ids.items():
        if norm(p) == norm(prenom) and norm(nom)[:4] == norm(n)[:4]:
            return cid
    return None


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("Import initial SYNERGIE Cysoing")
    print("=" * 60)
    print(f"\nSource : {XLSX_PATH}")
    print(f"Cible  : {DB_PATH}")
    print("\n[!] TOUTES les donnees actuelles de la base seront ECRASEES.")
    resp = input("Confirmer l'import ? (oui/N) ").strip().lower()
    if resp not in ('o', 'oui', 'y', 'yes'):
        print("Abandon.")
        return

    if not XLSX_PATH.exists():
        print(f"[X] Fichier introuvable : {XLSX_PATH}")
        return

    # --- 1. Reset base ---
    with open(SCHEMA_PATH, encoding='utf-8') as f:
        schema = f.read()
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(schema)
    conn.commit()
    print("[OK] Base reinitialisee depuis schema.sql")

    # --- 2. Charger Excel ---
    wb = openpyxl.load_workbook(XLSX_PATH)
    ws_clients = wb['Feuil3']
    ws_cours = wb['SUIVI COURS']

    # --- 3. Lecture des clients (Feuil3) ---
    clients_raw = []
    for row_idx in range(2, ws_clients.max_row + 1):
        prenom_raw = ws_clients.cell(row=row_idx, column=1).value
        nom_raw = ws_clients.cell(row=row_idx, column=2).value
        if not prenom_raw and not nom_raw:
            continue
        prenom = normalize_prenom(prenom_raw)
        nom = normalize_nom(nom_raw)
        if not prenom or not nom:
            continue

        tel_raw = ws_clients.cell(row=row_idx, column=3).value
        if isinstance(tel_raw, (int, float)):
            tel = str(int(tel_raw))
        elif tel_raw:
            tel = str(tel_raw).strip()
        else:
            tel = None

        pack = ws_clients.cell(row=row_idx, column=4).value
        cours = ws_clients.cell(row=row_idx, column=7).value

        dates = []
        for col_idx in range(8, 28):  # cours 1 à cours 20
            v = ws_clients.cell(row=row_idx, column=col_idx).value
            if isinstance(v, datetime):
                dates.append(v.strftime('%Y-%m-%d'))
            elif isinstance(v, date):
                dates.append(v.strftime('%Y-%m-%d'))

        clients_raw.append({
            'prenom': prenom, 'nom': nom, 'tel': tel,
            'pack': pack, 'cours': cours, 'dates': dates,
        })

    print(f"[OK] {len(clients_raw)} clients lus depuis Feuil3")

    # --- 4. Créneaux uniques ---
    creneaux_uniques = set()
    for c in clients_raw:
        parsed = parse_creneau_recurrent(c['cours'])
        if parsed:
            creneaux_uniques.add((parsed['jour'], parsed['heure']))

    creneau_id_by_key = {}
    for jour, heure in sorted(creneaux_uniques):
        cur = conn.execute(
            'INSERT INTO semaine_type (jour_semaine, heure_debut, duree, type_seance, actif) VALUES (?, ?, ?, ?, 1)',
            (jour, heure, DUREE_DEFAULT, TYPE_SEANCE_DEFAULT)
        )
        creneau_id_by_key[(jour, heure)] = cur.lastrowid
    print(f"[OK] {len(creneau_id_by_key)} creneaux crees : "
          + ", ".join(f"{['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'][j]} {h}" for j, h in sorted(creneaux_uniques)))

    # --- 5. Clients + inscriptions + historique ---
    client_ids = {}
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total_checkins = 0

    for c in clients_raw:
        forfait, pack_nombre = parse_pack(c['pack'])
        nb_dates = len(c['dates'])
        seances_restantes = pack_nombre - nb_dates

        cur = conn.execute('''
            INSERT INTO clients (prenom, nom, telephone, seances_restantes, total_seances_faites)
            VALUES (?, ?, ?, ?, ?)
        ''', (c['prenom'], c['nom'], c['tel'], seances_restantes, nb_dates))
        cid_client = cur.lastrowid
        client_ids[(c['prenom'], c['nom'])] = cid_client

        # Historique NEW_ACCOUNT (avec pack initial si > 0)
        if pack_nombre > 0:
            conn.execute('''
                INSERT INTO historique_seances (client_id, action, nombre, forfait, date_heure)
                VALUES (?, 'NEW_ACCOUNT', ?, ?, ?)
            ''', (cid_client, pack_nombre, forfait, now_str))

        # Historique CHECK-IN pour chaque date de séance
        parsed_creneau = parse_creneau_recurrent(c['cours'])
        heure_cours = (parsed_creneau['heure'] + ':00') if parsed_creneau else '10:00:00'
        for d in c['dates']:
            conn.execute('''
                INSERT INTO historique_seances (client_id, action, nombre, date_heure)
                VALUES (?, 'CHECK-IN', -1, ?)
            ''', (cid_client, f"{d} {heure_cours}"))
            total_checkins += 1

        # Inscription au créneau récurrent
        if parsed_creneau:
            cid_creneau = creneau_id_by_key.get((parsed_creneau['jour'], parsed_creneau['heure']))
            if cid_creneau:
                conn.execute('''
                    INSERT INTO inscriptions (client_id, creneau_id, frequence)
                    VALUES (?, ?, 'hebdo')
                ''', (cid_client, cid_creneau))

    conn.commit()
    print(f"[OK] {len(client_ids)} clients crees, {total_checkins} CHECK-IN historiques")

    # --- 6. Cours annulés (col J = 'annulé') ---
    annulations = 0
    warnings = []
    for row_idx in range(2, ws_cours.max_row + 1):
        cell_a = ws_cours.cell(row=row_idx, column=1).value
        if not cell_a:
            continue
        parsed = parse_creneau_dated(str(cell_a))
        if not parsed:
            continue
        cell_j = ws_cours.cell(row=row_idx, column=10).value
        if cell_j and 'annul' in str(cell_j).lower():
            cid_creneau = creneau_id_by_key.get((parsed['jour'], parsed['heure']))
            if cid_creneau:
                try:
                    conn.execute('''
                        INSERT INTO annulations_cours (creneau_id, date_seance, raison)
                        VALUES (?, ?, 'Importe depuis SYNERGIE')
                    ''', (cid_creneau, parsed['date']))
                    annulations += 1
                except sqlite3.IntegrityError:
                    pass
            else:
                warnings.append(f"Annulation : creneau inconnu pour '{cell_a}' (jour {parsed['jour']} heure {parsed['heure']})")
    conn.commit()
    print(f"[OK] {annulations} cours annules importes")

    # --- 7. Previsions (cellules vertes theme:8 sur cours futurs) ---
    previsions_ok = 0
    previsions_ko = []
    today = date.today()
    for row_idx in range(2, ws_cours.max_row + 1):
        cell_a = ws_cours.cell(row=row_idx, column=1).value
        if not cell_a:
            continue
        parsed = parse_creneau_dated(str(cell_a))
        if not parsed:
            continue
        cours_date = datetime.strptime(parsed['date'], '%Y-%m-%d').date()
        # Ne prendre que les cours à venir (les orange sur cours passes sont deja gerees par les CHECK-IN)
        if cours_date < today:
            continue
        cid_creneau = creneau_id_by_key.get((parsed['jour'], parsed['heure']))
        if not cid_creneau:
            continue

        for col_idx in range(2, 10):
            cell = ws_cours.cell(row=row_idx, column=col_idx)
            if not cell.value:
                continue
            fill = cell.fill
            if (fill.patternType == 'solid'
                    and fill.fgColor.type == 'theme'
                    and fill.fgColor.theme == THEME_PREVU):
                name = extract_client_from_cell(cell.value)
                if not name:
                    previsions_ko.append(f"R{row_idx}C{col_idx} : nom illisible '{cell.value}'")
                    continue
                cid_client = match_client(name[0], name[1], client_ids)
                if cid_client is None:
                    previsions_ko.append(f"R{row_idx}C{col_idx} : client introuvable '{name[0]} {name[1]}'")
                    continue
                try:
                    conn.execute('''
                        INSERT INTO previsions (client_id, creneau_id, date_seance)
                        VALUES (?, ?, ?)
                    ''', (cid_client, cid_creneau, parsed['date']))
                    previsions_ok += 1
                except sqlite3.IntegrityError:
                    pass

    conn.commit()
    print(f"[OK] {previsions_ok} previsions importees")

    # --- Rapport ---
    print("\n" + "=" * 60)
    print("RAPPORT FINAL")
    print("=" * 60)
    print(f"  Clients importes       : {len(client_ids)}")
    print(f"  Creneaux crees         : {len(creneau_id_by_key)}")
    print(f"  CHECK-IN historiques   : {total_checkins}")
    print(f"  Cours annules          : {annulations}")
    print(f"  Previsions             : {previsions_ok}")

    all_warnings = warnings + previsions_ko
    if all_warnings:
        print(f"\n[!] {len(all_warnings)} warnings (nom illisible / client introuvable) :")
        for w in all_warnings[:20]:
            print(f"    - {w}")
        if len(all_warnings) > 20:
            print(f"    ... et {len(all_warnings) - 20} autre(s)")

    conn.close()
    print("\n[OK] Import termine.")


if __name__ == '__main__':
    main()
