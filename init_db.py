# -*- coding: utf-8 -*-
"""
author: @lancelot
name : init_db.py
description : initialise une base de données SQLite vide à partir de schema.sql.
              À utiliser pour un nouveau déploiement (production) ou pour repartir
              d'une base propre. Aucune donnée n'est insérée.
              Pour une base avec un jeu de test, voir init_db_test.py.

Usage :
    python init_db.py
"""

import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database_clients.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def init_db():
    """Crée database_clients.db à partir de schema.sql. Écrase toute base existante."""
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
    connection.commit()
    connection.close()

    print(f"[OK] Base creee : {DB_PATH}")
    print("   -> Aucune donnee inseree. Ajouter clients et creneaux via l'interface web.")


if __name__ == "__main__":
    init_db()
