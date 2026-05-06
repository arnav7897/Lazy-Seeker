"""
Resume Tailor Service — Generates a tailored resume JSON and exports it as PDF.

Flow:
  1. GeminiService produces structured tailored_resume dict
  2. Jinja2 renders it into ATS-safe HTML
  3. WeasyPrint converts HTML → PDF
  4. PDF saved to outputs/{user_id}/{job_id}/resume.pdf
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from jinja2 import Environment, BaseLoader

from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

OUTPUTS_DIR = Path(__file__).resolve().parents[2] / "outputs"

# ── ATS-safe single-column resume template ────────────────────────────────────
RESUME_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Arial', sans-serif;
    font-size: 11pt;
    color: #1a1a1a;
    line-height: 1.5;
    padding: 32px 40px;
  }
  h1 { font-size: 18pt; font-weight: bold; margin-bottom: 2px; }
  .contact { font-size: 10pt; color: #444; margin-bottom: 16px; }
  h2 {
    font-size: 12pt;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid #333;
    margin: 14px 0 6px;
    padding-bottom: 2px;
  }
  .summary { margin-bottom: 8px; }
  .skills { margin-bottom: 8px; }
  .skills span { margin-right: 6px; }
  .job { margin-bottom: 10px; }
  .job-header { display: flex; justify-content: space-between; }
  .job-title { font-weight: bold; }
  .job-dates { font-size: 10pt; color: #555; }
  ul { padding-left: 18px; }
  li { margin-bottom: 2px; }
  .project { margin-bottom: 8px; }
  .project-title { font-weight: bold; }
</style>
</head>
<body>

<h1>{{ name }}</h1>
<div class="contact">
  {{ email }} | {{ phone }} | {{ location }}
  {% if linkedin %} | {{ linkedin }}{% endif %}
  {% if github %} | {{ github }}{% endif %}
</div>

{% if summary %}
<h2>Summary</h2>
<div class="summary">{{ summary }}</div>
{% endif %}

{% if top_skills %}
<h2>Skills</h2>
<div class="skills">
  {% for skill in top_skills %}<span>{{ skill }}{% if not loop.last %} ·{% endif %}</span>{% endfor %}
</div>
{% endif %}

{% if tailored_bullets %}
<h2>Experience</h2>
{% for job in tailored_bullets %}
<div class="job">
  <div class="job-header">
    <span class="job-title">{{ job.title }} — {{ job.company }}</span>
  </div>
  <ul>
    {% for bullet in job.bullets %}<li>{{ bullet }}</li>{% endfor %}
  </ul>
</div>
{% endfor %}
{% endif %}

{% if selected_projects %}
<h2>Projects</h2>
{% for proj in selected_projects %}
<div class="project">
  <div class="project-title">{{ proj.title }}
    {% if proj.tech_stack %} · <em>{{ proj.tech_stack | join(', ') }}</em>{% endif %}
  </div>
  <div>{{ proj.summary }}</div>
  {% if proj.result %}<div>{{ proj.result }}</div>{% endif %}
</div>
{% endfor %}
{% endif %}

{% if education %}
<h2>Education</h2>
{% for edu in education %}
<div>
  <strong>{{ edu.degree }} in {{ edu.field }}</strong> — {{ edu.institution }}
  {% if edu.graduation_year %}({{ edu.graduation_year }}){% endif %}
  {% if edu.gpa %} · GPA: {{ edu.gpa }}{% endif %}
</div>
{% endfor %}
{% endif %}

</body>
</html>
"""

_jinja_env = Environment(loader=BaseLoader())


class ResumeTailorService:

    async def tailor(
        self,
        profile: dict,
        projects: list[dict],
        education: list[dict],
        parsed_jd: dict,
    ) -> dict:
        """Call Gemini to produce a tailored resume dict."""
        return await gemini_service.tailor_resume(profile, projects, parsed_jd)

    def render_html(
        self,
        tailored: dict,
        profile: dict,
        education: list[dict],
    ) -> str:
        """Render the tailored resume dict into ATS-safe HTML."""
        location_parts = filter(None, [
            profile.get("city"), profile.get("state"), profile.get("country")
        ])
        template = _jinja_env.from_string(RESUME_HTML_TEMPLATE)
        return template.render(
            name=profile.get("name", "Candidate"),
            email=profile.get("email", ""),
            phone=profile.get("phone", ""),
            location=", ".join(location_parts),
            linkedin=profile.get("linkedin_url", ""),
            github=profile.get("github_url", ""),
            summary=tailored.get("summary", ""),
            top_skills=tailored.get("top_skills", []),
            tailored_bullets=tailored.get("tailored_bullets", []),
            selected_projects=tailored.get("selected_projects", []),
            education=education,
        )

    def export_pdf(self, html: str, user_id: str, job_id: str) -> Path:
        """
        Convert HTML to PDF with WeasyPrint.
        Returns the path to the saved PDF.
        """
        try:
            from weasyprint import HTML as WeasyprintHTML
        except ImportError:
            raise RuntimeError("WeasyPrint not installed. Run: pip install weasyprint")

        out_dir = OUTPUTS_DIR / user_id / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / "resume.pdf"

        WeasyprintHTML(string=html).write_pdf(str(pdf_path))
        logger.info("PDF exported to %s", pdf_path)
        return pdf_path

    async def tailor_and_export(
        self,
        profile: dict,
        projects: list[dict],
        education: list[dict],
        parsed_jd: dict,
        user_id: str,
        job_id: str,
    ) -> dict:
        """Full pipeline: Gemini tailor → HTML render → PDF export."""
        tailored = await self.tailor(profile, projects, education, parsed_jd)
        html = self.render_html(tailored, profile, education)
        pdf_path = self.export_pdf(html, user_id, job_id)
        return {
            **tailored,
            "pdf_path": str(pdf_path),
            "html": html,
        }


resume_tailor_service = ResumeTailorService()
