# -*- coding: utf-8 -*-
"""
app/routes.py — Toutes les routes de l'application.

Ce fichier expose une fonction register_routes(app) que la factory
create_app() (voir app/__init__.py) appelle pour attacher toutes les
routes, hooks (before_request), filtres Jinja et context processors
à l'instance Flask fournie.

Les valeurs de configuration (SITE_NAME, ADMIN_USERNAME, ADMIN_PASSWORD_HASH…)
sont lues depuis app.config au moment de la requête, pas au chargement
du module — c'est ce qui permet de charger la même codebase avec des
profils différents (DevConfig / ProdConfig / TestConfig).
"""

# imports des modules
import sqlite3
from flask import render_template, request, redirect, url_for, make_response, session
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
)
import pytz


# récupération de l'heure de paris (constante partagée par toutes les routes)
paris_tz = pytz.timezone('Europe/Paris')

# pages accessibles SANS être connecté (la borne reste publique pour les clients)
PUBLIC_ENDPOINTS = {'login', 'borne', 'borne_succes', 'static'}


def register_routes(app):
    """
    Attache toutes les routes, hooks et filtres à l'app Flask fournie.
    Appelée depuis create_app() (voir app/__init__.py).
    """

    # ============================================================
    # HOOKS GLOBAUX (context processor, before_request, filtres)
    # ============================================================

    @app.context_processor
    def inject_site_name():
        """Rend SITE_NAME disponible dans tous les templates via {{ site_name }}."""
        return {'site_name': app.config['SITE_NAME']}


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
                return value  # On renvoie tel quel si on n'y arrive pas


    # ============================================================
    # ROUTES : AUTHENTIFICATION
    # ============================================================

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """
        Page de connexion à l'espace d'administration.
        """
        # si déjà connecté, on redirige vers l'accueil
        if session.get('logged_in'):
            return redirect(url_for('index'))

        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            remember = request.form.get('remember')  # case "Rester connecté"

            # vérification de l'identifiant et du mot de passe (lus depuis la config)
            admin_username = app.config['ADMIN_USERNAME']
            admin_password_hash = app.config['ADMIN_PASSWORD_HASH']
            if username.lower() == admin_username and check_password_hash(admin_password_hash, password):
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
        """
        session.clear()
        return redirect(url_for('login'))


    # ============================================================
    # ROUTES : TABLEAU DE BORD & GESTION CLIENTS
    # ============================================================

    @app.route('/')
    def index():
        """
        Tableau de bord (widgets).
        """
        connection = get_db_connection()

        # CONFIGURATION DES WIDGETS
        widgets_config = {
            'negative_balance': True,
            'zero_balance': True,
            'best_client_month': True,
            'best_client_all_time': False,
            'most_remaining': True,
            'total_clients': True,
            'seances_month': True,
            'client_not_comming': True,
        }

        # initialisation des données des widgets
        negative_clients = []
        best_clients_month = None
        best_clients_all_time = None
        client_most_remaining = None
        total_clients = None
        number_seances_month = None
        clients_not_coming = None
        zero_clients = None

        # récupération des variables
        actual_date = datetime.now(paris_tz).strftime('%Y-%m-%d')
        first_day_of_month = actual_date[:8] + '01'  # premier jour du mois courant

        # création des données pour les widgets
        if widgets_config['negative_balance']:
            negative_clients = get_negative_seances_clients()
        if widgets_config['zero_balance']:
            zero_clients = get_zero_clients()
        if widgets_config['best_client_month']:
            best_clients_month = get_best_clients(first_day_of_month, actual_date)
        if widgets_config['best_client_all_time']:
            best_clients_all_time = get_best_clients('2000-01-01', actual_date)
        if widgets_config['most_remaining']:
            client_most_remaining = get_client_most_remaining()
        if widgets_config['total_clients']:
            total_clients = connection.execute('SELECT COUNT(*) AS total FROM clients').fetchone()['total']
        if widgets_config['seances_month']:
            number_seances_month = get_number_seances(first_day_of_month, actual_date)
        if widgets_config['client_not_comming']:
            clients_not_coming = client_not_comming(
                (datetime.now(paris_tz) - timedelta(days=30)).strftime('%Y-%m-%d'),
                actual_date,
            )

        connection.close()

        return render_template(
            'index.html',
            widgets=widgets_config,
            negative_clients=negative_clients,
            zero_clients=zero_clients,
            best_clients_month=best_clients_month,
            client_most_remaining=client_most_remaining,
            total_clients=total_clients,
            number_seances_month=number_seances_month,
            clients_not_coming=clients_not_coming,
        )


    @app.route('/gestion_clients')
    def gestion_clients():
        """Liste complète des clients (DataTables)."""
        connection = get_db_connection()
        clients = connection.execute('SELECT * FROM clients').fetchall()
        connection.close()
        return render_template('gestion_clients.html', clients=clients)


    @app.route('/recherche_client', methods=['GET'])
    def recherche_client():
        """
        Recherche un client par son nom complet et redirige vers sa fiche.
        Gère les noms et prénoms composés.
        """
        query = request.args.get('q', '').strip()

        if not query:
            return redirect(url_for('gestion_clients'))

        connection = get_db_connection()

        client = connection.execute('''
            SELECT id FROM clients
            WHERE (prenom || ' ' || nom) LIKE ?
               OR (nom || ' ' || prenom) LIKE ?
        ''', (query, query)).fetchone()

        connection.close()

        if client:
            return redirect(url_for('fiche_client', client_id=client['id']))
        else:
            return "<h1>Client introuvable</h1><p>Désolé, aucun client ne correspond à cette recherche.</p><a href='/gestion_clients'>Retour à la liste</a>"


    @app.route('/client/<int:client_id>')
    def fiche_client(client_id):
        """Fiche détaillée d'un client (info, habitudes, historique, actions)."""
        connection = get_db_connection()

        client = connection.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()

        habitudes = connection.execute('''
            SELECT s.id, s.jour_semaine, s.heure_debut, s.type_seance
            FROM habitudes h
            JOIN semaine_type s ON h.creneau_id = s.id
            WHERE h.client_id = ?
        ''', (client_id,)).fetchall()

        historique = connection.execute('''
            SELECT date_heure, action, nombre
            FROM historique_seances
            WHERE client_id = ?
            ORDER BY date_heure DESC
            LIMIT 10
        ''', (client_id,)).fetchall()

        creneaux = connection.execute('''
            SELECT id, jour_semaine, heure_debut, type_seance
            FROM semaine_type
            WHERE actif = 1
            ORDER BY jour_semaine, heure_debut
        ''').fetchall()

        connection.close()

        jours_semaine = {0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi', 4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche'}

        return render_template(
            'fiche_client.html',
            client=client,
            habitudes=habitudes,
            historique=historique,
            creneaux=creneaux,
            jours=jours_semaine,
        )


    # ============================================================
    # ROUTES : SÉANCES (ajout, présence, modification)
    # ============================================================

    @app.route('/presence', methods=['GET', 'POST'])
    def presence():
        """Saisie manuelle prénom+nom pour valider une présence."""
        connection = get_db_connection()

        if request.method == "POST":
            prenom = request.form['prenom'].strip().title()
            nom = request.form['nom'].strip().title()
            current_time = datetime.now(paris_tz).strftime('%Y-%m-%d %H:%M:%S')

            client = connection.execute('SELECT * FROM clients WHERE prenom = ? AND nom = ?', (prenom, nom)).fetchone()

            if client:
                client_id = client['id']
                connection.execute(
                    'UPDATE clients SET seances_restantes = seances_restantes - 1, total_seances_faites = total_seances_faites + 1 WHERE id = ?',
                    (client_id,),
                )
                connection.execute(
                    'INSERT INTO historique_seances (client_id, action, nombre, date_heure) VALUES (?, ?, ?, ?)',
                    (client_id, "CHECK-IN", -1, current_time),
                )

                nouveau_solde = client['seances_restantes'] - 1

                connection.commit()
                connection.close()

                return render_template('presence.html', success={
                    'prenom': prenom,
                    'nom': nom,
                    'solde': nouveau_solde,
                })

            else:
                connection.close()
                return (f"<h1>Erreur : Le client '{prenom} {nom}' est introuvable.</h1>"
                        f"<p>Vérifiez l'orthographe et réessayez.</p><a href='/presence'>Réessayer</a>")

        # GET
        clients = connection.execute('SELECT * FROM clients').fetchall()
        connection.close()
        return render_template('presence.html', clients=clients)


    @app.route('/ajout_client', methods=['GET', 'POST'])
    def ajout_client():
        """Formulaire de création d'un nouveau client."""
        connection = get_db_connection()

        if request.method == "POST":
            prenom = request.form['prenom'].strip().title()
            nom = request.form['nom'].strip().title()
            seances_initiales = int(request.form['seances_restantes'])
            email = request.form.get('email')
            telephone = request.form.get('telephone')
            abonnement = 1 if request.form.get('abonnement') else 0
            creneau = request.form.get('creneau')

            existing_client = connection.execute(
                'SELECT * FROM clients WHERE prenom = ? AND nom = ?',
                (prenom, nom),
            ).fetchone()

            if existing_client:
                connection.close()
                return (f"<h1>Erreur : Le client '{prenom} {nom}' existe déjà.</h1>"
                        f"<p>Veuillez vérifier les informations et réessayer.</p>"
                        f"<a href='/ajout_client'>Réessayer</a>")

            curseur = connection.execute(
                'INSERT INTO clients (prenom, nom, seances_restantes, email, telephone, abonnement) VALUES (?, ?, ?, ?, ?, ?)',
                (prenom, nom, seances_initiales, email, telephone, abonnement),
            )
            nouveau_client_id = curseur.lastrowid
            current_time = datetime.now(paris_tz).strftime('%Y-%m-%d %H:%M:%S')

            connection.execute(
                'INSERT INTO historique_seances (client_id, action, nombre, date_heure) VALUES (?, ?, ?, ?)',
                (nouveau_client_id, 'NEW_ACCOUNT', seances_initiales, current_time),
            )

            if creneau:
                connection.execute(
                    'INSERT INTO habitudes (client_id, creneau_id) VALUES (?, ?)',
                    (nouveau_client_id, creneau),
                )

            connection.commit()
            connection.close()

            return redirect(url_for('index'))

        # GET
        planning = connection.execute('''
            SELECT * FROM semaine_type
            WHERE actif = 1
            ORDER BY jour_semaine, heure_debut
        ''').fetchall()
        connection.close()
        return render_template('ajout_client.html', planning=planning)


    @app.route('/ajout_seances', methods=['GET', 'POST'])
    def ajout_seances():
        """Page dédiée à l'ajout de séances pour un client (recherche par nom)."""
        connection = get_db_connection()

        if request.method == "POST":
            prenom = request.form['prenom'].strip().title()
            nom = request.form['nom'].strip().title()
            seances_ajoutees = int(request.form['seances_ajoutees'])

            client = connection.execute(
                'SELECT * FROM clients WHERE prenom = ? AND nom = ?',
                (prenom, nom),
            ).fetchone()

            if client:
                client_id = client['id']
                connection.execute(
                    'UPDATE clients SET seances_restantes = seances_restantes + ? WHERE id = ?',
                    (seances_ajoutees, client_id),
                )
                current_time = datetime.now(paris_tz).strftime('%Y-%m-%d %H:%M:%S')
                connection.execute(
                    'INSERT INTO historique_seances (client_id, action, nombre, date_heure) VALUES (?, ?, ?, ?)',
                    (client_id, "ADD_SEANCES", seances_ajoutees, current_time),
                )
                connection.commit()
                connection.close()
                return redirect(url_for('index'))

        # GET
        clients = connection.execute('SELECT * FROM clients').fetchall()
        connection.close()
        return render_template('ajout_seances.html', clients=clients)


    @app.route('/ajout_seances_rapide', methods=['POST'])
    def ajout_seances_rapide():
        """Ajout rapide de séances via modale (index, gestion_clients, fiche_client)."""
        connection = get_db_connection()

        client_id = int(request.form['client_id'])
        seances_ajoutees = int(request.form['seances_ajoutees'])

        current_time = datetime.now(paris_tz).strftime('%Y-%m-%d %H:%M:%S')

        connection.execute(
            'UPDATE clients SET seances_restantes = seances_restantes + ? WHERE id = ?',
            (seances_ajoutees, client_id),
        )
        connection.execute(
            'INSERT INTO historique_seances (client_id, action, nombre, date_heure) VALUES (?, ?, ?, ?)',
            (client_id, "ADD_SEANCES", seances_ajoutees, current_time),
        )

        origine = request.form.get('origine')

        connection.commit()
        connection.close()

        # redirection selon l'origine du formulaire
        if origine == 'index':
            return redirect(url_for('index'))
        elif origine == 'fiche_client':
            return redirect(url_for('fiche_client', client_id=client_id))
        else:
            return redirect(url_for('gestion_clients'))


    @app.route('/modif_inscriptions', methods=['POST'])
    def modif_inscriptions():
        """Met à jour les habitudes (créneaux récurrents) d'un client."""
        connection = get_db_connection()

        client_id = int(request.form['client_id'])
        nouveaux_creneaux = request.form.getlist('creneaux')

        # 1. Nettoyer les anciennes habitudes
        connection.execute('DELETE FROM habitudes WHERE client_id = ?', (client_id,))

        # 2. Ajouter les nouvelles
        for creneau_id in nouveaux_creneaux:
            connection.execute(
                'INSERT INTO habitudes (client_id, creneau_id) VALUES (?, ?)',
                (client_id, creneau_id),
            )

        connection.commit()
        connection.close()

        return redirect(url_for('fiche_client', client_id=client_id))


    @app.route('/modif_client', methods=['POST'])
    def modif_client():
        """Met à jour les infos d'un client (prénom, nom, email, téléphone)."""
        connection = get_db_connection()

        client_id = int(request.form['client_id'])
        prenom = request.form['prenom'].strip().title()
        nom = request.form['nom'].strip().title()
        email = request.form.get('email', '').strip() or None
        telephone = request.form.get('telephone', '').strip() or None

        existing_client = connection.execute(
            'SELECT id FROM clients WHERE prenom = ? AND nom = ? AND id != ?',
            (prenom, nom, client_id),
        ).fetchone()

        if existing_client:
            connection.close()
            return (f"<h1>Erreur : Le client '{prenom} {nom}' existe déjà.</h1>"
                    f"<p>Veuillez vérifier les informations et réessayer.</p>"
                    f"<a href='/client/{client_id}'>Retour à la fiche</a>")

        connection.execute(
            'UPDATE clients SET prenom = ?, nom = ?, email = ?, telephone = ? WHERE id = ?',
            (prenom, nom, email, telephone, client_id),
        )

        connection.commit()
        connection.close()

        return redirect(url_for('fiche_client', client_id=client_id))


    @app.route('/supprimer_client', methods=['POST'])
    def supprimer_client():
        """Suppression définitive d'un client + données liées."""
        connection = get_db_connection()

        client_id = int(request.form['client_id'])

        # SQLite n'applique pas ON DELETE CASCADE par défaut : on nettoie à la main
        connection.execute('DELETE FROM habitudes WHERE client_id = ?', (client_id,))
        connection.execute('DELETE FROM historique_seances WHERE client_id = ?', (client_id,))
        connection.execute('DELETE FROM clients WHERE id = ?', (client_id,))

        connection.commit()
        connection.close()

        return redirect(url_for('gestion_clients'))


    # ============================================================
    # ROUTES : PLANNING (semaine + marquage présence)
    # ============================================================

    @app.route('/planning')
    def planning():
        """Vue hebdomadaire du planning avec présences."""
        # récupération du paramètre 'semaine' pour décaler l'affichage
        try:
            offset = int(request.args.get('semaine', 0))
        except ValueError:
            offset = 0

        today = datetime.now(paris_tz)
        start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
        end_of_week = start_of_week + timedelta(days=4)

        start_sql = start_of_week.strftime('%Y-%m-%d')
        end_sql = (end_of_week + timedelta(days=1)).strftime('%Y-%m-%d')

        week_number = start_of_week.isocalendar()[1]
        period_title = f"Semaine {week_number}"

        connection = get_db_connection()

        # 1. Squelette planning
        planning_squelett = connection.execute(
            'SELECT * FROM semaine_type WHERE actif = 1 ORDER BY heure_debut'
        ).fetchall()

        # 2. Habitudes (Qui est censé venir ?)
        habitudes_data = connection.execute('''
            SELECT h.creneau_id, c.id as client_id, c.prenom, c.nom, c.seances_restantes
            FROM habitudes h
            JOIN clients c ON h.client_id = c.id
        ''').fetchall()

        # 3. Historique de la semaine (Qui est DÉJÀ venu ?)
        presence_data = connection.execute('''
            SELECT client_id, date_heure
            FROM historique_seances
            WHERE date_heure >= ? AND date_heure < ?
            AND action IN ('CHECK-IN', 'PRESENCE_VALIDEE')
        ''', (start_sql, end_sql)).fetchall()

        connection.close()

        # --- TRAITEMENT DES DONNÉES EN PYTHON ---

        # A. Organiser les habitudes par créneau
        clients_par_creneau = {}
        for h in habitudes_data:
            cid = h['creneau_id']
            if cid not in clients_par_creneau:
                clients_par_creneau[cid] = []
            clients_par_creneau[cid].append({
                'id': h['client_id'],
                'nom': f"{h['prenom']} {h['nom']}",
                'solde': h['seances_restantes'],
            })

        # B. Créer une map des pointages : "client_id|YYYY-MM-DD" -> liste des heures
        presences_map = {}
        for p in presence_data:
            date_str = p['date_heure'].replace('T', ' ')
            p_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            key = f"{p['client_id']}|{p_date.strftime('%Y-%m-%d')}"
            if key not in presences_map:
                presences_map[key] = []
            presences_map[key].append(p_date.strftime('%H:%M'))

        # Constantes d'affichage
        HEURE_DEBUT = 9
        HEURE_FIN = 21
        DUREE_TOTAL_MINUTES = (HEURE_FIN - HEURE_DEBUT) * 60
        heure_affichage = [f"{h:02d}:00" for h in range(HEURE_DEBUT, HEURE_FIN + 1)]

        semaine_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
        planning = []

        for jour in range(5):
            jour_date = start_of_week + timedelta(days=jour)
            jour_date_str = jour_date.strftime('%Y-%m-%d')

            creneaux_jour = [c for c in planning_squelett if c['jour_semaine'] == jour]
            creneaux_jour_processed = []

            for creneau in creneaux_jour:
                start_time = datetime.strptime(creneau['heure_debut'], '%H:%M')
                h_debut, m_debut = map(int, start_time.strftime('%H:%M').split(':'))
                min_from_begin = (h_debut - HEURE_DEBUT) * 60 + m_debut
                top_percent = (min_from_begin / DUREE_TOTAL_MINUTES) * 100
                height_percent = (creneau['duree'] / DUREE_TOTAL_MINUTES) * 100

                raw_clients = clients_par_creneau.get(creneau['id'], [])
                final_clients = []

                for cl in raw_clients:
                    is_present = False
                    lookup_key = f"{cl['id']}|{jour_date_str}"

                    if lookup_key in presences_map:
                        heures_pointages = presences_map[lookup_key]
                        course_start_min = h_debut * 60 + m_debut
                        course_end_min = course_start_min + creneau['duree']

                        for hp in heures_pointages:
                            hp_h, hp_m = map(int, hp.split(':'))
                            pointage_min = hp_h * 60 + hp_m
                            # -30 min pour tolérer les check-ins juste avant le cours
                            if (course_start_min - 30) <= pointage_min <= course_end_min:
                                is_present = True
                                break

                    final_clients.append({
                        'id': cl['id'],
                        'nom': cl['nom'],
                        'present': is_present,
                        'solde': cl['solde'],
                    })

                creneaux_jour_processed.append({
                    'data': creneau,
                    'style': f"top: {top_percent}%; height: {height_percent}%;",
                    'clients': final_clients,
                    'date_reelle': jour_date_str,
                })

            planning.append({
                'nom': semaine_fr[jour],
                'date_courte': jour_date.strftime('%d/%m'),
                'is_today': jour_date.date() == today.date(),
                'creneaux': creneaux_jour_processed,
            })

        return render_template(
            'planning.html',
            semaine=planning,
            period_title=period_title,
            offset=offset,
            heures=heure_affichage,
        )


    @app.route('/marquer_presence', methods=['POST'])
    def marquer_presence():
        """Marque manuellement la présence d'un client depuis la modale du planning."""
        client_id = request.form['client_id']
        date_seance = request.form['date_seance']  # YYYY-MM-DD
        heure_seance = request.form['heure_seance']  # HH:MM

        # timestamp exact du début du cours
        timestamp_seance = f"{date_seance} {heure_seance}:00"

        connection = get_db_connection()

        connection.execute(
            'UPDATE clients SET seances_restantes = seances_restantes - 1, total_seances_faites = total_seances_faites + 1 WHERE id = ?',
            (client_id,),
        )
        connection.execute('''
            INSERT INTO historique_seances (client_id, action, nombre, date_heure)
            VALUES (?, ?, ?, ?)
        ''', (client_id, "PRESENCE_VALIDEE", -1, timestamp_seance))

        connection.commit()
        connection.close()

        return redirect(request.referrer or url_for('planning'))


    # ============================================================
    # ROUTES : BORNE (publiques, pour les clients)
    # ============================================================

    @app.route('/borne', methods=['GET', 'POST'])
    def borne():
        """Borne de check-in en libre-service."""
        connection = get_db_connection()

        # cookies pour pré-remplir le formulaire si disponibles
        id_cookie = request.cookies.get('borne_id')
        prenom_cookie = request.cookies.get('borne_prenom')
        nom_cookie = request.cookies.get('borne_nom')

        if request.method == "POST":
            client_id_form = request.form.get('client_id')
            if client_id_form:
                # validation rapide via cookie
                client = connection.execute(
                    'SELECT * FROM clients WHERE id = ?',
                    (client_id_form,),
                ).fetchone()
            else:
                # validation manuelle prénom + nom
                prenom = request.form['prenom'].strip().title()
                nom = request.form['nom'].strip().title()
                client = connection.execute(
                    'SELECT * FROM clients WHERE prenom = ? AND nom = ?',
                    (prenom, nom),
                ).fetchone()

            if client:
                nouveau_solde = client['seances_restantes'] - 1
                client_id = client['id']
                prenom = client['prenom']
                nom = client['nom']
                current_time = datetime.now(paris_tz).strftime('%Y-%m-%d %H:%M:%S')

                connection.execute(
                    'UPDATE clients SET seances_restantes = ?, total_seances_faites = total_seances_faites + 1 WHERE id = ?',
                    (nouveau_solde, client_id),
                )
                connection.execute(
                    'INSERT INTO historique_seances (client_id, action, nombre, date_heure) VALUES (?, ?, ?, ?)',
                    (client_id, "CHECK-IN", -1, current_time),
                )
                connection.commit()
                connection.close()

                # POST/Redirect/GET : empêche le re-décompte au rechargement
                session['borne_succes'] = {'prenom': prenom, 'solde': nouveau_solde}

                response = make_response(redirect(url_for('borne_succes')))

                # cookie 60 jours
                max_age = 60 * 24 * 60 * 60
                response.set_cookie('borne_id', str(client_id), max_age=max_age)
                response.set_cookie('borne_prenom', prenom, max_age=max_age)
                response.set_cookie('borne_nom', nom, max_age=max_age)

                return response

            else:
                connection.close()
                return render_template(
                    'borne.html',
                    erreur="Client non trouvé.",
                    id_cookie=id_cookie,
                    prenom_cookie=prenom_cookie,
                    nom_cookie=nom_cookie,
                )

        # GET : formulaire vide
        connection.close()
        return render_template(
            'borne.html',
            id_cookie=id_cookie,
            prenom_cookie=prenom_cookie,
            nom_cookie=nom_cookie,
        )


    @app.route('/borne_succes')
    def borne_succes():
        """
        Page de confirmation après un pointage à la borne.
        Lit le résultat depuis la session (usage unique) pour éviter
        les re-décomptes au rechargement.
        """
        data = session.pop('borne_succes', None)

        if not data:
            return redirect(url_for('borne'))

        return render_template('borne_succes.html', prenom=data['prenom'], solde=data['solde'])
