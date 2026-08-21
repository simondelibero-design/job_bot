"""Parses the structured resume markdown (this project's own format — see
DeLibero_Resume_*.md) into fields ATS handlers need to fill application
forms: name, contact info, and categorized skills.
"""
import re
from pathlib import Path


def parse_resume(md_path: str | Path) -> dict:
    md_path = Path(md_path)
    lines = md_path.read_text().splitlines()
    body_lines = [l for l in lines if l.strip() != ""]

    name_line = body_lines[0].strip()
    contact_line = body_lines[1].strip()

    name_parts = name_line.split()
    first_name = name_parts[0] if name_parts else ""
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", contact_line)
    phone_match = re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", contact_line)
    linkedin_match = re.search(r"linkedin\.com/in/[\w-]+", contact_line, re.I)
    location_match = contact_line.split("||")[0].strip() if "||" in contact_line else None

    skills = {}
    in_skills = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_skills = stripped[3:].strip().lower() == "skills"
            continue
        if in_skills and stripped.startswith("**"):
            m = re.match(r"\*\*(.+?):\*\*\s*(.+)", stripped)
            if m:
                category, items = m.groups()
                # split on commas outside parentheses, so "Welding (MIG, TIG,
                # soldering)" stays one item instead of splitting on its
                # internal commas
                parts = re.split(r",\s*(?![^(]*\))", items)
                skills[category.strip()] = [p.strip() for p in parts]

    resume_pdf = md_path.with_suffix(".pdf")

    return {
        "full_name": name_line,
        "first_name": first_name,
        "last_name": last_name,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
        "linkedin_url": f"https://{linkedin_match.group(0)}" if linkedin_match else None,
        "location": location_match,
        "skills": skills,
        "resume_pdf_path": str(resume_pdf) if resume_pdf.exists() else None,
        "resume_md_path": str(md_path),
    }


if __name__ == "__main__":
    import json
    import sys

    here = Path(__file__).parent
    target = sys.argv[1] if len(sys.argv) > 1 else str(here / "DeLibero_Resume_formal.md")
    print(json.dumps(parse_resume(target), indent=2))
