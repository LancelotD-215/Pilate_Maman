# -*- coding: utf-8 -*-
"""
Migration : ajoute la colonne `notes` (TEXT DEFAULT '')
a la table clients si elle n'existe pas deja.

A executer :
    python migrate_add_notes.py

Sans risque : idempotent (ne fait rien si deja migre).
"""
import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database_clients.db")


def main():
    if not os.path.exists(DB_PATH):
        print(f"[!] Base introuvable : {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(clients)")
    cols = [row[1] for row in cur.fetchall()]

    if 'notes' in cols:
        print("[OK] La colonne 'notes' existe deja. Rien a faire.")
    else:
        cur.execute("ALTER TABLE clients ADD COLUMN notes TEXT DEFAULT ''")
        conn.commit()
        print("[OK] Colonne 'notes' ajoutee a clients.")

    conn.close()


if __name__ == "__main__":
    main()
