import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/documents"]
DOCUMENT_ID = "1r3uN2mztFBHm5RfiLm6SwcaFTOHa1lPZgqulV2XYnF8"


def main():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", scopes=SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                scopes=SCOPES,
            )
            creds = flow.run_local_server(port=0)

            with open("token.json", "w") as token:
                token.write(creds.to_json())

    service = build("docs", "v1", credentials=creds)
    document = service.documents().get(documentId=DOCUMENT_ID).execute()
    print(document)


if __name__ == "__main__":
    main()
