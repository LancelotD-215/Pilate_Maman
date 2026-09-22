# -*- coding: utf-8 -*-
"""
Renomme le cours de lundi 11h00 en "Pilates Stretching".

Idempotent : ne fait rien si le cours est deja renomme.
A executer sur la BDD locale et/ou sur celle de prod :

    python rename_pilates_stretching.py
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
    conn.row_factory = sqlite3.Row

    # Cible : jour_semaine=0 (lundi) et heure_debut='11:00'
    row = conn.execute(
        "SELECT id, type_seance FROM semaine_type WHERE jour_semaine = 0 AND heure_debut = '11:00'"
    ).fetchone()

    if not row:
        print("[!] Aucun creneau trouve pour Lundi 11:00.")
        conn.close()
        return

    if row['type_seance'] == 'Pilates Stretching':
        print("[OK] Le creneau Lundi 11:00 est deja 'Pilates Stretching'. Rien a faire.")
    else:
        conn.execute(
            "UPDATE semaine_type SET type_seance = 'Pilates Stretching' WHERE id = ?",
            (row['id'],)
        )
        conn.commit()
        print(f"[OK] Creneau id={row['id']} renomme : '{row['type_seance']}' -> 'Pilates Stretching'")

    conn.close()


if __name__ == "__main__":
    main()
