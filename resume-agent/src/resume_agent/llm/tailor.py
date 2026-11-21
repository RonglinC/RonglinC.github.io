from __future__ import annotations

from resume_agent.models.job import Job
from resume_agent.models.resume import Resume


def generate_cover_letter(resume: Resume, job: Job, api_key: str | None, model: str) -> str:
    if api_key:
        return _generate_with_openai(resume, job, api_key, model)
    return _generate_template(resume, job)


def _generate_template(resume: Resume, job: Job) -> str:
    skills = resume.skills_text() or "relevant technologies"
    summary = resume.summary or (
        f"I am a {resume.latest_title()} with experience building reliable software."
    )
    return f"""Dear Hiring Manager,

I am writing to express my interest in the {job.title} position at {job.company}.

{summary}

My background includes expertise in {skills}, which aligns well with the requirements for this role. I am excited about the opportunity to contribute to your team and would welcome the chance to discuss how my experience can support {job.company}'s goals.

Thank you for your consideration.

Best regards,
{resume.name}
{resume.email}
"""


def _generate_with_openai(resume: Resume, job: Job, api_key: str, model: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    prompt = f"""Write a concise, professional cover letter (200-300 words) for this job application.

Candidate:
- Name: {resume.name}
- Title: {resume.latest_title()}
- Skills: {resume.skills_text()}
- Summary: {resume.summary or 'N/A'}
- Recent experience: {', '.join(e.title + ' at ' + e.company for e in resume.experience[:2]) or 'N/A'}

Job:
- Title: {job.title}
- Company: {job.company}
- Description excerpt: {(job.description or '')[:1500]}

Requirements:
- Professional tone, no placeholders
- Highlight relevant skills matching the job
- End with candidate name and email
"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You write tailored job application cover letters."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=500,
    )
    return response.choices[0].message.content or _generate_template(resume, job)
