# -*- coding: utf-8 -*-
"""
author: @lancelot
name :  app_lib.py
description : bibliothèque de fonctions pour l'application Flask de gestion des clients de Pilates
date : 2026/01/21
"""


# imports des modules
import sqlite3
from datetime import datetime, timedelta
import locale
import os

# On récupère le chemin de la RACINE du projet (dossier parent de app/)
# __file__ = ce fichier (app/app_lib.py)
# dirname(__file__) = son dossier (app/)
# '..' = on remonte d'un cran pour arriver à la racine
# abspath = simplifie le tout en chemin absolu propre
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# On crée le chemin complet vers la base de données (à la racine du projet)
DB_PATH = os.path.join(BASE_DIR, "database_clients.db")

# création des fonctions utilitaires
def get_db_connection():
    """
    Fonction de connexion à la base de données.
    Appelée à chaque requête pour lire ou écrire des données.
    Args:j
        None
    Returns:
        sqlite3.Connection: lien de connexion à la base de données.
    """
    # connection à la base de données
    connection = sqlite3.connect(DB_PATH)

    # pour accéder aux colonnes par nom et non par index
    connection.row_factory = sqlite3.Row
    return connection



def get_best_clients(since_date, until_date):
    """
    Fonction pour récupérer le meilleur client depuis une date donnée. (celui qui a utilisé le plus de séances)
    Args:
        since_date (str): date au format 'YYYY-MM-DD' pour filtrer le début des actions.
        until_date (str): date au format 'YYYY-MM-DD' pour filtrer la fin des actions.
    Returns:
        list: liste des clients avec le nombre de séances utilisées.
    """
    connection = get_db_connection()

    query = """
        SELECT c.prenom, c.nom, COUNT(h.id) AS seances_utilisees
        FROM historique_seances h
        JOIN clients c ON h.client_id = c.id
        WHERE h.action IN ('CHECK-IN', 'PRESENCE_VALIDEE')
        AND DATE(h.date_heure) BETWEEN ? AND ?
        GROUP BY c.id
        ORDER BY seances_utilisees DESC
        LIMIT 1;  
    """

    result = connection.execute(query, (since_date, until_date)).fetchone()
    connection.close()
    return result




def get_client_most_remaining():
    """
    Fonction pour récupérer le client avec le plus de séances restantes.
    Args:
        None
    Returns:
        sqlite3.Row: ligne contenant les informations du client.
    """
    connection = get_db_connection()

    query = """
        SELECT prenom, nom, seances_restantes
        FROM clients
        ORDER BY seances_restantes DESC
        LIMIT 1;
    """

    result = connection.execute(query).fetchone()
    connection.close()
    return result




def get_number_seances(since_date, until_date):
    """
    Fonction pour récupérer le nombre total de séances donnée par le prof depuis une date donnée.
    Compte les créneaux de semaine_type qui ont eu au moins un CHECK-IN.
    Args:
        since_date (str): date au format 'YYYY-MM-DD' pour filtrer le début des actions.
        until_date (str): date au format 'YYYY-MM-DD' pour filtrer la fin des actions.
    Returns:
        int: nombre total de séances données.
    """
    connection = get_db_connection()

    # Récupérer tous les CHECK-IN dans la période avec date/heure détaillée
    query_checkins = """
        SELECT date_heure
        FROM historique_seances
        WHERE action IN ('CHECK-IN', 'PRESENCE_VALIDEE')
        AND DATE(date_heure) BETWEEN ? AND ?
    """
    
    checkins = connection.execute(query_checkins, (since_date, until_date)).fetchall()
    
    if not checkins:
        connection.close()
        return 0

    # Récupérer tous les créneaux actifs
    query_creneaux = """
        SELECT id, jour_semaine, heure_debut, duree
        FROM semaine_type
        WHERE actif = 1
    """
    
    creneaux = connection.execute(query_creneaux).fetchall()
    connection.close()

    # Set pour éviter les doublons de créneaux
    seances_donnees = set()
    
    for checkin in checkins:
        # Convertir le CHECK-IN en datetime Python
        date_str = checkin['date_heure'].replace('T', ' ')  # Gérer le format ISO avec T
        checkin_dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        jour_semaine = checkin_dt.weekday()  # 0=lundi, 1=mardi, etc.
        heure_checkin = checkin_dt.time()
        
        # Trouver le créneau correspondant
        for creneau in creneaux:
            if creneau['jour_semaine'] == jour_semaine:
                # Parser l'heure de début du créneau
                heure_debut = datetime.strptime(creneau['heure_debut'], '%H:%M').time()
                
                # Calculer l'heure de fin (début + durée)
                debut_dt = datetime.combine(checkin_dt.date(), heure_debut)
                fin_dt = debut_dt + timedelta(minutes=creneau['duree'])
                heure_fin = fin_dt.time()
                
                # Vérifier si le CHECK-IN est dans cette plage horaire
                if heure_debut <= heure_checkin <= heure_fin:
                    seances_donnees.add(creneau['id'])
                    break  # On a trouvé le bon créneau, pas besoin de chercher plus
    
    return len(seances_donnees)


def get_negative_seances_clients():
    """
    Fonction pour récupérer la liste des clients avec un solde négatif de séances.
    Args:
        None
    Returns:
        list: liste des clients avec un solde négatif de séances.
    """
    connection = get_db_connection()

    query = """
        SELECT id, prenom, nom, seances_restantes
        FROM clients
        WHERE seances_restantes < 0
        ORDER BY seances_restantes ASC
    """

    results = connection.execute(query).fetchall()
    connection.close()
    return results


def get_zero_clients():
    """
    Fonction pour récupérer la liste des clients avec un solde de séances à zéro.
    Args:
        None
    Returns:
        list: liste des clients avec un solde de séances à zéro.
    """
    connection = get_db_connection()

    query = """
        SELECT id, prenom, nom, seances_restantes
        FROM clients
        WHERE seances_restantes = 0
        ORDER BY nom ASC, prenom ASC
    """

    results = connection.execute(query).fetchall()
    connection.close()
    return results


def client_not_comming(since_date, until_date):
    """
    Fonction pour récupérer la liste des clients qui n'ont pas utilisé de séances depuis une date donnée.
    Args:
        since_date (str): date au format 'YYYY-MM-DD' pour filtrer le début des actions.
        until_date (str): date au format 'YYYY-MM-DD' pour filtrer la fin des actions.
    Returns:
        list: liste des clients qui n'ont pas utilisé de séances dans la période donnée.
    """
    connection = get_db_connection()

    query = """
        SELECT c.id, c.prenom, c.nom
        FROM clients c
        LEFT JOIN historique_seances h ON c.id = h.client_id 
            AND h.action IN ('CHECK-IN', 'PRESENCE_VALIDEE') 
            AND DATE(h.date_heure) BETWEEN ? AND ?
        WHERE h.id IS NULL
        ORDER BY c.nom ASC, c.prenom ASC
    """

    results = connection.execute(query, (since_date, until_date)).fetchall()
    connection.close()
    return results


# ============================================================
# Widgets ajoutés en V2 : prochain cours, aperçu jour, fidèles, etc.
# ============================================================

# Mois en français (pour labels des graphs)
_MONTHS_FR = ['Jan', 'Fev', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Aout', 'Sept', 'Oct', 'Nov', 'Dec']


def get_prochain_cours(now):
    """
    Retourne le prochain créneau du jour (à venir) avec son nb d'inscrits.
    Args:
        now (datetime): heure actuelle (aware, ex: datetime.now(paris_tz))
    Returns:
        dict ou None : {id, heure_debut, duree, type_seance, nb_inscrits} ou None si aucun.
    """
    day_of_week = now.weekday()
    current_time = now.strftime('%H:%M')

    connection = get_db_connection()
    row = connection.execute('''
        SELECT s.id, s.heure_debut, s.duree, s.type_seance,
               (SELECT COUNT(*) FROM inscriptions WHERE creneau_id = s.id) AS nb_inscrits
        FROM semaine_type s
        WHERE s.jour_semaine = ?
          AND s.heure_debut > ?
          AND s.actif = 1
        ORDER BY s.heure_debut ASC
        LIMIT 1
    ''', (day_of_week, current_time)).fetchone()
    connection.close()
    return dict(row) if row else None


def get_apercu_jour(now):
    """
    Retourne l'aperçu de la journée : nb de cours restants + total d'inscrits attendus.
    """
    day_of_week = now.weekday()
    current_time = now.strftime('%H:%M')

    connection = get_db_connection()
    row = connection.execute('''
        SELECT COUNT(*) AS nb_cours,
               COALESCE(SUM((SELECT COUNT(*) FROM inscriptions WHERE creneau_id = s.id)), 0) AS total_inscrits
        FROM semaine_type s
        WHERE s.jour_semaine = ?
          AND s.heure_debut > ?
          AND s.actif = 1
    ''', (day_of_week, current_time)).fetchone()
    connection.close()
    return {'nb_cours': row['nb_cours'], 'total_inscrits': row['total_inscrits']}


def get_nouveaux_clients_mois(first_day_of_month):
    """Retourne le nb de clients inscrits depuis le début du mois."""
    connection = get_db_connection()
    row = connection.execute(
        'SELECT COUNT(*) AS nb FROM clients WHERE date_inscription >= ?',
        (first_day_of_month,)
    ).fetchone()
    connection.close()
    return row['nb']


def get_fideles(seuil=20):
    """Retourne le nb de clients ayant fait au moins `seuil` séances au total."""
    connection = get_db_connection()
    row = connection.execute(
        'SELECT COUNT(*) AS nb FROM clients WHERE total_seances_faites >= ?',
        (seuil,)
    ).fetchone()
    connection.close()
    return row['nb']


def get_evolution_achats(now, n_months=6):
    """
    Retourne l'évolution du nb de séances vendues (ADD_SEANCES) sur N derniers mois.
    Args:
        now (datetime): date de référence.
        n_months (int): nombre de mois à couvrir.
    Returns:
        list de dicts : [{label, value}, ...] du plus ancien au plus récent.
    """
    connection = get_db_connection()
    result = []
    for i in range(n_months - 1, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        start = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end = f"{year+1:04d}-01-01"
        else:
            end = f"{year:04d}-{month+1:02d}-01"

        row = connection.execute('''
            SELECT COALESCE(SUM(nombre), 0) AS total
            FROM historique_seances
            WHERE action = 'ADD_SEANCES'
              AND date_heure >= ? AND date_heure < ?
        ''', (start, end)).fetchone()

        result.append({'label': _MONTHS_FR[month - 1], 'value': row['total']})
    connection.close()
    return result


def get_evolution_clients(now, n_months=12):
    """
    Retourne l'évolution cumulée du nb total de clients sur N derniers mois.
    Returns:
        list de dicts : [{label, value}, ...] du plus ancien au plus récent.
    """
    connection = get_db_connection()
    result = []
    for i in range(n_months - 1, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        if month == 12:
            end = f"{year+1:04d}-01-01"
        else:
            end = f"{year:04d}-{month+1:02d}-01"

        row = connection.execute(
            'SELECT COUNT(*) AS total FROM clients WHERE date_inscription < ?',
            (end,)
        ).fetchone()

        result.append({'label': _MONTHS_FR[month - 1], 'value': row['total']})
    connection.close()
    return result


def get_presents_vs_inscrits(now, n_weeks=4, top=6):
    """
    Pour chaque créneau récurrent avec au moins 1 inscrit, calcule le nb moyen
    de présents sur les N dernières semaines (via les check-ins). Retourne les
    `top` créneaux les plus inscrits.
    """
    connection = get_db_connection()
    JOURS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

    creneaux = connection.execute('''
        SELECT s.id, s.jour_semaine, s.heure_debut, s.type_seance, s.duree,
               (SELECT COUNT(*) FROM inscriptions WHERE creneau_id = s.id) AS nb_inscrits
        FROM semaine_type s
        WHERE s.actif = 1
        ORDER BY s.jour_semaine, s.heure_debut
    ''').fetchall()

    result = []
    for c in creneaux:
        if c['nb_inscrits'] == 0:
            continue

        h, m = map(int, c['heure_debut'].split(':'))
        start_min = h * 60 + m - 30
        end_min = h * 60 + m + c['duree']

        total_presents = 0
        weeks_counted = 0

        for w in range(n_weeks):
            weeks_ago = now - timedelta(weeks=w)
            days_diff = (weeks_ago.weekday() - c['jour_semaine']) % 7
            occurrence_date = weeks_ago - timedelta(days=days_diff)
            if occurrence_date.date() > now.date():
                continue

            date_str = occurrence_date.strftime('%Y-%m-%d')
            checkins = connection.execute('''
                SELECT DISTINCT client_id, date_heure
                FROM historique_seances
                WHERE action IN ('CHECK-IN', 'PRESENCE_VALIDEE')
                  AND DATE(date_heure) = ?
            ''', (date_str,)).fetchall()

            nb_in_slot = 0
            for ck in checkins:
                ck_str = ck['date_heure'].replace('T', ' ').split('.')[0]
                ck_dt = datetime.strptime(ck_str, '%Y-%m-%d %H:%M:%S')
                ck_min = ck_dt.hour * 60 + ck_dt.minute
                if start_min <= ck_min <= end_min:
                    nb_in_slot += 1

            total_presents += nb_in_slot
            weeks_counted += 1

        avg_presents = round(total_presents / max(weeks_counted, 1))
        taux = round((avg_presents / c['nb_inscrits']) * 100) if c['nb_inscrits'] > 0 else 0

        result.append({
            'jour': JOURS[c['jour_semaine']],
            'heure': c['heure_debut'],
            'type': c['type_seance'],
            'nb_inscrits': c['nb_inscrits'],
            'nb_presents_avg': avg_presents,
            'taux': taux,
        })

    connection.close()
    result.sort(key=lambda x: -x['nb_inscrits'])
    return result[:top]


def get_suggestions_inscription(now, min_consecutive=4, weeks_lookback=6):
    """
    Détecte les clients qui font des check-ins réguliers à un créneau
    sans y être inscrits (au moins `min_consecutive` occurrences consécutives).
    Retourne une liste de suggestions à afficher sur le dashboard.

    Args:
        now (datetime): date de référence aware.
        min_consecutive (int): nombre de check-ins consécutifs requis (défaut 4).
        weeks_lookback (int): profondeur de recherche en semaines (défaut 6).
    Returns:
        list de dicts : [{client_id, prenom, nom, creneau_id, creneau_label, streak}, ...]
    """
    connection = get_db_connection()
    JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

    # Set des (client_id, creneau_id) déjà inscrits
    inscriptions_existantes = set(
        (row['client_id'], row['creneau_id'])
        for row in connection.execute('SELECT client_id, creneau_id FROM inscriptions').fetchall()
    )

    # Créneaux actifs
    creneaux = connection.execute(
        'SELECT id, jour_semaine, heure_debut, duree, type_seance FROM semaine_type WHERE actif = 1'
    ).fetchall()

    suggestions = []

    for creneau in creneaux:
        h, m = map(int, creneau['heure_debut'].split(':'))
        start_min = h * 60 + m - 30
        end_min = h * 60 + m + creneau['duree']

        # Dates des N dernières occurrences (du + récent au + ancien)
        occurrences_dates = []
        for w in range(weeks_lookback):
            weeks_ago = now - timedelta(weeks=w)
            days_diff = (weeks_ago.weekday() - creneau['jour_semaine']) % 7
            occurrence = weeks_ago - timedelta(days=days_diff)
            if occurrence.date() > now.date():
                continue
            occurrences_dates.append(occurrence.strftime('%Y-%m-%d'))

        # Récupérer tous les check-ins pendant ces occurrences dans la plage horaire
        checkins_by_client = {}
        for date_str in occurrences_dates:
            checkins = connection.execute('''
                SELECT h.client_id, h.date_heure, c.prenom, c.nom
                FROM historique_seances h
                JOIN clients c ON h.client_id = c.id
                WHERE h.action IN ('CHECK-IN', 'PRESENCE_VALIDEE')
                  AND DATE(h.date_heure) = ?
            ''', (date_str,)).fetchall()

            for ck in checkins:
                ck_str = ck['date_heure'].replace('T', ' ').split('.')[0]
                ck_dt = datetime.strptime(ck_str, '%Y-%m-%d %H:%M:%S')
                ck_min = ck_dt.hour * 60 + ck_dt.minute
                if start_min <= ck_min <= end_min:
                    if ck['client_id'] not in checkins_by_client:
                        checkins_by_client[ck['client_id']] = {
                            'dates': set(),
                            'prenom': ck['prenom'],
                            'nom': ck['nom'],
                        }
                    checkins_by_client[ck['client_id']]['dates'].add(date_str)

        # Pour chaque client : calculer la streak depuis la plus récente occurrence
        for client_id, data in checkins_by_client.items():
            # Skip si déjà inscrit à ce créneau (suggestion inutile)
            if (client_id, creneau['id']) in inscriptions_existantes:
                continue

            streak = 0
            for date_str in occurrences_dates:  # ordre : plus récent → plus ancien
                if date_str in data['dates']:
                    streak += 1
                else:
                    break

            if streak >= min_consecutive:
                suggestions.append({
                    'client_id': client_id,
                    'prenom': data['prenom'],
                    'nom': data['nom'],
                    'creneau_id': creneau['id'],
                    'creneau_label': f"{JOURS[creneau['jour_semaine']]} {creneau['heure_debut']} — {creneau['type_seance']}",
                    'streak': streak,
                })

    connection.close()
    return suggestions