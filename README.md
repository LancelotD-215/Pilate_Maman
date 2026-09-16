# 📂 Gestion Pilates — Gestionnaire de Séances

Application web de gestion pour un studio de Pilates (ou toute activité à
prestations comptées) : soldes de séances par client, présences, planning
hebdomadaire et borne de check-in en libre-service.

Base de code générique, prête à être personnalisée (nom du studio, palette,
logo, identifiants admin) pour un nouveau déploiement.

---

## 🎯 1. Objectif

- Remplacer le suivi papier par une base de données numérique
- Gérer les soldes de séances de chaque client
- Suivre la fréquentation et les inscriptions (créneaux récurrents)
- Visualiser le planning hebdomadaire et valider les présences
- Permettre aux clients de pointer eux-mêmes via une **borne**
- Interface responsive (ordinateur / tablette / mobile)

---

## 🛠 2. Stack technique

| Couche          | Technologie                                    |
|-----------------|------------------------------------------------|
| Backend         | Python 3 + **Flask 3.1**                       |
| Base de données | **SQLite** (`database_clients.db`)             |
| Templates       | Jinja2 + **Bootstrap 5.3**                     |
| JavaScript      | jQuery + **DataTables** (tableaux interactifs) |
| Icônes          | Font Awesome 6.4                               |
| Fuseau horaire  | **pytz** (`Europe/Paris`)                      |

Architecture : monolithique simple (`app.py` + `app_lib.py`).

---

## 🗄 3. Structure des données

Schéma complet dans [`schema.sql`](schema.sql).

### Table `clients`
`id`, `prenom`, `nom`, `date_inscription`, `telephone`, `email`,
`seances_restantes` (solde courant), `total_seances_faites`, `abonnement`.

### Table `semaine_type` (créneaux récurrents)
`id`, `jour_semaine` (0=Lundi … 6=Dimanche), `heure_debut` (`"HH:MM"`),
`duree` (minutes), `type_seance`, `actif`.

### Table `inscriptions` (créneaux récurrents auxquels un client est inscrit)
`id`, `client_id` → `clients`, `creneau_id` → `semaine_type`, `date_debut`.

### Table `historique_seances`
`id`, `client_id`, `date_heure`, `action`, `nombre` (variation +/−), `seance_id`.
Valeurs d'`action` : `CHECK-IN`, `PRESENCE_VALIDEE`, `ADD_SEANCES`,
`NEW_ACCOUNT`, `IMPORT_INITIAL`.

### Table `calendrier_seances` *(créée, pas encore exploitée)*
Destinée au planning des séances réelles avec statuts.

---

## 💻 4. Fonctionnalités

### 🏠 Tableau de bord (`/`)
Widgets d'alerte et de suivi :
- Clients à solde **négatif** (régularisation rapide possible)
- Clients à solde **zéro**
- **Meilleur client** du mois (le plus de séances faites)
- Client avec le **plus de séances restantes**
- **Nombre total** de clients
- **Séances données** dans le mois
- Clients **pas venus depuis 30 jours**

### 👥 Gestion des clients (`/gestion_clients`)
Liste complète avec DataTables (tri, recherche, pagination), badges colorés
selon le solde (vert / orange / rouge), ajout rapide de séances en un clic.

### ✅ Présence / Check-in (`/presence`)
Saisie prénom + nom → décrément automatique du solde + entrée dans l'historique.

### 🖥️ Borne libre-service (`/borne`)
Check-in autonome par le client. Mémorise l'identité via **cookies** (60 jours)
pour un pointage en un clic les fois suivantes. Page de succès dédiée.

### 📝 Nouveau client (`/ajout_client`)
Formulaire complet (identité, contact, solde initial, abonnement) avec choix
d'un créneau récurrent → création automatique de l'inscription associée.

### 💰 Ajout de séances (`/ajout_seances` et ajout rapide)
Recharge des comptes, depuis la page dédiée, la liste clients ou la fiche client.
Traçabilité complète dans l'historique.

### 📅 Planning hebdomadaire (`/planning`)
Vue calendrier (Lundi→Vendredi, 9h–21h), navigation semaine par semaine,
créneaux positionnés à l'heure, mise en évidence du jour courant.
Affiche les clients inscrits attendus par créneau et leur **statut de présence**
(pointage détecté entre −30 min et la fin du cours). Validation manuelle
de présence directement depuis un créneau.

### 👤 Fiche client (`/client/<id>`)
Coordonnées, solde, statistiques, inscriptions (créneaux récurrents),
10 dernières actions de l'historique, ajout de séances et **modification des
inscriptions** via modale. Accessible aussi par la recherche globale (barre de nav).
Suppression du client possible depuis la fiche.

---

## 📁 5. Architecture des fichiers

```
Pilate_Maman/
├── app.py                  # Application Flask : toutes les routes + config (SITE_NAME, credentials)
├── app_lib.py              # Fonctions utilitaires (connexion DB, widgets, stats)
├── schema.sql              # Structure complète de la base
├── init_db.py              # Initialise une base VIDE (production)
├── init_db_test.py         # Initialise une base avec un jeu de démo (dev local)
├── set_admin_password.py   # Génère un hash pbkdf2 pour ADMIN_PASSWORD_HASH
├── requirements.txt        # Dépendances Python
├── database_clients.db     # Base SQLite (NON versionnée — voir .gitignore)
├── static/
│   └── style.css           # Palette & styles personnalisés (variables --brand, --slot-1..5)
└── templates/              # Pages HTML (Bootstrap + Jinja2)
    ├── layout.html         # Structure générale + navigation
    ├── login.html          # Page de connexion admin
    ├── index.html          # Tableau de bord
    ├── gestion_clients.html
    ├── fiche_client.html
    ├── ajout_client.html
    ├── ajout_seances.html
    ├── presence.html
    ├── borne.html          # Borne de check-in (public)
    ├── borne_succes.html
    └── planning.html       # Planning hebdomadaire
```

---

## ⚙️ 6. Installation et lancement (local)

```bash
# 1. Cloner le projet
git clone <votre-repo>
cd Pilate_Maman

# 2. Créer et activer un environnement virtuel (recommandé)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Initialiser une base de données locale avec un jeu de démonstration
python init_db_test.py
# → crée database_clients.db avec 5 créneaux et 4 clients de test.

# 5. Lancer l'application
python app.py
# → http://localhost:5000
# → Connexion : admin / admin (À CHANGER — voir §7)
```

Le mode `debug` s'active automatiquement en local et se désactive en
production (détection de la variable `PYTHONANYWHERE_DOMAIN`).

---

## 🔐 7. Personnalisation (à faire une fois avant la mise en prod)

Toute la configuration tient dans le bloc en haut de [`app.py`](app.py) :

```python
SITE_NAME = "Gestion Pilates"                     # Nom affiché partout
ADMIN_USERNAME = "admin"                          # Identifiant admin
ADMIN_PASSWORD_HASH = "pbkdf2:sha256:..."         # Hash du mot de passe (voir ci-dessous)
SECRET_KEY = "dev-secret-CHANGEZ-MOI-EN-PROD"     # Clé de signature des cookies de session
```

**Générer un nouveau mot de passe admin :**
```bash
python set_admin_password.py
# Saisir le mot de passe, coller la ligne obtenue dans app.py.
```

**Générer une SECRET_KEY aléatoire :**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Palette & couleurs :** variables CSS dans [`static/style.css`](static/style.css)
(`--brand`, `--slot-1..5`, fonds).

**Logo & favicon :** déposer dans `static/`, activer les balises correspondantes
dans [`templates/layout.html`](templates/layout.html) et
[`templates/login.html`](templates/login.html) (blocs commentés prêts à l'emploi).

---

## 🚀 8. Déploiement en production

```bash
# 1. Configurer app.py (voir §7)
# 2. Créer une base de production vide
python init_db.py

# 3. Sur le serveur (PythonAnywhere, VPS, …), déployer les fichiers et
#    reload la web app. La base n'est PAS versionnée, chaque environnement a la sienne.
```

> ⚠️ La base de données (`*.db`) **n'est pas versionnée** (voir `.gitignore`).
> Ne jamais commiter de données réelles de clients (RGPD).

---

## 📋 9. Suites prévues

Voir [`TO_DO.md`](TO_DO.md).
