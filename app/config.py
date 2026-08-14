# -*- coding: utf-8 -*-
"""
app/config.py — Configurations de l'application selon l'environnement.

Chaque classe = un profil de réglages :
    - DevConfig  : développement local (debug ON, tolérant)
    - ProdConfig : serveur de production (debug OFF, strict sur les secrets)
    - TestConfig : tests automatisés (base fictive, session simplifiée)

Le choix du profil se fait via la variable d'environnement FLASK_ENV.
"""

import os
from datetime import timedelta


class BaseConfig:
    """Réglages communs à tous les environnements."""

    # Nom du site affiché dans les templates (via {{ site_name }})
    SITE_NAME = os.environ.get('SITE_NAME', 'Gestion Pilates')

    # Identifiants admin (accès à l'espace de gestion)
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH', '')

    # Durée de vie de la session persistante ("Rester connecté" coché)
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)


class DevConfig(BaseConfig):
    """Environnement de développement local."""

    DEBUG = True
    # En dev, on tolère un fallback si SECRET_KEY manque dans le .env
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-fallback-CHANGEZ-MOI')


class ProdConfig(BaseConfig):
    """Environnement de production (serveur)."""

    DEBUG = False
    # En prod, SECRET_KEY DOIT venir de l'environnement.
    # Si elle est absente, l'app refusera de démarrer (protection anti-oubli).
    SECRET_KEY = os.environ['SECRET_KEY']


class TestConfig(BaseConfig):
    """Environnement des tests automatisés."""

    TESTING = True
    DEBUG = False
    SECRET_KEY = 'test-secret-key'


# Mapping "nom lisible" -> classe de config. Utilisé par create_app().
configs = {
    'development': DevConfig,
    'production': ProdConfig,
    'testing': TestConfig,
}