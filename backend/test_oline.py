import os
from dotenv import load_dotenv

from app.oline import Oline, OlineError

load_dotenv()


def tester_connexion():
    url = os.getenv("OLINE_URL")
    api_key = os.getenv("OLINE_API_KEY")

    if not url:
        print("[ERREUR] OLINE_URL n'est pas configure dans votre environnement ou fichier .env.")
        return

    print(f"Tentative de connexion a : {url}")
    print(f"Authentification presente : {'Oui' if api_key else 'Non'}\n")

    try:
        instance_oline = Oline()
    except Exception as exc:
        print(f"[ERREUR] Initialisation impossible : {exc}")
        return

    print("--- DEBUT DE LA RECUPERATION DES PARAMETRES ---\n")

    try:
        orgs = instance_oline.get_organizations()
        print(f"[OK] get_organizations() - {len(orgs)} element(s) :")
        print(f"     Exemples : {orgs[:5]}")
    except OlineError as err:
        print(f"[ERREUR] get_organizations() a echoue : {err}")

    try:
        emails = instance_oline.get_person_emails()
        print(f"[OK] get_person_emails() - {len(emails)} element(s) :")
        print(f"     Exemples : {emails[:5]}")
    except OlineError as err:
        print(f"[ERREUR] get_person_emails() a echoue : {err}")

    try:
        teams = instance_oline.get_teams()
        print(f"[OK] get_teams() - {len(teams)} element(s) :")
        print(f"     Exemples : {teams[:5]}")
    except OlineError as err:
        print(f"[ERREUR] get_teams() a echoue : {err}")

    try:
        services = instance_oline.get_services()
        print(f"[OK] get_services() - {len(services)} element(s) :")
        print(f"     Exemples : {services[:5]}")
    except OlineError as err:
        print(f"[ERREUR] get_services() a echoue : {err}")

    try:
        subcats = instance_oline.get_service_subcategories()
        print(f"[OK] get_service_subcategories() - {len(subcats)} element(s) :")
        print(f"     Exemples : {subcats[:5]}")
    except OlineError as err:
        print(f"[ERREUR] get_service_subcategories() a echoue : {err}")

    print("\n--- FIN DES TESTS ---")


if __name__ == "__main__":
    tester_connexion()
