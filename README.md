# Demandes d'ouverture de flux

FastAPI + PostgreSQL / MySQL (SQLAlchemy) · React (Vite) · validation à 3 niveaux scellée en Ed25519 · export PDF officiel · synchronisation de tickets Oline / iTop.

## Déploiement en Production (Docker Compose + Nginx Hôte)

L'application est conteneurisée pour un déploiement sécurisé avec persistance complète des données :

```bash
# 1. Vérifier la configuration backend/.env
# S'assurer que JWT_SECRET, KEY_ENCRYPTION_SECRET et DATABASE_URL sont définis

# 2. Démarrer l'ensemble des conteneurs
docker compose up -d --build

# 3. Vérifier l'état des services
docker compose ps
docker compose logs -f backend
```

Les conteneurs sont configurés comme suit :
* **Base de données (`flux-db`)** : PostgreSQL 16 Alpine avec volume persistant nommé `flux_postgres_data`. Les données sont préservées même en cas d'arrêt ou de suppression du conteneur.
* **Backend (`flux-backend`)** : FastAPI orchestré par Gunicorn avec 4 workers Uvicorn sur `127.0.0.1:8000`.
* **Frontend (`flux-frontend`)** : React SPA compilé et servi par Nginx Alpine sur `127.0.0.1:3000`.

Pour le reverse proxy du serveur hôte, un modèle de configuration prêt à l'emploi est disponible dans `nginx-host.conf.example`.

## Démarrage en Développement Local
docker run -d --name flux-postgres -p 127.0.0.1:5435:5432 -e POSTGRES_DB=flux_db -e POSTGRES_USER=flux_user -e POSTGRES_PASSWORD=flux_password postgres:16-alpine

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate        # Linux/macOS (.venv\Scripts\activate sous Windows)
pip install -r requirements.txt
python -m app.seed                                     # tables + données initiales + comptes fictifs
uvicorn app.main:app --host 127.0.0.1 --port 8000
pytest -q tests                                        # 34 tests automatisés

# 3. Frontend
cd frontend
npm install
npm run build                                          # build de production
```

Configuration Oline (iTop) dans `backend/.env` :
```ini
OLINE_URL=https://<votre-serveur-itop-oline>/webservices/rest.php
OLINE_API_KEY=<token_ou_cle_api_base64>
OLINE_VERIFY_SSL=true
```

Comptes fictifs de développement (mot de passe applicatif = `SEED_PASSWORD`) :
- `DEMD0001` : Demandeur
- `MGR00001` : Manager de département (Direction CX)
- `SECU0001` : Validateur Technique Sécurité
- `RSSI0001` : RSSI (Validation finale)
- `ADMN0001` : Administrateur Système

## Circuit de validation

Le processus de validation s'articule en 3 étapes successives :

| Niveau | Rôle | Conditions et permissions |
|---|---|---|
| Niveau 1 | Manager de département (`manager`) | Filtre strict par CUID : ne voit et ne valide que les demandes dont le département lui est rattaché (`manager_cuid`). |
| Niveau 2 | Validateur Technique (`securite`) | Contrôle de conformité réseau et sécurité après validation du manager. |
| Niveau 3 | RSSI (`rssi`) | Approbation finale de sécurité SI débloquant le PDF scellé et la création du ticket Oline / iTop. |

## Gestion multi-managers par direction et contrôles anti-contournement

Pour les directions regroupant plusieurs départements (ex: DRSI) :
- L'administrateur peut associer plusieurs CUIDs de managers autorisés à une même direction (séparés par des virgules dans `/admin/referentiels`).
- Lors de la soumission d'une demande, si la direction possède plusieurs managers, un menu déroulant restreint oblige le demandeur à choisir son responsable légitime.
- Le serveur applique des contrôles stricts anti-contournement (Zero Trust) :
  1. Rejet si le manager choisi n'est pas déclaré pour la direction (`400 Bad Request`).
  2. Rejet si le compte manager ne possède pas le rôle `manager` ou `admin`.
  3. Rejet si le demandeur tente de s'auto-désigner comme manager.
  4. Récupération et application des coordonnées officielles du compte manager pour éliminer toute usurpation de coordonnées.

## Profil utilisateur et annuaire Active Directory

Lorsqu'un collaborateur se connecte pour la première fois via l'annuaire d'entreprise (Active Directory) avec des attributs par défaut (ex. nom égal au CUID, email en `@annuaire.invalid`), l'application lui propose automatiquement une modale de complétion de profil :
- Prénom et Nom réels
- Email professionnel nominatif
- Direction de rattachement (sélectionnée parmi les directions configurées)
- Téléphone de contact

Ces informations sont persistées en base et protégées contre tout écrasement lors des futures authentifications AD.

## Intégration Oline / iTop

L'application intègre un client Oline (`backend/app/oline.py`) pour la génération automatique de tickets d'ouverture de flux dès la validation finale par le RSSI :
- Création de la demande sous la classe `UserRequest` avec l'organisation (`Direction Informatique`).
- Description détaillée reprenant le demandeur, le département, les dates et la liste complète des flux demandés.
- Attachement du PDF scellé et signé électroniquement directement en pièce jointe du ticket.

## Vérification d'authenticité et d'intégrité

Un portail de vérification accessible sur `/verifier` (et via l'API `GET /api/public/verify?q=...`) permet aux ingénieurs réseau et exploitants de contrôler la validité d'une demande avant ouverture sur le pare-feu :
- Recherche directe par référence de demande (`DOF-2026-000001`) ou par numéro de ticket Oline (`R-211299`).
- Recalcul de l'empreinte SHA-256 et contrôle mathématique des 3 signatures asymétriques Ed25519 (Manager, Technique, RSSI).
- Affichage des règles approuvées ou refus clair si la demande n'existe pas ou a été altérée.
