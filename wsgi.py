# -*- coding: utf-8 -*-
"""
wsgi.py — Point d'entrée standard de l'application.

Deux usages :

    1) Lancement local (développement) :
           python wsgi.py
       → démarre le serveur de dev Flask sur http://127.0.0.1:5000
       → mode debug piloté par app.config['DEBUG'] (True en DevConfig)

    2) Déploiement production (PythonAnywhere, Gunicorn, uWSGI…) :
       le serveur importe simplement `app` depuis ce fichier :
           from wsgi import app
       et l'objet `app` est déjà configuré via create_app().
"""

from app import create_app

# On instancie l'app UNE fois au chargement du module.
# Le profil de config est déterminé par la variable d'environnement FLASK_ENV
# (voir app/__init__.py -> create_app()).
app = create_app()


if __name__ == '__main__':
    # Lancement direct en local : `python wsgi.py`
    # app.run() lit automatiquement app.config['DEBUG'] pour choisir le mode.
    app.run()
