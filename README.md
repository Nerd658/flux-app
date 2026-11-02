# Demandes d'ouverture de flux

FastAPI + PostgreSQL / MySQL (SQLAlchemy) · React (Vite) · validation à 3 niveaux scellée en Ed25519 · export PDF officiel · synchronisation de tickets Oline / iTop.

```bash
# 1. Base de données PostgreSQL (Docker)
docker run -d --name flux-postgres -p 127.0.0.1:5435:5432 -e POSTGRES_DB=flux_db -e POSTGRES_USER=flux_user -e POSTGRES_PASSWORD=flux_password postgres:16-alpine

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate        # Linux/macOS (.venv\Scripts\activate sous Windows)
pip install -r requirements.txt
python -m app.seed                                     # tables + données initiales + comptes fictifs
uvicorn app.main:app --host 127.0.0.1 --port 8000
pytest -q tests                                        # 21 tests automatisés

# 3. Frontend
cd frontend
npm install
npm run build                                          # build de production
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
