from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime

# 1. Die Rechte definieren, die wir brauchen
SCOPES = ['https://www.googleapis.com/auth/calendar']

# 2. Die Credentials aus der JSON-Datei laden
SERVICE_ACCOUNT_FILE = 'credentials.json'

def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    # 3. Den "Service" bauen (Das ist unsere Schnittstelle zu Google)
    service = build('calendar', 'v3', credentials=creds)
    return service

def check_calendar():
    try:
        service = get_calendar_service()
        print("Erfolgreich eingeloggt!")
        
        # Hier ist nun deine echte Kalender-ID eingetragen:
        MEINE_KALENDER_ID = 'rochecxlab@gmail.com'
        
        # Wir fragen jetzt gezielt nach diesem einen Kalender
        calendar = service.calendars().get(calendarId=MEINE_KALENDER_ID).execute()
        
        print("=========================================")
        print(f"BINGO! Zugriff auf Kalender bestätigt:")
        print(f"Name: {calendar['summary']}")
        print(f"Zeitzone: {calendar['timeZone']}")
        print("=========================================")

    except Exception as e:
        print(f"Fehler beim Zugriff auf den spezifischen Kalender: {e}")
        print("Tipp: Hast du die Kalender-ID richtig kopiert und den Kalender mit dem Service Account geteilt?")

# Wenn wir diese Datei direkt starten, führe den Test aus:
if __name__ == '__main__':
    check_calendar()