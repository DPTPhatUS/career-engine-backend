from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class GoogleDocsService:
    def __init__(self, credentials: Credentials):
        self.service = build("docs", "v1", credentials=credentials, cache_discovery=False)

    def create_document(self, title: str) -> str:
        document = self.service.documents().create(body={"title": title}).execute()
        return document["documentId"]

    def batch_update(self, document_id: str, requests: list[dict]) -> dict:
        return self.service.documents().batchUpdate(
            documentId=document_id,
            body={"requests": requests},
        ).execute()

    def get_append_index(self, document_id: str) -> int:
        document = self.service.documents().get(documentId=document_id).execute()
        body_content = document.get("body", {}).get("content", [])

        if not body_content or "endIndex" not in body_content[-1]:
            raise ValueError("Unable to derive append index from document body content.")

        return max(1, body_content[-1]["endIndex"] - 1)
