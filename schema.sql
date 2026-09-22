/*
author: @lancelot   
name : schema.sql
description : 
date : 2026/01/20
*/



-- Supprimer les tables existantes pour éviter les conflits (ordre inverse des dépendances)
DROP TABLE IF EXISTS historique_seances;
DROP TABLE IF EXISTS annulations_cours;
DROP TABLE IF EXISTS previsions;
DROP TABLE IF EXISTS inscriptions;
DROP TABLE IF EXISTS habitudes;              -- ancien nom, conservé pour nettoyer les anciennes bases
DROP TABLE IF EXISTS calendrier_seances;
DROP TABLE IF EXISTS semaine_type;
DROP TABLE IF EXISTS clients;

-- Création de la table des clients
CREATE TABLE clients(
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Identifiant unique pour chaque client, INTEGER pour un entier, AUTOINCREMENT pour qu'il s'incrémente automatiquement
    prenom TEXT NOT NULL, --TEXT pour chaine de caractères, NOT NULL pour que ce champ soit obligatoire
    nom TEXT NOT NULL,
    date_inscription DATE DEFAULT CURRENT_DATE,
    telephone TEXT,
    email TEXT,
    seances_restantes INTEGER DEFAULT 0,
    total_seances_faites INTEGER DEFAULT 0,
    abonnement INTEGER DEFAULT 0,
    notes TEXT DEFAULT ''    -- Notes libres saisies dans la fiche client
);

-- Création de la table des créneaux types de la semaine
CREATE TABLE semaine_type (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jour_semaine INTEGER NOT NULL,
    heure_debut TEXT NOT NULL,
    duree INTEGER DEFAULT 60,
    type_seance TEXT DEFAULT 'Collectif',
    actif INTEGER DEFAULT 1
);

-- Création de la table des inscriptions des clients à des créneaux récurrents
-- Un client "inscrit" à un créneau est censé venir toutes les semaines à ce créneau
-- (sauf si frequence = 'bimensuel' : alors une semaine sur deux à partir de date_debut).
CREATE TABLE inscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    creneau_id INTEGER NOT NULL,
    date_debut DATE DEFAULT (date('now')),
    frequence TEXT DEFAULT 'hebdo',             -- 'hebdo' (toutes les semaines) ou 'bimensuel' (1 sem/2)
    FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE,
    FOREIGN KEY (creneau_id) REFERENCES semaine_type(id) ON DELETE CASCADE
);

-- Création de la table des cours annulés (annulation ponctuelle d'un créneau pour une date précise)
-- Ex: "Le cours du lundi 25 mars est annulé car la prof est malade"
CREATE TABLE annulations_cours (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creneau_id INTEGER NOT NULL,
    date_seance DATE NOT NULL,                          -- date précise du cours annulé
    raison TEXT,                                        -- optionnel : pourquoi (ex: "maladie", "jour férié")
    date_annulation DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(creneau_id, date_seance),
    FOREIGN KEY (creneau_id) REFERENCES semaine_type(id) ON DELETE CASCADE
);

-- Création de la table des prévisions (client confirmé pour un cours à une date précise)
-- Contrairement aux inscriptions (récurrentes), les prévisions sont datées :
-- "Sophie a confirmé qu'elle vient au Pilates du 25 mars"
CREATE TABLE previsions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    creneau_id INTEGER NOT NULL,
    date_seance DATE NOT NULL,                          -- date précise du cours (pas récurrent)
    date_confirmation DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, creneau_id, date_seance),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (creneau_id) REFERENCES semaine_type(id) ON DELETE CASCADE
);

-- Création de la table du calendrier des séances
CREATE TABLE calendrier_seances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_heure DATETIME NOT NULL,
    duree INTEGER DEFAULT 60,
    statut TEXT DEFAULT 'PLANIFIE',
    creneau_id INTEGER,
    FOREIGN KEY (creneau_id) REFERENCES semaine_type(id)
);

-- Création de la table de l'historique des séances
CREATE TABLE historique_seances(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    date_heure DATETIME DEFAULT CURRENT_TIMESTAMP,
    action TEXT NOT NULL,     -- CHECK-IN, PRESENCE_VALIDEE, ADD_SEANCES, NEW_ACCOUNT, RECTIFICATION
    nombre INTEGER DEFAULT 0, -- nb de séances ajoutées ou utilisées (négatif si utilisées)
    forfait TEXT,             -- pour ADD_SEANCES : 'essai', 'unite', '10', '20', 'autre' (NULL pour les autres actions)
    seance_id INTEGER,
    annulee INTEGER DEFAULT 0, -- 1 si l'entrée a été annulée (ex: fausse manip de présence)
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (seance_id) REFERENCES calendrier_seances(id)
);