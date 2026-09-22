# -*- coding: utf-8 -*-
"""
Migration : ajoute la colonne `annulee` (INTEGER DEFAULT 0)
a la table historique_seances si elle n'existe pas deja.

A executer :
    python migrate_add_annulee.py

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

    # Verifie si la colonne existe deja
    cur.execute("PRAGMA table_info(historique_seances)")
    cols = [row[1] for row in cur.fetchall()]

    if 'annulee' in cols:
        print("[OK] La colonne 'annulee' existe deja. Rien a faire.")
    else:
        cur.execute("ALTER TABLE historique_seances ADD COLUMN annulee INTEGER DEFAULT 0")
        conn.commit()
        print("[OK] Colonne 'annulee' ajoutee a historique_seances.")

    conn.close()


if __name__ == "__main__":
    main()
