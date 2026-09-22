# -*- coding: utf-8 -*-
"""
author: @lancelot
name : app/main.py
description : code principal de l'application Flask pour la gestion des clients de Pilates
              (Flask app + toutes les routes, dans un seul fichier).
              Lancement via run.py à la racine du projet.
date : 2026/01/20
"""

# imports des modules
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, make_response, session
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash
from app.app_lib import (
    client_not_comming,
    get_db_connection,
    get_best_clients,
    get_client_most_remaining,
    get_number_seances,
    get_negative_seances_clients,
    get_zero_clients,
    # widgets V2
    get_prochain_cours,
    get_apercu_jour,
    get_nouveaux_clients_mois,
    get_fideles,
    get_evolution_achats,
    get_evolution_clients,
    get_presents_vs_inscrits,
    get_suggestions_inscription,
    # fréquence bimensuelle
    is_inscription_active_this_week,
)
from dotenv import load_dotenv
import pytz
import os

# Charge les variables du fichier .env vers les variables d'environnement,
# pour que os.environ.get(...) ci-dessous puisse les lire.
load_dotenv()

# ============================================================
# CONFIGURATION — lue depuis le fichier .env
# (voir .env.example pour le modèle des variables à définir)
# ============================================================
# Nom du site affiché en haut de chaque page (fallback si .env absent)
SITE_NAME = os.environ.get('SITE_NAME', 'Gestion Pilates')

# Identifiants admin (accès à l'espace de gestion)
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD_HASH = os.environ['ADMIN_PASSWORD_HASH']  # obligatoire : plante si absent

# Clé secrète Flask (signature des cookies de session) - obligatoire
SECRET_KEY = os.environ['SECRET_KEY']

# On est en prod si FLASK_ENV=production dans le .env, sinon en dev (par défaut)
IS_PROD = os.environ.get('FLASK_ENV') == 'production'
# ============================================================


# création de l'application Flask
app = Flask(__name__) # création du site web
app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = not IS_PROD  # debug ON en dev, OFF en prod

# durée de vie de la session si "Rester connecté" est coché
app.permanent_session_lifetime = timedelta(days=30)

# récupération de l'heure de paris
paris_tz = pytz.timezone('Europe/Paris')


# --- AUTHENTIFICATION ---
# pages accessibles SANS être connecté (la borne reste publique pour les clients)
PUBLIC_ENDPOINTS = {'login', 'borne', 'borne_succes', 'static'}


# === WIDGETS DASHBOARD ===
# Config par défaut (tous actifs) + libellés user-friendly pour la modale de personnalisation.
# L'utilisateur peut activer/désactiver individuellement via le bouton "Personnaliser".
DEFAULT_WIDGETS_CONFIG = {
    # Quick stats (choisis dans le sélecteur "Personnaliser")
    'prochain_cours':            True,
    'apercu_jour':               True,
    'best_client_month':         True,
    'nouveaux_clients':          True,
    'total_clients':             True,
    'fideles':                   True,
    'most_remaining':            True,
    'client_not_comming':        True,
    # Graphs (choisis dans le sélecteur "Personnaliser")
    'evolution_achats':          True,
    'evolution_clients':         True,
    'presents_vs_inscrits':      True,
}

# NOTE : les alertes (soldes négatifs, soldes à zéro, suggestions d'inscription)
# ne sont PAS dans WIDGET_LABELS : elles s'affichent TOUJOURS quand il y a de
# la data à alerter (ce sont des infos critiques, pas des widgets optionnels).

WIDGET_LABELS = {
    'prochain_cours':            ("Prochain cours", "Le prochain cours de la journée"),
    'apercu_jour':               ("Aperçu du jour", "Nombre de cours restants aujourd'hui + inscrits"),
    'best_client_month':         ("Meilleur client du mois", "Client ayant fait le plus de séances ce mois"),
    'nouveaux_clients':          ("Nouveaux clients", "Nombre d'inscriptions ce mois"),
    'total_clients':             ("Total clients", "Nombre total de clients inscrits"),
    'fideles':                   ("Clients fidèles", "Clients ayant fait plus de 20 séances"),
    'most_remaining':            ("Plus grand solde", "Client avec le plus de séances restantes"),
    'client_not_comming':        ("Clients absents 30 jours", "Clients à relancer"),
    'evolution_achats':          ("Séances vendues (6 mois)", "Bar chart des séances vendues par mois"),
    'evolution_clients':         ("Évolution clients (12 mois)", "Courbe du nb total de clients inscrits"),
    'presents_vs_inscrits':      ("Présents vs Inscrits", "Comparaison inscrits / réellement présents par créneau"),
}


@app.context_processor
def inject_site_name():
    """Rend SITE_NAME disponible dans tous les templates via {{ site_name }}."""
    return {'site_name': SITE_NAME}


@app.before_request
def require_login():
    """
    Avant chaque requête, on vérifie que l'utilisateur est connecté,
    sauf pour les pages publiques (borne, page de connexion, fichiers statiques).
    """
    # on laisse passer les pages publiques et les requêtes sans endpoint (404)
    if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint is None:
        return
    # sinon, connexion obligatoire
    if not session.get('logged_in'):
        return redirect(url_for('login', next=request.path))


@app.template_filter('format_datetime')
def format_datetime(value, format="%d/%m/%Y à %H:%M"):
    """Filtre Jinja pour formater les dates proprement."""
    if value is None:
        return ""

    # Si c'est déjà un objet datetime, on formate direct
    if isinstance(value, datetime):
        return value.strftime(format)

    # Si c'est une string (ex: venant de SQLite), on essaie de la parser
    try:
        # On nettoie le 'T' éventuel et les microsecondes
        value = value.replace('T', ' ').split('.')[0]
        dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return dt.strftime(format)
    except ValueError:
        # Si ça ne marche pas (ex: format date seul YYYY-MM-DD), on essaie juste la date
        try:
            dt = datetime.strptime(value, '%Y-%m-%d')
            return dt.strftime('%d/%m/%Y')
        except ValueError:
            return value # On renvoie tel quel si on n'y arrive pas




# création des routes pour le site web (pages)
@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Page de connexion à l'espace d'administration.
    Args:
        None
    Returns:
        str: rendu HTML de la page de connexion, ou redirection si succès.
    """
    # si déjà connecté, on redirige vers l'accueil
    if session.get('logged_in'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember')  # case "Rester connecté"

        # vérification de l'identifiant et du mot de passe
        if username.lower() == ADMIN_USERNAME.lower() and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['logged_in'] = True
            # "Rester connecté" => session persistante (cookie 30 jours), sinon session de navigation
            session.permanent = bool(remember)

            # redirection vers la page demandée initialement (en restant sur le site)
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('index'))
        else:
            return render_template('login.html', erreur="Identifiant ou mot de passe incorrect.")

    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    Déconnexion : vide la session et supprime le cookie de connexion.
    Args:
        None
    Returns:
        str: redirection vers la page de connexion.
    """
    session.clear()
    return redirect(url_for('login'))


@app.route('/save_widgets_config', methods=['POST'])
def save_widgets_config():
    """
    Sauvegarde en session la configuration des widgets choisie via la modale
    "Personnaliser" du tableau de bord. Un widget est activé si sa checkbox
    est cochée (présente dans le form), sinon désactivé.
    """
    new_config = {key: (key in request.form) for key in DEFAULT_WIDGETS_CONFIG}
    session['widgets_config'] = new_config
    session.modified = True
    return redirect(url_for('index'))


@app.route('/')
def index():
    """
    Fonction exécutée lors de l'accès à la page d'accueil ('/').
    Args:
        None
    Returns:
        str: rendu HTML de la page d'accueil.
    """
    connection = get_db_connection()

    # === CONFIGURATION DES WIDGETS ===
    # Config par défaut si l'utilisateur n'a rien personnalisé. Persistée en session
    # via /save_widgets_config (bouton "Personnaliser" sur la dashboard).
    widgets_config = session.get('widgets_config', DEFAULT_WIDGETS_CONFIG.copy())

    now = datetime.now(paris_tz)
    actual_date = now.strftime('%Y-%m-%d')
    first_day_of_month = actual_date[:8] + '01'

    # === COLLECTE DES DONNÉES ===

    # Alertes : TOUJOURS chargées (pas optionnelles — infos critiques)
    negative_clients = get_negative_seances_clients()
    zero_clients = get_zero_clients()

    # Quick stats non-graphiques
    prochain_cours = get_prochain_cours(now) if widgets_config['prochain_cours'] else None
    apercu_jour = get_apercu_jour(now) if widgets_config['apercu_jour'] else None
    best_clients_month = get_best_clients(first_day_of_month, actual_date) if widgets_config['best_client_month'] else None
    nouveaux_clients = get_nouveaux_clients_mois(first_day_of_month) if widgets_config['nouveaux_clients'] else None
    total_clients = connection.execute('SELECT COUNT(*) AS total FROM clients').fetchone()['total'] if widgets_config['total_clients'] else None
    fideles = get_fideles(seuil=20) if widgets_config['fideles'] else None
    client_most_remaining = get_client_most_remaining() if widgets_config['most_remaining'] else None
    clients_not_coming = client_not_comming(
        (now - timedelta(days=30)).strftime('%Y-%m-%d'), actual_date
    ) if widgets_config['client_not_comming'] else None

    # Graphs
    evolution_achats = get_evolution_achats(now, n_months=6) if widgets_config['evolution_achats'] else None
    evolution_clients = get_evolution_clients(now, n_months=12) if widgets_config['evolution_clients'] else None
    presents_vs_inscrits = get_presents_vs_inscrits(now, n_weeks=4, top=6) if widgets_config['presents_vs_inscrits'] else None

    # Suggestions d'inscription : TOUJOURS calculées (info critique)
    suggestions_inscription = get_suggestions_inscription(now, min_consecutive=4)

    connection.close()

    return render_template('index.html',
                            widgets=widgets_config,
                            widget_labels=WIDGET_LABELS,
                            negative_clients=negative_clients,
                            zero_clients=zero_clients,
                            prochain_cours=prochain_cours,
                            apercu_jour=apercu_jour,
                            best_clients_month=best_clients_month,
                            nouveaux_clients=nouveaux_clients,
                            total_clients=total_clients,
                            fideles=fideles,
                            client_most_remaining=client_most_remaining,
                            clients_not_coming=clients_not_coming,
                            evolution_achats=evolution_achats,
                            evolution_clients=evolution_clients,
                            presents_vs_inscrits=presents_vs_inscrits,
                            suggestions_inscription=suggestions_inscription,
                           )


@app.route('/gestion_clients')
def gestion_clients():
    """
    Fonction exécutée lors de l'accès à la page gestion_clients ('/gestion_clients').
    Args:
        None
    Returns:
        str: rendu HTML de la page gestion_clients.
    """
    # connexion à la base de données
    connection = get_db_connection()

    # requête SQL pour récupérer tous les clients de la table 'clients'
    clients = connection.execute('SELECT * FROM clients').fetchall()

    # fermeture de la connexion à la base de données
    connection.close()

    # envoi des données à la page HTML gestion_clients.html
    return render_template('gestion_clients.html', clients=clients)




@app.route('/presence', methods=['GET', 'POST']) # pour accepter les requêtes GET et POST
def presence():
    """
    Fonction exécutée lors de l'accès à la page '/presence'.
    Args:
        None
    Returns:
        str: rendu HTML de la page de présence.
    """
    # connexion à la base de données
    connection = get_db_connection()

    if request.method == "POST": # si l'utilisateur a soumis le formulaire (POST)
        # récupération de l'ID du client depuis le formulaire
        prenom = request.form['prenom']
        nom = request.form['nom']

        # nettoyage des entrées
        prenom = prenom.strip().title()
        nom = nom.strip().title()

        # récuperation de l'heure actuelle à Paris
        current_time = datetime.now(paris_tz).strftime('%Y-%m-%d %H:%M:%S')

        # recherche du client dans la base de données
        client = connection.execute('SELECT * FROM clients WHERE prenom = ? AND nom = ?', (prenom, nom)).fetchone()

        if client:
            # récupération de l'ID du client
            client_id = client['id']

            # mise à jour de la présence du client dans la base de données
            connection.execute('UPDATE clients SET seances_restantes = seances_restantes - 1, total_seances_faites = total_seances_faites + 1 WHERE id = ?', (client_id,))

            # ajout dans historique seances
            connection.execute('INSERT INTO historique_seances (client_id, action, nombre, date_heure) VALUES (?, ?, ?, ?)', (client_id, "CHECK-IN", -1, current_time))

            # calcul du solde restant après le check-in
            nouveau_solde = client['seances_restantes'] - 1

            # commit des changements
            connection.commit()
            connection.close()

            # ré-affichage de la page avec la pop-up de confirmation
            return render_template('presence.html', success={
                'prenom': prenom,
                'nom': nom,
                'solde': nouveau_solde
            })

        else:
            # client non trouvé
            connection.close()
            return (f"<h1>Erreur : Le client '{prenom} {nom}' est introuvable.</h1><p>Vérifiez l'orthographe et réessayez.</p><a href='/presence'>Réessayer</a>")

    if request.method == "GET" :
        # affichage de la liste des clients
        clients = connection.execute('SELECT * FROM clients').fetchall()
        connection.close()
        return render_template('presence.html', clients=clients)




@app.route('/ajout_client', methods=['GET', 'POST'])
def ajout_client():
    """
    Fonction exécutée lors de l'accès à la page '/ajout_client'.
    Args:
        None
    Returns:
        str: rendu HTML de la page d'ajout de client.
    """
    # connexion à la base de données
    connection = get_db_connection()

    if request.method == "POST":
        prenom = request.form['prenom'].strip().title()
        nom = request.form['nom'].strip().title()
        seances_initiales = int(request.form.get('seances_ajoutees', 0))  # vient du pack selector
        forfait_initial = request.form.get('forfait')                     # 'essai', 'unite', '10', '20', 'autre' ou None

        email = request.form.get('email')
        telephone = request.form.get('telephone')
        abonnement = 1 if request.form.get('abonnement') else 0
        creneau = request.form.get('creneau')

        existing_client = connection.execute(
            'SELECT * FROM clients WHERE prenom = ? AND nom = ?', (prenom, nom)
        ).fetchone()

        if existing_client:
            connection.close()
            return (f"<h1>Erreur : Le client '{prenom} {nom}' existe déjà.</h1><p>Veuillez vérifier les informations et réessayer.</p><a href='/ajout_client'>Réessayer</a>")

        curseur = connection.execute(
            'INSERT INTO clients (prenom, nom, seances_restantes, email, telephone, abonnement) VALUES (?, ?, ?, ?, ?, ?)',
            (prenom, nom, seances_initiales, email, telephone, abonnement)
        )
        nouveau_client_id = curseur.lastrowid
        current_time = datetime.now(paris_tz).strftime('%Y-%m-%d %H:%M:%S')

        # Historique : entrée NEW_ACCOUNT (avec forfait si un pack initial a été choisi)
        connection.execute(
            'INSERT INTO historique_seances (client_id, action, nombre, forfait, date_heure) VALUES (?, ?, ?, ?, ?)',
            (nouveau_client_id, 'NEW_ACCOUNT', seances_initiales, forfait_initial, current_time)
        )

        if creneau:
            # fréquence : 'hebdo' (défaut) ou 'bimensuel' selon la case cochée
            freq = 'bimensuel' if request.form.get('frequence') == 'bimensuel' else 'hebdo'
            connection.execute(
                'INSERT INTO inscriptions (client_id, creneau_id, frequence) VALUES (?, ?, ?)',
                (nouveau_client_id, creneau, freq)
            )

        connection.commit()
        connection.close()

        return redirect(url_for('index'))

    if request.method == "GET" :
        planning = connection.execute('''
        SELECT * FROM semaine_type
        WHERE actif = 1
        ORDER BY jour_semaine, heure_debut
        ''').fetchall()
        connection.close()
        # affichage du formulaire d'ajout de client
        return render_template('ajout_client.html', planning=planning)




@app.route('/ajout_seances', methods=['GET', 'POST'])
def ajout_seances():
    """
    Fonction exécutée lors de l'accès à la page '/ajout_seances'.
    Args:
        None
    Returns:
        str: rendu HTML de la page d'ajout de séances.
    """
    # connexion à la base de données
    connection = get_db_connection()

    if request.method == "POST":
        prenom = request.form['prenom'].strip().title()
        nom = request.form['nom'].strip().title()
        seances_ajoutees = int(request.form['seances_ajoutees'])
        forfait = request.form.get('forfait', 'autre')

        client = connection.execute('SELECT * FROM clients WHERE prenom = ? AND nom = ?', (prenom, nom)).fetchone()

        if client:
            client_id = client['id']
            connection.execute(
                'UPDATE clients SET seances_restantes = seances_restantes + ? WHERE id = ?',
                (seances_ajoutees, client_id)
            )
            current_time = datetime.now(paris_tz).strftime('%Y-%m-%d %H:%M:%S')
            connection.execute(
                'INSERT INTO historique_seances (client_id, action, nombre, forfait, date_heure) VALUES (?, ?, ?, ?, ?)',
                (client_id, "ADD_SEANCES", seances_ajoutees, forfait, current_time)
            )
            connection.commit()
            connection.close()
            return redirect(url_for('index'))

    if request.method == "GET" :
        # affichage de la liste des clients
        clients = connection.execute('SELECT * FROM clients').fetchall()
        connection.close()
        return render_template('ajout_seances.html', clients=clients)



@app.route('/ajout_seances_rapide', methods=['POST'])
def ajout_seances_rapide():
    """
    Fonction exécutée lors de l'accès à la page '/ajout_seances_rapide'.
    Args:
        None
    Returns:
        str: redirection vers la page de gestion des clients.
    """
    # connexion à la base de données
    connection = get_db_connection()

    if request.method == "POST":
        client_id = int(request.form['client_id'])
        seances_ajoutees = int(request.form['seances_ajoutees'])
        forfait = request.form.get('forfait', 'autre')    # 'essai', 'unite', '10', '20', 'autre'

        current_time = datetime.now(paris_tz).strftime('%Y-%m-%d %H:%M:%S')

        connection.execute(
            'UPDATE clients SET seances_restantes = seances_restantes + ? WHERE id = ?',
            (seances_ajoutees, client_id)
        )
        connection.execute(
            'INSERT INTO historique_seances (client_id, action, nombre, forfait, date_heure) VALUES (?, ?, ?, ?, ?)',
            (client_id, "ADD_SEANCES", seances_ajoutees, forfait, current_time)
        )

        origine = request.form.get('origine')
        connection.commit()
        connection.close()

        if origine == 'index':
            return redirect(url_for('index'))
        elif origine == 'fiche_client':
            return redirect(url_for('fiche_client', client_id=client_id))
        else:
            return redirect(url_for('gestion_clients'))



@app.route('/recherche_client', methods=['GET'])
def recherche_client():
    """
    Fonction exécutée lors de l'accès à la page '/recherche_client'.
    Recherche un client par son nom complet et redirige vers sa fiche.
    Gère les noms et prénoms composés.
    Args:
        None
    Returns:
        str: rendu HTML de la page de résultats de recherche de client.
    """
    # récupération du terme de recherche depuis les paramètres GET
    query = request.args.get('q', '').strip()

    if not query:
        return redirect(url_for('gestion_clients'))

    # connexion à la base de données
    connection = get_db_connection()

    client = connection.execute('''
        SELECT id FROM clients
        WHERE (prenom || ' ' || nom) LIKE ?
           OR (nom || ' ' || prenom) LIKE ?
    ''', (query, query)).fetchone()

    connection.close()

    # envoi des résultats à la page HTML recherche_client.html
    if client:
        return redirect(url_for('fiche_client', client_id=client['id']))
    else:
        # Si aucun client n'est trouvé, on peut rediriger vers la liste avec un message
        return "<h1>Client introuvable</h1><p>Désolé, aucun client ne correspond à cette recherche.</p><a href='/gestion_clients'>Retour à la liste</a>"



@app.route('/client/<int:client_id>')
def fiche_client(client_id):
    """
    Fonction exécutée lors de l'accès à la page '/client/<client_id>'.
    Args:
        client_id (int): ID du client à afficher.
    Returns:
        str: rendu HTML de la fiche du client.
    """
    # connexion à la base de données
    connection = get_db_connection()

    # récupération des informations du client
    client = connection.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()

    # récupération des inscriptions du client (avec fréquence)
    inscriptions = connection.execute('''
        SELECT s.id, s.jour_semaine, s.heure_debut, s.type_seance, h.frequence
        FROM inscriptions h
        JOIN semaine_type s ON h.creneau_id = s.id
        WHERE h.client_id = ?
    ''', (client_id,)).fetchall()

    # récupération de l'historique des séances du client (10 dernières actions)
    historique = connection.execute('''
        SELECT date_heure, action, nombre, forfait, annulee
        FROM historique_seances
        WHERE client_id = ?
        ORDER BY date_heure DESC
        LIMIT 10
    ''', (client_id,)).fetchall()

    # récupération des tous les créneaux pour la modale
    creneaux = connection.execute('''
        SELECT id, jour_semaine, heure_debut, type_seance
        FROM semaine_type
        WHERE actif = 1
        ORDER BY jour_semaine, heure_debut
    ''').fetchall()

    # fermeture de la connexion à la base de données
    connection.close()

    # pour affichage des jours
    jours_semaine = {0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi', 4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche'}

    # envoi des données à la page HTML fiche_client.html
    return render_template('fiche_client.html',
                            client=client,
                            inscriptions=inscriptions,
                            historique=historique,
                            creneaux=creneaux,
                            jours=jours_semaine)



@app.route('/planning')
def planning():
    """
    Fonction exécutée lors de l'accès à la page '/planning'.
    Args:
        None
    Returns:
        str: rendu HTML de la page de planning.
    """
    # récupération du paramètre 'semaine' pour décaler l'affichage du planning
    try:
        offset = int(request.args.get('semaine', 0))
    except ValueError:
        offset = 0

    # calcul des dates de début et de fin de la semaine à afficher
    today = datetime.now(paris_tz)
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    end_of_week = start_of_week + timedelta(days=4)

    # Formatage dates pour SQL
    start_sql = start_of_week.strftime('%Y-%m-%d')
    end_sql = (end_of_week + timedelta(days=1)).strftime('%Y-%m-%d') # +1 jour pour inclure le vendredi soir

    # Calcul du numéro de semaine ISO
    week_number = start_of_week.isocalendar()[1]
    period_title = f"Semaine {week_number}"

    connection = get_db_connection()

    # 1. Squelette planning (créneaux récurrents)
    planning_squelett = connection.execute(
        'SELECT * FROM semaine_type WHERE actif = 1 ORDER BY heure_debut'
    ).fetchall()

    # 2. Inscriptions (qui est censé venir chaque semaine ?) — inclut la fréquence
    inscriptions_data = connection.execute('''
        SELECT i.creneau_id, i.frequence, i.date_debut,
               c.id as client_id, c.prenom, c.nom, c.seances_restantes
        FROM inscriptions i
        JOIN clients c ON i.client_id = c.id
    ''').fetchall()

    # 2bis. Annulations de cours pour la semaine
    annulations_data = connection.execute('''
        SELECT creneau_id, date_seance, raison
        FROM annulations_cours
        WHERE date_seance >= ? AND date_seance <= ?
    ''', (start_sql, end_of_week.strftime('%Y-%m-%d'))).fetchall()
    annulations_map = {(a['creneau_id'], a['date_seance']): a['raison'] for a in annulations_data}

    # 3. Prévisions de la semaine (qui a confirmé pour un jour précis ?)
    previsions_data = connection.execute('''
        SELECT p.creneau_id, p.date_seance, c.id as client_id, c.prenom, c.nom, c.seances_restantes
        FROM previsions p
        JOIN clients c ON p.client_id = c.id
        WHERE p.date_seance >= ? AND p.date_seance <= ?
    ''', (start_sql, end_of_week.strftime('%Y-%m-%d'))).fetchall()

    # 4. Check-ins de la semaine (avec noms/prénoms pour repérer les "surprises")
    presence_data = connection.execute('''
        SELECT h.client_id, h.date_heure, c.prenom, c.nom, c.seances_restantes
        FROM historique_seances h
        JOIN clients c ON h.client_id = c.id
        WHERE h.date_heure >= ? AND h.date_heure < ?
          AND h.action IN ('CHECK-IN', 'PRESENCE_VALIDEE')
          AND (h.annulee = 0 OR h.annulee IS NULL)
    ''', (start_sql, end_sql)).fetchall()

    connection.close()

    # --- TRAITEMENT DES DONNÉES EN PYTHON ---

    # A. Inscriptions organisées par créneau, avec filtrage bimensuel
    # (un client bimensuel apparaît une semaine sur deux à partir de sa date_debut)
    target_week_date = start_of_week.date()   # référence : lundi de la semaine affichée
    clients_par_creneau = {}
    for i in inscriptions_data:
        if not is_inscription_active_this_week(i['frequence'], i['date_debut'], target_week_date):
            continue   # bimensuel qui ne tombe pas cette semaine → skip
        cid = i['creneau_id']
        clients_par_creneau.setdefault(cid, []).append({
            'id': i['client_id'],
            'prenom': i['prenom'],
            'nom_complet': f"{i['prenom']} {i['nom']}",
            'solde': i['seances_restantes'],
        })

    # B. Prévisions organisées par (creneau_id, date_seance) : set d'ids clients
    prevus_par_seance = {}
    for p in previsions_data:
        key = (p['creneau_id'], p['date_seance'])
        prevus_par_seance.setdefault(key, set()).add(p['client_id'])

    # C. Check-ins organisés par (client_id, YYYY-MM-DD) → liste de (heure, prenom, nom, solde)
    presences_map = {}
    for p in presence_data:
        date_str = p['date_heure'].replace('T', ' ').split('.')[0]
        p_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        key = f"{p['client_id']}|{p_date.strftime('%Y-%m-%d')}"
        presences_map.setdefault(key, []).append({
            'heure': p_date.strftime('%H:%M'),
            'prenom': p['prenom'],
            'nom_complet': f"{p['prenom']} {p['nom']}",
            'solde': p['seances_restantes'],
        })

    # D. Aussi : par (YYYY-MM-DD, heure_range) → tous les checkins ce jour dans cette plage,
    # utilisé pour repérer les "clients surprise" (checkin mais pas inscrit)
    checkins_by_day = {}  # { 'YYYY-MM-DD' : [ {client_id, heure, ...}, ... ] }
    for p in presence_data:
        date_str = p['date_heure'].replace('T', ' ').split('.')[0]
        p_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        d = p_date.strftime('%Y-%m-%d')
        checkins_by_day.setdefault(d, []).append({
            'client_id': p['client_id'],
            'heure_min': p_date.hour * 60 + p_date.minute,
            'prenom': p['prenom'],
            'nom_complet': f"{p['prenom']} {p['nom']}",
            'solde': p['seances_restantes'],
        })

    HEURE_DEBUT = 9
    HEURE_FIN = 21
    DUREE_TOTAL_MINUTES = (HEURE_FIN - HEURE_DEBUT) * 60
    heure_affichage = [f"{h:02d}:00" for h in range(HEURE_DEBUT, HEURE_FIN + 1)]

    semaine_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
    planning = []
    now_paris = datetime.now(paris_tz)

    for jour in range(5):
        jour_date = start_of_week + timedelta(days=jour)
        jour_date_str = jour_date.strftime('%Y-%m-%d')

        creneaux_jour = [c for c in planning_squelett if c['jour_semaine'] == jour]
        creneaux_jour_processed = []

        for creneau in creneaux_jour:
            # Position du créneau dans la grille visuelle
            h_debut, m_debut = map(int, creneau['heure_debut'].split(':'))
            min_from_begin = (h_debut - HEURE_DEBUT) * 60 + m_debut
            top_percent = (min_from_begin / DUREE_TOTAL_MINUTES) * 100
            height_percent = (creneau['duree'] / DUREE_TOTAL_MINUTES) * 100
            course_start_min = h_debut * 60 + m_debut
            course_end_min = course_start_min + creneau['duree']

            # Ce créneau est-il passé, en cours, ou à venir ?
            course_dt_naive = datetime.combine(jour_date.date(), datetime.strptime(creneau['heure_debut'], '%H:%M').time())
            course_dt = paris_tz.localize(course_dt_naive)
            is_past = course_dt <= now_paris

            # Inscrits de ce créneau
            raw_clients = clients_par_creneau.get(creneau['id'], [])
            inscrits_ids = {cl['id'] for cl in raw_clients}
            prevus_ids = prevus_par_seance.get((creneau['id'], jour_date_str), set())

            final_clients = []
            for cl in raw_clients:
                # Est-il présent ? Check dans la plage horaire
                is_present = False
                lookup_key = f"{cl['id']}|{jour_date_str}"
                if lookup_key in presences_map:
                    for hp in presences_map[lookup_key]:
                        hp_h, hp_m = map(int, hp['heure'].split(':'))
                        pointage_min = hp_h * 60 + hp_m
                        if (course_start_min - 30) <= pointage_min <= course_end_min:
                            is_present = True
                            break

                is_prevu = cl['id'] in prevus_ids
                # No-show = prévu mais pas venu ET cours passé
                is_no_show = is_prevu and (not is_present) and is_past

                final_clients.append({
                    'id': cl['id'],
                    'nom': cl['nom_complet'],
                    'present': is_present,
                    'prevu': is_prevu,
                    'no_show': is_no_show,
                    'solde': cl['solde'],
                })

            # "Surprise" : clients checkés-in dans la plage mais PAS inscrits
            surprises = []
            surprises_seen = set()
            for ck in checkins_by_day.get(jour_date_str, []):
                if ck['client_id'] in inscrits_ids or ck['client_id'] in surprises_seen:
                    continue
                if (course_start_min - 30) <= ck['heure_min'] <= course_end_min:
                    surprises.append({
                        'id': ck['client_id'],
                        'nom': ck['nom_complet'],
                        'solde': ck['solde'],
                    })
                    surprises_seen.add(ck['client_id'])

            # Tri : prévus en haut, puis inscrits normaux, puis surprises rendus après
            final_clients.sort(key=lambda x: (not x['prevu'], x['nom']))

            # Annulation éventuelle de ce créneau à cette date
            annulation_key = (creneau['id'], jour_date_str)
            is_annule = annulation_key in annulations_map
            raison_annulation = annulations_map.get(annulation_key)

            # Nb total de présents (inscrits présents + surprises)
            nb_presents = sum(1 for cl in final_clients if cl['present']) + len(surprises)

            creneaux_jour_processed.append({
                'data': creneau,
                'style': f"top: {top_percent}%; height: {height_percent}%;",
                'clients': final_clients,
                'surprises': surprises,
                'is_past': is_past,
                'is_annule': is_annule,
                'raison_annulation': raison_annulation,
                'nb_presents': nb_presents,
                'date_reelle': jour_date_str,
            })

        planning.append({
            'nom': semaine_fr[jour],
            'date_courte': jour_date.strftime('%d/%m'),
            'is_today': jour_date.date() == today.date(),
            'creneaux': creneaux_jour_processed,
        })

    return render_template('planning.html',
                           semaine=planning,
                           period_title=period_title,
                           offset=offset,
                           heures=heure_affichage)



@app.route('/inscrire_suggestion', methods=['POST'])
def inscrire_suggestion():
    """
    Depuis le widget "Suggestions" du dashboard : inscrit d'un click un client
    à un créneau (crée une entrée dans inscriptions).
    """
    client_id = int(request.form['client_id'])
    creneau_id = int(request.form['creneau_id'])
    connection = get_db_connection()
    try:
        connection.execute(
            'INSERT INTO inscriptions (client_id, creneau_id) VALUES (?, ?)',
            (client_id, creneau_id)
        )
        connection.commit()
    except sqlite3.IntegrityError:
        pass  # déjà inscrit, pas grave
    finally:
        connection.close()
    return redirect(url_for('index'))


@app.route('/annuler_cours', methods=['POST'])
def annuler_cours():
    """
    Annule un cours à une date précise (l'ajoute à annulations_cours).
    Le cours reste visible dans le planning mais grisé + badge "Annulé".
    """
    from flask import jsonify

    creneau_id = int(request.form['creneau_id'])
    date_seance = request.form['date_seance']
    raison = (request.form.get('raison') or '').strip() or None

    connection = get_db_connection()
    try:
        connection.execute(
            'INSERT INTO annulations_cours (creneau_id, date_seance, raison) VALUES (?, ?, ?)',
            (creneau_id, date_seance, raison)
        )
        connection.commit()
        result = {'ok': True}
    except sqlite3.IntegrityError:
        result = {'ok': True, 'already': True}
    finally:
        connection.close()
    return jsonify(result)


@app.route('/desannuler_cours', methods=['POST'])
def desannuler_cours():
    """Réactive un cours précédemment annulé (retire de annulations_cours)."""
    from flask import jsonify

    creneau_id = int(request.form['creneau_id'])
    date_seance = request.form['date_seance']

    connection = get_db_connection()
    connection.execute(
        'DELETE FROM annulations_cours WHERE creneau_id = ? AND date_seance = ?',
        (creneau_id, date_seance)
    )
    connection.commit()
    connection.close()
    return jsonify({'ok': True})


@app.route('/marquer_prevu', methods=['POST'])
def marquer_prevu():
    """
    Flagge un client comme "prévu" pour un cours à une date précise.
    Refusé si la date/heure du cours est dans le passé.
    Retourne JSON pour permettre un appel AJAX depuis la modale du planning.
    """
    from flask import jsonify

    client_id = int(request.form['client_id'])
    creneau_id = int(request.form['creneau_id'])
    date_seance = request.form['date_seance']    # 'YYYY-MM-DD'
    heure_seance = request.form['heure_seance']  # 'HH:MM'

    # Vérifier que le cours n'est pas passé
    try:
        cours_dt = datetime.strptime(f"{date_seance} {heure_seance}", '%Y-%m-%d %H:%M')
        cours_dt = paris_tz.localize(cours_dt)
    except ValueError:
        return jsonify({'ok': False, 'error': 'Date/heure invalide'}), 400

    if cours_dt <= datetime.now(paris_tz):
        return jsonify({'ok': False, 'error': 'Impossible de marquer un cours passé comme prévu'}), 400

    connection = get_db_connection()
    try:
        connection.execute(
            'INSERT INTO previsions (client_id, creneau_id, date_seance) VALUES (?, ?, ?)',
            (client_id, creneau_id, date_seance)
        )
        connection.commit()
        result = {'ok': True}
    except sqlite3.IntegrityError:
        # déjà prévu (UNIQUE constraint violée) — pas grave
        result = {'ok': True, 'already': True}
    finally:
        connection.close()

    return jsonify(result)


@app.route('/annuler_prevu', methods=['POST'])
def annuler_prevu():
    """Retire le flag "prévu" pour un client à une date précise."""
    from flask import jsonify

    client_id = int(request.form['client_id'])
    creneau_id = int(request.form['creneau_id'])
    date_seance = request.form['date_seance']

    connection = get_db_connection()
    connection.execute(
        'DELETE FROM previsions WHERE client_id = ? AND creneau_id = ? AND date_seance = ?',
        (client_id, creneau_id, date_seance)
    )
    connection.commit()
    connection.close()
    return jsonify({'ok': True})


@app.route('/marquer_presence', methods=['POST'])
def marquer_presence():
    """
    Marque un client comme présent à une séance.
    Débite -1 séance, ajoute une ligne PRESENCE_VALIDEE dans l'historique.
    """
    client_id = request.form['client_id']
    date_seance = request.form['date_seance'] # Format YYYY-MM-DD
    heure_seance = request.form['heure_seance'] # Format HH:MM

    # On reconstruit le timestamp exact du début du cours
    timestamp_seance = f"{date_seance} {heure_seance}:00"

    connection = get_db_connection()

    # Débiter le client
    connection.execute('UPDATE clients SET seances_restantes = seances_restantes - 1, total_seances_faites = total_seances_faites + 1 WHERE id = ?', (client_id,))

    # Ajouter l'historique (Note le -1 et l'action spécifique)
    connection.execute('''
        INSERT INTO historique_seances (client_id, action, nombre, date_heure)
        VALUES (?, ?, ?, ?)
    ''', (client_id, "PRESENCE_VALIDEE", -1, timestamp_seance))

    connection.commit()
    connection.close()

    # On recharge la page planning (on essaie de rester sur la même semaine si possible)
    return redirect(request.referrer or url_for('planning'))


@app.route('/annuler_presence', methods=['POST'])
def annuler_presence():
    """
    Annule un pointage de présence (fausse manip) : recrédite +1 séance,
    décrémente total_seances_faites, et FLAG l'entrée historique comme
    annulée (annulee=1) au lieu de la supprimer — pour trace.

    Cherche l'entree PRESENCE_VALIDEE ou CHECK-IN la plus recente pour
    (client_id, date_seance) qui n'est pas deja annulee.
    """
    from flask import jsonify

    client_id = int(request.form['client_id'])
    date_seance = request.form['date_seance']  # YYYY-MM-DD

    connection = get_db_connection()

    # Trouve la derniere entree de presence pour ce client/date, non annulee
    row = connection.execute('''
        SELECT id FROM historique_seances
        WHERE client_id = ?
          AND DATE(date_heure) = ?
          AND action IN ('PRESENCE_VALIDEE', 'CHECK-IN')
          AND (annulee = 0 OR annulee IS NULL)
        ORDER BY date_heure DESC, id DESC
        LIMIT 1
    ''', (client_id, date_seance)).fetchone()

    if not row:
        connection.close()
        return jsonify({'ok': False, 'error': 'Aucune presence a annuler'}), 404

    # Flagger l'entree comme annulee + recrediter le solde
    connection.execute('UPDATE historique_seances SET annulee = 1 WHERE id = ?', (row['id'],))
    connection.execute(
        'UPDATE clients SET seances_restantes = seances_restantes + 1, '
        'total_seances_faites = total_seances_faites - 1 WHERE id = ?',
        (client_id,)
    )

    # Recupere le nouveau solde pour retour immediat cote UI
    new_solde_row = connection.execute(
        'SELECT seances_restantes FROM clients WHERE id = ?', (client_id,)
    ).fetchone()

    connection.commit()
    connection.close()

    return jsonify({'ok': True, 'nouveau_solde': new_solde_row['seances_restantes']})


@app.route('/rectifier_seances', methods=['POST'])
def rectifier_seances():
    """
    Rectifie manuellement le solde de séances d'un client (positif ou négatif),
    sans lien avec une date de cours. Historisé comme action RECTIFICATION.
    """
    client_id = int(request.form['client_id'])
    delta = int(request.form['delta'])   # peut etre negatif

    if delta == 0:
        return redirect(request.referrer or url_for('gestion_clients'))

    current_time = datetime.now(paris_tz).strftime('%Y-%m-%d %H:%M:%S')

    connection = get_db_connection()
    connection.execute(
        'UPDATE clients SET seances_restantes = seances_restantes + ? WHERE id = ?',
        (delta, client_id)
    )
    connection.execute(
        'INSERT INTO historique_seances (client_id, action, nombre, date_heure) VALUES (?, ?, ?, ?)',
        (client_id, 'RECTIFICATION', delta, current_time)
    )
    connection.commit()
    connection.close()

    return redirect(request.referrer or url_for('fiche_client', client_id=client_id))


@app.route('/swap_bimensuel', methods=['POST'])
def swap_bimensuel():
    """
    Inverse la parite d'une inscription bimensuelle (decale date_debut de 7 jours)
    pour passer de la semaine A a la semaine B.
    """
    from flask import jsonify

    client_id = int(request.form['client_id'])
    creneau_id = int(request.form['creneau_id'])

    connection = get_db_connection()
    # On decale de 7 jours en avant : la semaine active change
    connection.execute('''
        UPDATE inscriptions
        SET date_debut = DATE(date_debut, '+7 days')
        WHERE client_id = ? AND creneau_id = ? AND frequence = 'bimensuel'
    ''', (client_id, creneau_id))
    connection.commit()
    connection.close()

    return jsonify({'ok': True})



@app.route('/modif_inscriptions', methods=['POST'])
def modif_inscriptions():
    """
    Fonction exécutée lors de l'accès à la page '/modif_inscriptions'.
    Args:
        None
    Returns:
        str: redirection vers la page de gestion des clients.
    """
    # connexion à la base de données
    connection = get_db_connection()

    if request.method == "POST":
        client_id = int(request.form['client_id'])
        nouveaux_creneaux = request.form.getlist('creneaux')

        # 1. Nettoie les anciennes inscriptions
        connection.execute('DELETE FROM inscriptions WHERE client_id = ?', (client_id,))

        # 2. Ajoute les nouvelles, avec fréquence individuelle pour chaque créneau
        for creneau_id in nouveaux_creneaux:
            # case "bimensuel_<creneau_id>" cochée dans le form
            freq = 'bimensuel' if request.form.get(f'bimensuel_{creneau_id}') == '1' else 'hebdo'
            connection.execute(
                'INSERT INTO inscriptions (client_id, creneau_id, frequence) VALUES (?, ?, ?)',
                (client_id, creneau_id, freq)
            )

        connection.commit()
        connection.close()

        return redirect(url_for('fiche_client', client_id=client_id))



@app.route('/modif_client', methods=['POST'])
def modif_client():
    """
    Fonction exécutée lors de l'accès à la page '/modif_client'.
    Met à jour les informations d'un client (prénom, nom, email, téléphone).
    Args:
        None
    Returns:
        str: redirection vers la fiche du client.
    """
    # connexion à la base de données
    connection = get_db_connection()

    # récupération des données du formulaire
    client_id = int(request.form['client_id'])
    prenom = request.form['prenom'].strip().title()
    nom = request.form['nom'].strip().title()
    email = request.form.get('email', '').strip() or None
    telephone = request.form.get('telephone', '').strip() or None

    # vérification qu'un AUTRE client ne porte pas déjà ce prénom/nom
    existing_client = connection.execute(
        'SELECT id FROM clients WHERE prenom = ? AND nom = ? AND id != ?',
        (prenom, nom, client_id)
    ).fetchone()

    if existing_client:
        connection.close()
        return (f"<h1>Erreur : Le client '{prenom} {nom}' existe déjà.</h1>"
                f"<p>Veuillez vérifier les informations et réessayer.</p>"
                f"<a href='/client/{client_id}'>Retour à la fiche</a>")

    # mise à jour des informations du client
    connection.execute(
        'UPDATE clients SET prenom = ?, nom = ?, email = ?, telephone = ? WHERE id = ?',
        (prenom, nom, email, telephone, client_id)
    )

    # commit des changements
    connection.commit()
    connection.close()

    # renvoie de l'utilisateur vers la fiche du client
    return redirect(url_for('fiche_client', client_id=client_id))



@app.route('/supprimer_client', methods=['POST'])
def supprimer_client():
    """
    Fonction exécutée lors de l'accès à la page '/supprimer_client'.
    Supprime définitivement un client ainsi que ses données liées
    (inscriptions et historique des séances).
    Args:
        None
    Returns:
        str: redirection vers la page de gestion des clients.
    """
    # connexion à la base de données
    connection = get_db_connection()

    # récupération de l'ID du client à supprimer
    client_id = int(request.form['client_id'])

    # suppression des données liées puis du client lui-même
    # (SQLite n'applique pas le ON DELETE CASCADE par défaut, on le fait manuellement)
    connection.execute('DELETE FROM inscriptions WHERE client_id = ?', (client_id,))
    connection.execute('DELETE FROM historique_seances WHERE client_id = ?', (client_id,))
    connection.execute('DELETE FROM clients WHERE id = ?', (client_id,))

    # commit des changements
    connection.commit()
    connection.close()

    # renvoie de l'utilisateur vers la liste des clients
    return redirect(url_for('gestion_clients'))




@app.route('/borne', methods=['GET', 'POST'])
def borne():
    """
    Fonction exécutée lors de l'accès à la page '/borne'.
    Args:
        None
    Returns:
        str: rendu HTML de la page de la borne de check-in. """
    connection = get_db_connection()

    # récupération des cookies pour pré-remplir le formulaire si disponibles
    id_cookie = request.cookies.get('borne_id')
    prenom_cookie = request.cookies.get('borne_prenom')
    nom_cookie = request.cookies.get('borne_nom')

    if request.method == "POST":
        client_id = request.form.get('client_id')
        if client_id:
            # validation rapide
            client = connection.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
        else :
            # validation manuelle
            prenom = request.form['prenom'].strip().title()
            nom = request.form['nom'].strip().title()
            client = connection.execute('SELECT * FROM clients WHERE prenom = ? AND nom = ?', (prenom, nom)).fetchone()

        if client:
            # Calcul du nouveau solde
            nouveau_solde = client['seances_restantes'] - 1
            client_id = client['id']
            prenom = client['prenom']
            nom = client['nom']
            current_time = datetime.now(paris_tz).strftime('%Y-%m-%d %H:%M:%S')

            # Mise à jour
            connection.execute('UPDATE clients SET seances_restantes = ?, total_seances_faites = total_seances_faites + 1 WHERE id = ?', (nouveau_solde, client_id))
            connection.execute('INSERT INTO historique_seances (client_id, action, nombre, date_heure) VALUES (?, ?, ?, ?)', (client_id, "CHECK-IN", -1, current_time))
            connection.commit()
            connection.close()

            # On stocke le résultat en session puis on REDIRIGE vers la page de succès.
            # (Schéma POST/Redirect/GET : empêche le re-décompte si le client recharge la page.)
            session['borne_succes'] = {'prenom': prenom, 'solde': nouveau_solde}

            response = make_response(redirect(url_for('borne_succes')))

            # on enregistre le cookie pour 60 jours
            max_age = 60 * 24 * 60 * 60 # 60 jours en secondes
            response.set_cookie('borne_id', str(client_id), max_age=max_age)
            response.set_cookie('borne_prenom', prenom, max_age=max_age)
            response.set_cookie('borne_nom', nom, max_age=max_age)

            return response

        else:
            connection.close()
            # On renvoie l'erreur ET les infos du cookie pour que la pop-up puisse se ré-ouvrir
            return render_template('borne.html',
                                erreur="Client non trouvé.",
                                id_cookie=id_cookie,
                                prenom_cookie=prenom_cookie,
                                nom_cookie=nom_cookie)

    # Affichage du formulaire vide
    connection.close()
    return render_template('borne.html',
                           id_cookie=id_cookie,
                           prenom_cookie=prenom_cookie,
                           nom_cookie=nom_cookie)




@app.route('/borne_succes')
def borne_succes():
    """
    Page de confirmation affichée après un pointage à la borne.
    Lit le résultat depuis la session (et le retire, pour qu'un rechargement
    ne re-décompte pas de séance et n'affiche pas une info périmée).
    Args:
        None
    Returns:
        str: rendu HTML de la page de succès, ou redirection vers la borne.
    """
    # on récupère ET on supprime les infos de la session (usage unique)
    data = session.pop('borne_succes', None)

    # si on arrive ici sans pointage récent (rechargement, accès direct), retour à la borne
    if not data:
        return redirect(url_for('borne'))

    return render_template('borne_succes.html', prenom=data['prenom'], solde=data['solde'])




# Note : le lancement du serveur se fait via run.py à la racine du projet
# (pas via ce fichier, qui n'est plus exécutable directement).

