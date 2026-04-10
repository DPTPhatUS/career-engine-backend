from app.schemas.resume import ResumePayload

HEADER_FONT_SIZE = 12
BODY_FONT_SIZE = 12
SPACER_FONT_SIZE = 10
HEADER_FONT_FAMILY = "Garamond"
BODY_FONT_FAMILY = "Garamond"


def insert_link(requests: list[dict], start: int, end: int, url: str) -> None:
    requests.append(
        {
            "updateTextStyle": {
                "range": {
                    "startIndex": start,
                    "endIndex": end,
                },
                "textStyle": {"link": {"url": url}},
                "fields": "link",
            }
        }
    )


def add_paragraph_border_bottom(
    requests: list[dict],
    start: int,
    end: int,
    *,
    width_pt: int = 1,
    padding_pt: int = 1,
) -> None:
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


def apply_bullets(requests: list[dict], start: int, end: int) -> None:
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
                    "indentStart": {"magnitude": 18, "unit": "PT"},
                    "indentFirstLine": {"magnitude": 0, "unit": "PT"},
                },
                "fields": "indentStart,indentFirstLine",
            }
        }
    )


def append_text(requests: list[dict], index: int, text: str) -> tuple[int, int, int]:
    requests.append({"insertText": {"location": {"index": index}, "text": text}})
    start = index
    end = index + len(text)
    return start, end, end


def add_text_style(
    requests: list[dict],
    start: int,
    end: int,
    *,
    bold: bool = False,
    font_size: int = BODY_FONT_SIZE,
    font_family: str = BODY_FONT_FAMILY,
) -> None:
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
                    "weightedFontFamily": {"fontFamily": font_family},
                },
                "fields": "bold,fontSize,weightedFontFamily",
            }
        }
    )


def add_bold(requests: list[dict], start: int, end: int) -> None:
    requests.append(
        {
            "updateTextStyle": {
                "range": {
                    "startIndex": start,
                    "endIndex": end,
                },
                "textStyle": {"bold": True},
                "fields": "bold",
            }
        }
    )


def add_italic(requests: list[dict], start: int, end: int) -> None:
    requests.append(
        {
            "updateTextStyle": {
                "range": {
                    "startIndex": start,
                    "endIndex": end,
                },
                "textStyle": {"italic": True},
                "fields": "italic",
            }
        }
    )


def append_spacer_line(requests: list[dict], index: int) -> int:
    spacer_start, spacer_end, index = append_text(requests, index, "\n")
    add_text_style(
        requests,
        spacer_start,
        spacer_end,
        font_size=SPACER_FONT_SIZE,
        font_family=BODY_FONT_FAMILY,
    )
    return index


def insert_personal_info(requests: list[dict], start_index: int, payload: ResumePayload) -> int:
    index = start_index
    personal = payload.personal_info

    name_line = f"{personal.full_name}\n"
    name_start, name_end, index = append_text(requests, index, name_line)
    add_text_style(requests, name_start, name_end, bold=True, font_size=24, font_family=BODY_FONT_FAMILY)

    github_label = personal.github_label or "GitHub"
    contact_prefix = f"{personal.email} | {personal.phone} | {personal.address}"
    if personal.github_url:
        contact_prefix = f"{contact_prefix} | "
        contact_line = f"{contact_prefix}{github_label}\n"
    else:
        contact_line = f"{contact_prefix}\n"

    contact_start, contact_end, index = append_text(requests, index, contact_line)
    add_text_style(requests, contact_start, contact_end, font_size=16, font_family=BODY_FONT_FAMILY)
    add_paragraph_border_bottom(requests, contact_start, contact_end)

    if personal.github_url:
        github_start = contact_start + len(contact_prefix)
        github_end = github_start + len(github_label)
        insert_link(requests, github_start, github_end, str(personal.github_url))

    return append_spacer_line(requests, index)


def insert_education_section(requests: list[dict], start_index: int, payload: ResumePayload) -> int:
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

    for item in payload.education:
        line_1 = f"{item.university} | {item.time_period}\n"
        line_1_start, line_1_end, index = append_text(requests, index, line_1)
        add_text_style(requests, line_1_start, line_1_end)
        add_bold(requests, line_1_start, line_1_end - 1)

        location = item.location or ""
        sep = " | " if location else ""
        line_2 = f"{item.degree}, {item.field}{sep}{location}\n"
        line_2_start, line_2_end, index = append_text(requests, index, line_2)
        add_text_style(requests, line_2_start, line_2_end)
        add_italic(requests, line_2_start, line_2_end - 1)

        bullet_start = None
        bullet_end = None

        if item.gpa:
            gpa_line = f"GPA: {item.gpa}\n"
            gpa_start, gpa_end, index = append_text(requests, index, gpa_line)
            add_text_style(requests, gpa_start, gpa_end)
            add_bold(requests, gpa_start, gpa_end - 1)
            bullet_start = gpa_start
            bullet_end = gpa_end

        if item.relevant_coursework:
            coursework_line = f"Relevant Coursework: {item.relevant_coursework}\n"
            c_start, c_end, index = append_text(requests, index, coursework_line)
            add_text_style(requests, c_start, c_end)
            add_bold(requests, c_start, c_start + len("Relevant Coursework:"))
            if bullet_start is None:
                bullet_start = c_start
            bullet_end = c_end

        if bullet_start is not None and bullet_end is not None:
            apply_bullets(requests, bullet_start, bullet_end)

    return append_spacer_line(requests, index)


def insert_projects_section(requests: list[dict], start_index: int, payload: ResumePayload) -> int:
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

    for project in payload.projects:
        title_line = f"{project.title} | {project.date_range}\n"
        title_start, title_end, index = append_text(requests, index, title_line)
        add_text_style(requests, title_start, title_end, bold=True)

        if project.github_url:
            insert_link(requests, title_start, title_start + len(project.title), str(project.github_url))

        if project.tech_stack:
            stack_line = f"Tech Stack: {project.tech_stack}\n"
            stack_start, stack_end, index = append_text(requests, index, stack_line)
            add_text_style(requests, stack_start, stack_end)

        bullet_block_start = None
        bullet_block_end = None
        for bullet in project.bullets:
            bullet_text = bullet + "\n"
            bullet_start, bullet_end, index = append_text(requests, index, bullet_text)
            add_text_style(requests, bullet_start, bullet_end)
            if bullet_block_start is None:
                bullet_block_start = bullet_start
            bullet_block_end = bullet_end

        if bullet_block_start is not None and bullet_block_end is not None:
            apply_bullets(requests, bullet_block_start, bullet_block_end)

        index = append_spacer_line(requests, index)

    return index


def insert_skills_section(requests: list[dict], start_index: int, payload: ResumePayload) -> int:
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

    bullet_block_start = None
    bullet_block_end = None
    for item in payload.skills:
        line_text = f"{item.label}: {item.values}\n"
        line_start, line_end, index = append_text(requests, index, line_text)
        add_text_style(requests, line_start, line_end)
        add_bold(requests, line_start, line_start + len(item.label) + 1)

        if bullet_block_start is None:
            bullet_block_start = line_start
        bullet_block_end = line_end

    if bullet_block_start is not None and bullet_block_end is not None:
        apply_bullets(requests, bullet_block_start, bullet_block_end)

    return append_spacer_line(requests, index)


def build_resume_requests(payload: ResumePayload, start_index: int) -> tuple[list[dict], int]:
    requests: list[dict] = [
        {
            "updateDocumentStyle": {
                "documentStyle": {
                    "marginLeft": {"magnitude": 36, "unit": "PT"},
                    "marginRight": {"magnitude": 36, "unit": "PT"},
                    "marginTop": {"magnitude": 32, "unit": "PT"},
                    "marginBottom": {"magnitude": 32, "unit": "PT"},
                },
                "fields": "marginLeft,marginRight,marginTop,marginBottom",
            }
        }
    ]

    index = start_index
    index = insert_personal_info(requests, index, payload)
    index = insert_education_section(requests, index, payload)
    index = insert_projects_section(requests, index, payload)
    index = insert_skills_section(requests, index, payload)
    return requests, index
