import os.path
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/documents"]
DOCUMENT_ID = "16dTVwalHaMiACxwjLNzCr5nRXaB_jsc-KzxCHy9BTPY"

FULL_NAME = "Jobby McJobface"
EMAIL = "jobbymcjobface@gmail.com"
PHONE = "0123-456-789"
ADDRESS = "Somewhere, Earth"
GITHUB = "GitHub"
GITHUB_URL = "https://github.com"

UNIVERSITY = "University of Life"
DEGREE = "Bachelor of Science"
FIELD = "Advanced Program in Computer Science"
TIME_PERIOD = "Oct. 2023 - Oct. 2027 (Est.)"
GPA = "3.63/4.0"

SAMPLE_PROJECT_TITLE = "Career Engine"
SAMPLE_PROJECT_DATE = "Jan. 2026 - Present"
SAMPLE_PROJECT_STACK = "Python, FastAPI, Google Docs API, PostgreSQL"
SAMPLE_PROJECT_BULLETS = [
    "Built a resume management backend to generate and update structured resume sections automatically.",
    "Implemented batched Google Docs API requests to insert and style content with consistent formatting.",
    "Designed modular section writers to support scalable additions for projects, education, and skills.",
]

SKILLS_LANGUAGES = "Python, SQL, JavaScript"
SKILLS_FRAMEWORKS = "FastAPI, Flask, React"
SKILLS_TOOLS = "Git, Docker, Google Cloud"

HEADER_FONT_SIZE = 13
BODY_FONT_SIZE = 11
HEADER_FONT_FAMILY = "Garamond"
BODY_FONT_FAMILY = "Garamond"


def get_credentials():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", scopes=SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                creds = None
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                scopes=SCOPES,
            )
            creds = flow.run_local_server(port=0)

            with open("token.json", "w", encoding="utf-8") as token:
                token.write(creds.to_json())

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            scopes=SCOPES,
        )
        creds = flow.run_local_server(port=0)

        with open("token.json", "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return creds


def get_append_index(service, document_id):
    document = service.documents().get(documentId=document_id).execute()
    body_content = document.get("body", {}).get("content", [])

    if not body_content or "endIndex" not in body_content[-1]:
        raise ValueError("Unable to derive append index from document body content.")

    return max(1, body_content[-1]["endIndex"] - 1)


def insert_link(requests, start, end, url):
    """Apply link styling to a range of text."""
    requests.append(
        {
            "updateTextStyle": {
                "range": {
                    "startIndex": start,
                    "endIndex": end,
                },
                "textStyle": {
                    "link": {
                        "url": url,
                    }
                },
                "fields": "link",
            }
        }
    )


def add_paragraph_border_bottom(requests, start, end, *, width_pt=1, padding_pt=1):
    """Apply a bottom border to the paragraphs covered by [start, end)."""
    requests.append(
        {
            "updateParagraphStyle": {
                "range": {
                    "startIndex": start,
                    "endIndex": end,
                },
                "paragraphStyle": {
                    "borderBottom": {
                        "color": {"color": {"rgbColor": {"red": 0, "green": 0, "blue": 0}}},
                        "width": {"magnitude": width_pt, "unit": "PT"},
                        "padding": {"magnitude": padding_pt, "unit": "PT"},
                        "dashStyle": "SOLID",
                    }
                },
                "fields": "borderBottom",
            }
        }
    )


def apply_bullets(requests, start, end):
    """Apply bullet formatting to all paragraphs in [start, end) and remove indent."""
    requests.append(
        {
            "createParagraphBullets": {
                "range": {
                    "startIndex": start,
                    "endIndex": end,
                },
                "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
            }
        }
    )
    requests.append(
        {
            "updateParagraphStyle": {
                "range": {
                    "startIndex": start,
                    "endIndex": end,
                },
                "paragraphStyle": {
                    "indentStart": {"magnitude": 0, "unit": "PT"},
                    "indentFirstLine": {"magnitude": -6, "unit": "PT"},
                },
                "fields": "indentStart,indentFirstLine",
            }
        }
    )


def append_text(requests, index, text):
    requests.append(
        {
            "insertText": {
                "location": {"index": index},
                "text": text,
            }
        }
    )
    start = index
    end = index + len(text)
    return start, end, end


def add_text_style(requests, start, end, *, bold=False, font_size=BODY_FONT_SIZE, font_family=BODY_FONT_FAMILY):
    requests.append(
        {
            "updateTextStyle": {
                "range": {
                    "startIndex": start,
                    "endIndex": end,
                },
                "textStyle": {
                    "bold": bold,
                    "fontSize": {
                        "magnitude": font_size,
                        "unit": "PT",
                    },
                    "weightedFontFamily": {
                        "fontFamily": font_family,
                    },
                },
                "fields": "bold,fontSize,weightedFontFamily",
            }
        }
    )


def insert_personal_info(requests, start_index):
    """Insert name, email, phone, address, and GitHub link."""
    index = start_index

    # Insert name
    name_line = f"{FULL_NAME}\n"
    name_start, name_end, index = append_text(requests, index, name_line)
    add_text_style(
        requests,
        name_start,
        name_end,
        bold=True,
        font_size=16,
        font_family=BODY_FONT_FAMILY,
    )

    # Insert contact info line (single insert to simplify styling + link range)
    contact_prefix = f"{EMAIL} | {PHONE} | {ADDRESS} | "
    contact_line = f"{contact_prefix}{GITHUB}\n"
    contact_start, contact_end, index = append_text(requests, index, contact_line)
    add_text_style(
        requests,
        contact_start,
        contact_end,
        font_size=BODY_FONT_SIZE,
        font_family=BODY_FONT_FAMILY,
    )
    add_paragraph_border_bottom(requests, contact_start, contact_end)
    github_start = contact_start + len(contact_prefix)
    github_end = github_start + len(GITHUB)
    insert_link(requests, github_start, github_end, GITHUB_URL)

    # Add spacing after personal info
    index = append_text(requests, index, "\n")[2]

    return index


def insert_education_section(requests, start_index):
    index = start_index

    header_start, header_end, index = append_text(requests, index, "EDUCATION\n")
    add_text_style(
        requests,
        header_start,
        header_end,
        bold=True,
        font_size=HEADER_FONT_SIZE,
        font_family=HEADER_FONT_FAMILY,
    )
    add_paragraph_border_bottom(requests, header_start, header_end)

    education_text = (
        f"{UNIVERSITY}\n"
        f"{DEGREE}, {FIELD}\n"
        f"{TIME_PERIOD}\n"
        f"GPA: {GPA}\n\n"
    )
    body_start, body_end, index = append_text(requests, index, education_text)
    add_text_style(requests, body_start, body_end)

    return index


def insert_technical_projects_section(requests, start_index):
    index = start_index

    header_start, header_end, index = append_text(requests, index, "TECHNICAL PROJECTS\n")
    add_text_style(
        requests,
        header_start,
        header_end,
        bold=True,
        font_size=HEADER_FONT_SIZE,
        font_family=HEADER_FONT_FAMILY,
    )
    add_paragraph_border_bottom(requests, header_start, header_end)

    return index


def insert_sample_project(requests, start_index):
    index = start_index

    title_line = f"{SAMPLE_PROJECT_TITLE} | {SAMPLE_PROJECT_DATE}\n"
    title_start, title_end, index = append_text(requests, index, title_line)
    add_text_style(requests, title_start, title_end, bold=True)

    stack_line = f"Tech Stack: {SAMPLE_PROJECT_STACK}\n"
    stack_start, stack_end, index = append_text(requests, index, stack_line)
    add_text_style(requests, stack_start, stack_end)

    # Insert bullets, style them, then apply real Docs bullet formatting
    bullet_block_start = None
    bullet_block_end = None
    for bullet in SAMPLE_PROJECT_BULLETS:
        bullet_text = bullet + "\n"
        bullet_start, bullet_end, index = append_text(requests, index, bullet_text)
        add_text_style(
            requests,
            bullet_start,
            bullet_end,
            font_size=BODY_FONT_SIZE,
            font_family=BODY_FONT_FAMILY,
        )
        if bullet_block_start is None:
            bullet_block_start = bullet_start
        bullet_block_end = bullet_end

    if bullet_block_start is not None and bullet_block_end is not None:
        apply_bullets(requests, bullet_block_start, bullet_block_end)

    # Add spacing after project
    index = append_text(requests, index, "\n")[2]

    return index


def insert_skills_section(requests, start_index):
    index = start_index

    header_start, header_end, index = append_text(requests, index, "SKILLS\n")
    add_text_style(
        requests,
        header_start,
        header_end,
        bold=True,
        font_size=HEADER_FONT_SIZE,
        font_family=HEADER_FONT_FAMILY,
    )
    add_paragraph_border_bottom(requests, header_start, header_end)

    skills_text = (
        f"Languages: {SKILLS_LANGUAGES}\n"
        f"Frameworks: {SKILLS_FRAMEWORKS}\n"
        f"Tools: {SKILLS_TOOLS}\n"
    )
    skills_start, skills_end, index = append_text(requests, index, skills_text)
    add_text_style(requests, skills_start, skills_end)

    return index


def main():
    creds = get_credentials()
    service = build("docs", "v1", credentials=creds)
    requests = []

    index = get_append_index(service, DOCUMENT_ID)
    index = insert_personal_info(requests, index)
    index = insert_education_section(requests, index)
    index = insert_technical_projects_section(requests, index)
    index = insert_sample_project(requests, index)
    insert_skills_section(requests, index)

    result = (
        service.documents()
        .batchUpdate(documentId=DOCUMENT_ID, body={"requests": requests})
        .execute()
    )
    print("Inserted sections: PERSONAL INFO, EDUCATION, TECHNICAL PROJECTS, SAMPLE PROJECT, SKILLS")
    print(f"Request count: {len(requests)}")
    print(result)


if __name__ == "__main__":
    main()
