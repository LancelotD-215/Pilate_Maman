# -*- coding: utf-8 -*-
"""
run.py — Point d'entrée pour lancer le serveur de développement local.

    python run.py
    → démarre le serveur sur http://127.0.0.1:5000
    → mode debug ON en dev (piloté par app.config['DEBUG'] dans app/main.py)

En PRODUCTION (PythonAnywhere) : ce fichier n'est PAS utilisé.
Le serveur PythonAnywhere importe directement l'app depuis app/main.py :
    from app.main import app
"""

from app.main import app


if __name__ == '__main__':
    app.run()
