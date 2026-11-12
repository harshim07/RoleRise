import re


SECTION_HEADINGS = {
    "summary", "professional summary", "profile", "professional profile", "objective",
    "career objective", "skills", "technical skills", "core competencies", "technologies",
    "tools", "work experience", "professional experience", "experience", "employment history",
    "education", "education and training", "certifications", "projects", "languages",
}
SKILL_TERMS = (
    "Python", "FastAPI", "PostgreSQL", "AWS", "Figma", "React", "TypeScript", "Accessibility",
    "CSS", "SQL", "Tableau", "Analytics", "SEO", "Content Strategy", "Campaign Management",
    "User Research", "Usability Testing", "Kubernetes", "Terraform", "CI/CD", "Product Strategy",
    "Customer Success", "Communication", "SaaS", "SIEM", "Incident Response", "Business Analysis",
    "Excel", "Playwright", "Test Automation", "REST APIs", "Technical Writing", "Financial Modeling",
    "Forecasting", "CRM", "Adobe Creative Suite", "Machine Learning", "Statistics", "HRIS",
    "React Native", "Mobile Development", "Project Management", "Agile", "Stakeholder Communication",
    "Documentation", "Git", "Docker", "Java", "C++", "Go", "Node.js", "Azure", "GCP",
)


def _section_content(lines: list[str], names: set[str]) -> list[str]:
    for index, line in enumerate(lines):
        heading = line.casefold().rstrip(":").strip()
        if heading in names:
            values = []
            for candidate in lines[index + 1:]:
                if candidate.casefold().rstrip(":").strip() in SECTION_HEADINGS:
                    break
                if candidate:
                    values.append(candidate)
            return values
        match = re.match(r"^([^:]{2,40}):\s*(.+)$", line)
        if match and match.group(1).casefold().strip() in names:
            values = [match.group(2).strip()]
            for candidate in lines[index + 1:]:
                if candidate.casefold().rstrip(":").strip() in SECTION_HEADINGS:
                    break
                if candidate:
                    values.append(candidate)
            return values
    return []


def parse_resume_text(text: str) -> dict[str, str]:
    lines = [
        re.sub(r"\s+", " ", line.strip().lstrip("•*- \t")).strip()
        for line in text.replace("\r", "\n").splitlines()
    ]
    lines = [line for line in lines if line]
    normalized_text = "\n".join(lines)
    email = next(iter(re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", normalized_text)), "")[:255]
    phone = next(iter(re.findall(r"(?<!\w)(?:\+?\d[\d ().-]{7,}\d)(?!\w)", normalized_text)), "")[:40]

    name = ""
    for line in lines[:8]:
        if (2 <= len(line) <= 80 and len(line.split()) <= 6 and "@" not in line
                and not re.search(r"\d{3}", line)
                and line.casefold().rstrip(":") not in (SECTION_HEADINGS | {"resume", "curriculum vitae", "cv"})):
            name = line
            break

    skills_section = _section_content(
        lines, {"skills", "technical skills", "core competencies", "technologies", "tools"}
    )
    skills = []
    for value in skills_section:
        for skill in re.split(r"[,;|•]", value):
            skill = skill.strip(" -\t")[:100]
            if skill and skill.casefold() not in {item.casefold() for item in skills}:
                skills.append(skill)
    if not skills:
        skills = [
            term for term in SKILL_TERMS
            if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized_text, re.IGNORECASE)
        ]

    summary = " ".join(_section_content(
        lines, {"summary", "professional summary", "profile", "professional profile", "objective", "career objective"}
    ))[:5000]
    location_match = re.search(r"(?im)^\s*(?:location|address)\s*:\s*(.+)$", normalized_text)
    return {
        "full_name": name,
        "email": email,
        "phone": phone,
        "location": location_match.group(1).strip()[:160] if location_match else "",
        "summary": summary,
        "skills": ", ".join(skills)[:2000],
    }
