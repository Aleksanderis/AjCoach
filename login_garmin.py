import os
import getpass
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
    GarminConnectConnectionError
)
from dotenv import load_dotenv

PERSONAS_DIR = os.path.join(os.path.dirname(__file__), "personas")

def login_and_save():
    personas = [d for d in os.listdir(PERSONAS_DIR) if os.path.isdir(os.path.join(PERSONAS_DIR, d))]
    if not personas:
        print("No personas found in personas/")
        return
    if len(personas) == 1:
        persona = personas[0]
    else:
        print("Available personas:", ", ".join(personas))
        persona = input("Persona name: ").strip()

    persona_dir = os.path.join(PERSONAS_DIR, persona)
    env_path = os.path.join(persona_dir, ".env")
    load_dotenv(env_path)
    token_dir = os.path.join(persona_dir, ".garmin_tokens")

    email = os.getenv("GARMIN_EMAIL") or input("Garmin Email: ")
    password = getpass.getpass("Garmin Password: ")

    print(f"Attempting to login and save session to {token_dir}...")

    def mfa_callback():
        return input("Enter MFA Code (from email/SMS): ")

    try:
        client = Garmin(email, password, prompt_mfa=mfa_callback)
        client.login(token_dir)
        print(f"\nSuccess! Session tokens saved to {token_dir}")

    except GarminConnectTooManyRequestsError:
        print("\nError: Still being rate limited (429). Please wait 15-30 minutes before trying again.")
    except GarminConnectAuthenticationError:
        print("\nError: Invalid email or password.")
    except Exception as e:
        print(f"\nLogin failed: {e}")

if __name__ == "__main__":
    login_and_save()
