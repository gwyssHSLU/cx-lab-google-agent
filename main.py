from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
from datetime import datetime, timedelta
import base64
from email.message import EmailMessage
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# --- Google Calendar Setup ---
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.send'
]

if os.path.exists('secrets/credentials.json'):
    SERVICE_ACCOUNT_FILE = 'secrets/credentials.json'
else:
    SERVICE_ACCOUNT_FILE = 'credentials.json'

def get_gmail_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('gmail', 'v1', credentials=creds)
    return service


def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return service
# -----------------------------


# Wir initialisieren die FastAPI App
app = FastAPI(title="CX Lab Calendar API")

# Wir definieren, wie die Daten aussehen müssen, die watsonx uns schickt
class FreeBusyRequest(BaseModel):
    participant_email: str
    moderator_email: str
    note_taker_email: str
    time_min: str # ISO 8601 Format (z.B. "2026-05-01T09:00:00Z")
    time_max: str # ISO 8601 Format
    session_duration_minutes: int

# Dies ist unser neuer Endpunkt
@app.post("/freebusy")
def check_joint_availability(request: FreeBusyRequest):
    service = get_calendar_service()
    
    body = {
        "timeMin": request.time_min,
        "timeMax": request.time_max,
        "items": [
            {"id": request.participant_email},
            {"id": request.moderator_email},
            {"id": request.note_taker_email}
        ]
    }

    # 1. Busy-Zeiten von Google holen
    fb_response = service.freebusy().query(body=body).execute()
    calendars = fb_response.get('calendars', {})

    all_busy_periods = []
    for cal_id, cal_data in calendars.items():
        for busy in cal_data.get('busy', []):
            # Text in echte Zeit-Objekte umwandeln (das 'Z' am Ende entfernen wir kurz für Python)
            start_time = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
            all_busy_periods.append((start_time, end_time))

    # 2. Besetzte Zeiten sortieren (damit wir sie von vorne nach hinten durchgehen können)
    all_busy_periods.sort(key=lambda x: x[0])

    # 3. Den Start- und Endpunkt der gesamten Suche festlegen
    search_start = datetime.fromisoformat(request.time_min.replace('Z', '+00:00'))
    search_end = datetime.fromisoformat(request.time_max.replace('Z', '+00:00'))
    duration = timedelta(minutes=request.session_duration_minutes)

    # 4. Der "Lücken-Finder" Algorithmus
    available_slots = []
    current_time = search_start

    for busy_start, busy_end in all_busy_periods:
        # Wenn zwischen "jetzt" und dem nächsten Termin genug Platz ist:
        while current_time + duration <= busy_start:
            available_slots.append({
                "start": current_time.isoformat().replace('+00:00', 'Z'),
                "end": (current_time + duration).isoformat().replace('+00:00', 'Z')
            })
            current_time += duration # Einen Slot weiter hüpfen
            
        # Wir springen ans Ende des aktuellen Termins, falls der später ist als unsere jetzige Zeit
        if busy_end > current_time:
            current_time = busy_end

    # 5. Nach dem letzten Termin noch bis zum Ende des Such-Zeitraums prüfen
    while current_time + duration <= search_end:
        available_slots.append({
            "start": current_time.isoformat().replace('+00:00', 'Z'),
            "end": (current_time + duration).isoformat().replace('+00:00', 'Z')
        })
        current_time += duration

    return {
        "status": "success",
        "message": f"Ich habe {len(available_slots)} moegliche Zeitfenster gefunden, an denen alle Zeit haben.",
        "available_slots": available_slots
    }

class CreateEventRequest(BaseModel):
    title: str
    start_time: str # ISO 8601 Format (z.B. "2026-05-04T14:00:00Z")
    end_time: str   # ISO 8601 Format (z.B. "2026-05-04T15:00:00Z")
    participant_email: str
    moderator_email: str
    note_taker_email: str
    is_remote: bool = True # Standardmäßig Remote (generiert einen Meet Link)

class SendEmailRequest(BaseModel):
    recipient_email: str
    subject: str
    body_text: str


# Der Health Check bleibt erhalten
@app.get("/health")
def health_check():
    return {"status": "ok", "app": "app_google_calendar"}

@app.post("/send-email")
def send_invitation_email(request: SendEmailRequest):
    try:
        # Hier eure echten Daten eintragen:
        SENDER_EMAIL = "rochecxlab@gmail.com"
        # Liest das Passwort aus der Cloud-Konfiguration oder nutzt das lokale zum Testen
        APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

        # 1. Die E-Mail aufbauen
        msg = MIMEMultipart()
        msg['From'] = f"CX Lab Agent <{SENDER_EMAIL}>"
        msg['To'] = request.recipient_email
        msg['Subject'] = request.subject

        # Den Text aus der Anfrage anhängen
        msg.attach(MIMEText(request.body_text, 'plain'))

        # 2. Sichere Verbindung zu Google Gmail aufbauen und senden
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)

        return {
            "status": "success",
            "message": "E-Mail erfolgreich ueber rochecxlab gesendet!",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim E-Mail-Versand: {str(e)}")

@app.post("/create-event")
def create_calendar_event(request: CreateEventRequest):
    try:
        service = get_calendar_service()
        
        # Die feste ID eures CX Lab Kalenders (hier werden alle Termine gebucht)
        CX_LAB_CALENDAR_ID = 'rochecxlab@gmail.com'
        
        # 1. Das Event-Objekt zusammenbauen
        event = {
            'summary': request.title,
            'description': 'Automatischer Termin, erstellt durch den CX Lab Scheduling Agent.',
            'start': {
                'dateTime': request.start_time,
                # Das Z durch einen sauberen UTC-Offset ersetzen, falls nötig
            },
            'end': {
                'dateTime': request.end_time,
            },
            # --- FÜR LOKALE TESTS AUSKOMMENTIERT ---
            # Ohne Domain-Wide Delegation dürfen Service Accounts keine Gäste einladen.
            # 'attendees': [
            #     {'email': request.participant_email},
            #     {'email': request.moderator_email},
            #     {'email': request.note_taker_email},
            # ],
            # ---------------------------------------
        }

        # 2. Wenn es ein Remote-Test ist, generieren wir EIGENTLICH einen Meet Link.
        # Da wir im Dev-Setup (ohne DWD/Workspace) einen 400 Error bekommen, 
        # fangen wir das hier für lokale Tests ab und schreiben den Link in die Beschreibung.
        
        # Original-Code (auskommentiert für Dev):
        # if request.is_remote:
        #     event['conferenceData'] = {
        #         'createRequest': {
        #             'requestId': f"cx-lab-meet-{datetime.now().timestamp()}",
        #             'conferenceSolutionKey': {'type': 'hangoutsMeet'}
        #         }
        #     }
        
        # Dev-Workaround:
        if request.is_remote:
            event['description'] += '\n\n[DEV-MODUS: Remote Test - Hier würde später der automatisch generierte Google Meet Link stehen.]'


        # 3. Den Termin bei Google eintragen
        # conferenceDataVersion=1 ist zwingend nötig, damit der Meet-Link generiert wird
        created_event = service.events().insert(
            calendarId=CX_LAB_CALENDAR_ID, 
            body=event, 
            sendUpdates='all', # Schickt automatisch Einladungs-E-Mails an die Gäste!
            conferenceDataVersion=1
        ).execute()

        return {
            "status": "success",
            "message": "Termin erfolgreich gebucht!",
            "event_id": created_event.get('id'),
            "event_link": created_event.get('htmlLink'),
            "meet_link": created_event.get('hangoutLink', 'Kein Meet Link (Onsite)')
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler bei der Terminerstellung: {str(e)}")