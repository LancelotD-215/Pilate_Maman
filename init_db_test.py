# -*- coding: utf-8 -*-
"""
author: @lancelot
name : init_db_test.py
description : initialise une base SQLite avec un jeu de données de démonstration
              (emploi du temps type + clients de test + historique).
              À utiliser pour le développement local.
              Pour une base 100 % vide, voir init_db.py.

Usage :
    python init_db_test.py
"""

import os
import sqlite3
from datetime import datetime, timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database_clients.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


# --- Emploi du temps de démonstration ---
# (jour_semaine 0=Lundi..6=Dimanche, heure_debut "HH:MM", duree_min, type_seance, actif)
CRENEAUX_DEMO = [
    (0, "09:30", 60, "Cours 1", 1),   # Lundi 9h30
    (0, "18:00", 60, "Cours 2", 1),   # Lundi 18h
    (2, "10:00", 60, "Cours 1", 1),   # Mercredi 10h
    (3, "19:00", 60, "Cours 3", 1),   # Jeudi 19h
    (4, "12:00", 45, "Cours 2", 1),   # Vendredi midi
]

# --- Clients de démonstration ---
# (prenom, nom, seances_restantes, total_seances_faites, telephone, email)
CLIENTS_DEMO = [
    ("Alice",  "Test",     10, 2,  "0600000001", "alice@test.local"),
    ("Bob",    "Demo",      5, 8,  "0600000002", "bob@test.local"),
    ("Chloe",  "Exemple",   0, 15, "0600000003", None),
    ("David",  "Fixture",  -2, 20, None,         "david@test.local"),
]

# --- Inscriptions (client_index dans CLIENTS_DEMO -> [creneau_index dans CRENEAUX_DEMO]) ---
INSCRIPTIONS_DEMO = {
    0: [0, 2],   # Alice : Lundi 9h30 + Mercredi 10h
    1: [1],      # Bob   : Lundi 18h
    2: [3],     # Chloe : Jeudi 19h
    3: [0, 4],   # David : Lundi 9h30 + Vendredi midi
}


def init_db_test():
    """Crée database_clients.db avec un jeu de données de démonstration. Écrase toute base existante."""
    if os.path.exists(DB_PATH):
        confirm = input(f"[!] '{DB_PATH}' existe deja. Ecraser ? (o/N) ").strip().lower()
        if confirm != "o":
            print("Abandon.")
            return
        os.remove(DB_PATH)

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()

    connection = sqlite3.connect(DB_PATH)
    connection.executescript(schema)

    # Insertion des créneaux
    connection.executemany(
        "INSERT INTO semaine_type (jour_semaine, heure_debut, duree, type_seance, actif) VALUES (?, ?, ?, ?, ?)",
        CRENEAUX_DEMO,
    )
    creneau_ids = [row[0] for row in connection.execute("SELECT id FROM semaine_type ORDER BY id").fetchall()]

    # Insertion des clients + entrée NEW_ACCOUNT dans l'historique
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    client_ids = []
    for prenom, nom, restantes, faites, tel, email in CLIENTS_DEMO:
        cur = connection.execute(
            "INSERT INTO clients (prenom, nom, seances_restantes, total_seances_faites, telephone, email) VALUES (?, ?, ?, ?, ?, ?)",
            (prenom, nom, restantes, faites, tel, email),
        )
        client_ids.append(cur.lastrowid)
        connection.execute(
            "INSERT INTO historique_seances (client_id, action, nombre, date_heure) VALUES (?, ?, ?, ?)",
            (cur.lastrowid, "NEW_ACCOUNT", restantes, now),
        )

    # Insertion des inscriptions
    for client_idx, creneau_indices in INSCRIPTIONS_DEMO.items():
        for creneau_idx in creneau_indices:
            connection.execute(
                "INSERT INTO inscriptions (client_id, creneau_id) VALUES (?, ?)",
                (client_ids[client_idx], creneau_ids[creneau_idx]),
            )

    # Un check-in "il y a 2 jours" pour rendre les widgets non vides
    past = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    connection.execute(
        "INSERT INTO historique_seances (client_id, action, nombre, date_heure) VALUES (?, ?, ?, ?)",
        (client_ids[0], "CHECK-IN", -1, past),
    )

    connection.commit()
    connection.close()

    print(f"[OK] Base de test creee : {DB_PATH}")
    print(f"   -> {len(CRENEAUX_DEMO)} creneaux, {len(CLIENTS_DEMO)} clients, historique de demo.")


if __name__ == "__main__":
    init_db_test()
