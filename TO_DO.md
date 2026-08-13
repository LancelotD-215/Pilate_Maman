# TO_DO

## Configuration initiale (avant mise en prod)
- [ ] Choisir le nom définitif du studio → mettre à jour `SITE_NAME` en haut de `app.py`
- [ ] Récupérer identifiant et mot de passe admin de la maman
  - [ ] Mettre à jour `ADMIN_USERNAME` en haut de `app.py`
  - [ ] Générer `ADMIN_PASSWORD_HASH` avec `python set_admin_password.py`, coller dans `app.py`
- [ ] Générer un `SECRET_KEY` aléatoire (`python -c "import secrets; print(secrets.token_hex(32))"`) et le mettre dans `app.py`
- [ ] (Optionnel) Ajouter un logo dans `static/` et l'activer dans `layout.html` + `login.html` (voir commentaires dans ces fichiers)
- [ ] (Optionnel) Ajouter un favicon dans `static/` et le déclarer dans `layout.html` et `login.html`
- [ ] Ajuster la palette dans `static/style.css` (variables `--brand`, `--slot-1..5`)
- [ ] Créer les vrais créneaux de la semaine (via interface — pas encore de page dédiée, à insérer directement en base pour l'instant)
- [ ] Créer la vraie base de production : `python init_db.py`

## Reprise du backlog (à trier avec la maman)
- [ ] Ajout / suppression de séances dans l'agenda (ponctuel et définitif)
- [ ] Ajout d'un client non-inscrit directement depuis une séance
- [ ] Widget "choix des widgets à afficher" sur le tableau de bord
- [ ] Widget "séance en cours"
- [ ] Corriger l'affichage des séances habituelles dans la fiche client
- [ ] Bouton "voir tout l'historique" dans la fiche client
- [ ] Page dédiée à la gestion des créneaux (`semaine_type`) depuis l'interface
- [ ] Vérifier que le compteur "séances du mois" reste correct après ajout de nouveaux types de cours

## Optionnel (nice-to-have)
- [ ] Sélecteur de calendrier pour choisir les créneaux habituels à la création client
- [ ] Section commentaires dans l'agenda
- [ ] Colonne "dernière séance" dans la gestion clients
- [ ] Présence prévue affichée dans l'agenda
