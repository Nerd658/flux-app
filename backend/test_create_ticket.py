import os
from dotenv import load_dotenv

from app.oline import Oline, OlineError

load_dotenv()


def main():
    print("--- CREATION D'UN TICKET TEST SUR OLINE ---\n")
    try:
        oline = Oline()
    except Exception as exc:
        print(f"[ERREUR] Impossible d'initialiser Oline : {exc}")
        return

    caller_email = "hassan.bikienga@orange.com"
    org = "Direction Informatique"
    title = "[TEST] Demande d'ouverture de flux - Test technique"
    description = (
        "Ceci est un ticket de test technique créé par l'application d'ouverture de flux "
        "pour valider la création automatique de ticket vers Oline.\n\n"
        "Paramètres du ticket :\n"
        f"- Organisation : {org}\n"
        f"- Demandeur : {caller_email}\n"
        "- Pièce jointe : Aucune (test initial sans pièce jointe)"
    )

    print(f"Organisation cible : {org}")
    print(f"Demandeur (caller)  : {caller_email}")
    print(f"Titre               : {title}\n")
    print("Envoi de la requête de création à Oline...")

    try:
        ticket = oline.create_ticket(
            title=title,
            description=description,
            org_id=org,
            caller_id=caller_email,
        )
        print("\n[SUCCES] Ticket créé avec succès sur Oline !")
        fields = ticket.get("fields", {})
        ticket_id = ticket.get("id") or ticket.get("key")
        ticket_ref = fields.get("ref") or ticket.get("ref") or ticket.get("friendlyname")
        ticket_title = fields.get("title") or ticket.get("title")
        ticket_status = fields.get("status") or ticket.get("status")

        print(f"- ID iTop        : {ticket_id}")
        print(f"- Référence      : {ticket_ref}")
        print(f"- Titre          : {ticket_title}")
        print(f"- Statut initial : {ticket_status}")
    except OlineError as err:
        print(f"\n[ERREUR] Échec de la création du ticket : {err}")


if __name__ == "__main__":
    main()
