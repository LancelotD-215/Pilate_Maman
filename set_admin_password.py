# -*- coding: utf-8 -*-
"""
author: @lancelot
name : set_admin_password.py
description : petit utilitaire pour générer un hash de mot de passe admin
              au format attendu par app.py (Werkzeug pbkdf2:sha256).

Usage :
    python set_admin_password.py
    # Saisir le mot de passe (masqué), puis copier la ligne obtenue
    # dans app.py -> ADMIN_PASSWORD_HASH.
"""

from getpass import getpass
from werkzeug.security import generate_password_hash


def main():
    pwd = getpass("Nouveau mot de passe admin : ")
    if not pwd:
        print("❌ Mot de passe vide, abandon.")
        return
    pwd_confirm = getpass("Confirmer : ")
    if pwd != pwd_confirm:
        print("❌ Les mots de passe ne correspondent pas, abandon.")
        return

    print("\n✅ Copier la ligne ci-dessous dans app.py :\n")
    print(f'ADMIN_PASSWORD_HASH = "{generate_password_hash(pwd)}"\n')


if __name__ == "__main__":
    main()
