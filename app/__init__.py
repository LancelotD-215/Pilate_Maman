# -*- coding: utf-8 -*-
"""
app/__init__.py — Application factory Flask.

Ce fichier expose la fonction create_app() qui assemble et retourne une
instance Flask prête à servir, à partir d'un profil de config choisi
(development / production / testing).

Séquence :
    1. Charger les variables du .env dans l'environnement (via python-dotenv)
    2. Sélectionner le profil de config (dépend de FLASK_ENV)
    3. Créer l'instance Flask
    4. Appliquer la config à app.config
    5. Enregistrer les routes / hooks / filtres via register_routes(app)
    6. Retourner l'app prête

Le point d'entrée réel (celui qui exécute create_app()) est wsgi.py à la racine.
"""

import os
from flask import Flask
from dotenv import load_dotenv

# Charger le .env AVANT tout autre import qui utilise os.environ, sinon
# les variables ne seraient pas dispo au moment de lire la config.
load_dotenv()

from app.config import configs


def create_app(config_name=None):
    """
    Fabrique une instance Flask configurée.

    Args:
        config_name (str, optional): 'development', 'production' ou 'testing'.
            Si None (défaut), lu depuis la variable d'environnement FLASK_ENV,
            elle-même par défaut à 'development'.

    Returns:
        Flask: instance de l'application prête à être servie.

    Raises:
        ValueError: si le nom de config n'est pas reconnu.
    """
    # 1. Choix du profil de config
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    if config_name not in configs:
        raise ValueError(
            f"Config inconnue : {config_name!r}. Valeurs valides : {list(configs)}"
        )

    # 2. Création de l'instance Flask + application de la config
    app = Flask(__name__)
    app.config.from_object(configs[config_name])

    # 3. Enregistrement des routes, hooks et filtres (voir app/routes.py)
    from app.routes import register_routes
    register_routes(app)

    return app
