import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from .database import SessionLocal
from .models import Application, ApplicationAction, ApplicationEvent, CandidateProfile, CandidateSkill, Job, Notification, User
from .security import password_hash
from .services.jobs import ingest_local_job

DEMO_EMAIL = "candidate@example.com"

SAMPLE_JOBS = (
    {
        "title": "Product Designer",
        "company": "Northstar Labs",
        "location": "Remote",
        "employment_type": "Full-time",
        "experience": "3+ years",
        "salary_range": "$110k–$145k",
        "skills": "Figma, product design, research",
        "description": "Shape clear, thoughtful product experiences with a collaborative design and engineering team. Lead discovery, prototypes, and product design from early ideas to launch.",
    },
    {
        "title": "Senior Python Engineer",
        "company": "Orbit Systems",
        "location": "New York, NY",
        "employment_type": "Full-time",
        "experience": "5+ years",
        "salary_range": "$145k–$185k",
        "skills": "Python, FastAPI, PostgreSQL, AWS",
        "description": "Build reliable services that power our customer platform. Work across API design, data systems, and cloud infrastructure alongside a pragmatic, supportive team.",
    },
    {
        "title": "People Operations Associate",
        "company": "Fable",
        "location": "Hybrid · Austin, TX",
        "employment_type": "Full-time",
        "experience": "1–3 years",
        "salary_range": "$65k–$82k",
        "skills": "People operations, communication, HRIS",
        "description": "Help create an excellent employee experience as we grow. Partner with teammates across recruiting, onboarding, people programs, and daily operations.",
    },
    {
        "title": "Frontend Engineer",
        "company": "Brightside",
        "location": "Remote",
        "employment_type": "Full-time",
        "experience": "3+ years",
        "salary_range": "$120k–$155k",
        "skills": "React, TypeScript, accessibility, CSS",
        "description": "Build polished, accessible interfaces for products used by thousands of people. Collaborate closely with design and product from idea through launch.",
    },
    {
        "title": "Data Analyst",
        "company": "Metricly",
        "location": "Hybrid · Chicago, IL",
        "employment_type": "Full-time",
        "experience": "2+ years",
        "salary_range": "$85k–$110k",
        "skills": "SQL, Python, Tableau, analytics",
        "description": "Turn product and business data into clear recommendations. Partner with teams to define metrics, build dashboards, and share insights.",
    },
    {
        "title": "Marketing Manager",
        "company": "Goodwell",
        "location": "Remote",
        "employment_type": "Full-time",
        "experience": "4+ years",
        "salary_range": "$95k–$125k",
        "skills": "Content strategy, SEO, campaign management",
        "description": "Lead integrated campaigns that make useful products easier to discover. Own planning, creative collaboration, and performance reporting.",
    },
    {
        "title": "UX Researcher",
        "company": "Fieldnote",
        "location": "Hybrid · Seattle, WA",
        "employment_type": "Full-time",
        "experience": "3+ years",
        "salary_range": "$105k–$135k",
        "skills": "User research, interviews, usability testing",
        "description": "Bring customer perspectives into every stage of product development through thoughtful research, synthesis, and clear storytelling.",
    },
    {
        "title": "DevOps Engineer",
        "company": "Cloudcraft",
        "location": "Remote",
        "employment_type": "Full-time",
        "experience": "4+ years",
        "salary_range": "$130k–$170k",
        "skills": "AWS, Kubernetes, Terraform, CI/CD",
        "description": "Make our cloud platform more reliable and easier to operate. Improve deployment workflows and partner with engineers on resilient systems.",
    },
    {
        "title": "Product Manager",
        "company": "Commonplace",
        "location": "New York, NY",
        "employment_type": "Full-time",
        "experience": "4+ years",
        "salary_range": "$125k–$160k",
        "skills": "Product strategy, roadmaps, user research",
        "description": "Set direction for a customer-facing product area and help a cross-functional team deliver the most valuable improvements.",
    },
    {
        "title": "Customer Success Manager",
        "company": "Relay",
        "location": "Remote",
        "employment_type": "Full-time",
        "experience": "2+ years",
        "salary_range": "$75k–$100k",
        "skills": "Customer success, communication, SaaS",
        "description": "Help customers get lasting value from our platform through thoughtful onboarding, proactive support, and strong relationships.",
    },
    {
        "title": "Cybersecurity Analyst",
        "company": "Redwood Security",
        "location": "Hybrid · Washington, DC",
        "employment_type": "Full-time",
        "experience": "3+ years",
        "salary_range": "$105k–$140k",
        "skills": "Security analysis, SIEM, incident response",
        "description": "Monitor and strengthen security across our services. Investigate alerts, communicate findings, and help teams improve their security practices.",
    },
    {
        "title": "Business Analyst",
        "company": "Civic Bridge",
        "location": "Hybrid · Denver, CO",
        "employment_type": "Full-time",
        "experience": "2+ years",
        "salary_range": "$80k–$105k",
        "skills": "Business analysis, Excel, SQL, documentation",
        "description": "Connect business needs to practical solutions. Gather requirements, map processes, and work with delivery teams to measure results.",
    },
    {
        "title": "QA Automation Engineer",
        "company": "Orbit Systems",
        "location": "Remote",
        "employment_type": "Full-time",
        "experience": "3+ years",
        "salary_range": "$110k–$145k",
        "skills": "Playwright, Python, test automation, APIs",
        "description": "Build dependable automated tests and work with engineers to catch issues early. Improve quality practices across web and API releases.",
    },
    {
        "title": "Content Strategist",
        "company": "Goodwell",
        "location": "Remote",
        "employment_type": "Contract",
        "experience": "3+ years",
        "salary_range": "$55–$75 / hour",
        "skills": "Writing, editorial strategy, SEO, research",
        "description": "Plan and create clear, useful content across our customer journey. Bring a strong editorial eye and a practical approach to measurement.",
    },
    {
        "title": "Financial Analyst",
        "company": "Evergreen Finance",
        "location": "Hybrid · Boston, MA",
        "employment_type": "Full-time",
        "experience": "2+ years",
        "salary_range": "$80k–$108k",
        "skills": "Financial modeling, Excel, forecasting",
        "description": "Support planning and decision-making with accurate forecasts, thoughtful analysis, and clear reporting for business partners.",
    },
    {
        "title": "Backend Engineer",
        "company": "Northstar Labs",
        "location": "Remote",
        "employment_type": "Full-time",
        "experience": "3+ years",
        "salary_range": "$125k–$165k",
        "skills": "Python, PostgreSQL, REST APIs, Docker",
        "description": "Design and operate backend services that support a growing product. Contribute to API design, data modeling, and system reliability.",
    },
    {
        "title": "Sales Development Representative",
        "company": "Layerworks",
        "location": "Hybrid · Austin, TX",
        "employment_type": "Full-time",
        "experience": "1+ years",
        "salary_range": "$60k–$85k",
        "skills": "Sales, prospecting, communication, CRM",
        "description": "Start conversations with teams who can benefit from our tools. Learn our market, build relationships, and grow with a supportive sales team.",
    },
    {
        "title": "Graphic Designer",
        "company": "Fable",
        "location": "Remote",
        "employment_type": "Part-time",
        "experience": "2+ years",
        "salary_range": "$45–$65 / hour",
        "skills": "Visual design, Figma, Adobe Creative Suite",
        "description": "Create a cohesive visual identity across digital campaigns and product launches. Bring strong craft and curiosity to a collaborative team.",
    },
    {
        "title": "Data Scientist",
        "company": "Metricly",
        "location": "Hybrid · San Francisco, CA",
        "employment_type": "Full-time",
        "experience": "4+ years",
        "salary_range": "$145k–$190k",
        "skills": "Python, machine learning, statistics, SQL",
        "description": "Use experimentation and predictive modeling to solve meaningful customer problems. Partner with product and engineering to put insights into action.",
    },
    {
        "title": "HR Generalist",
        "company": "Brightside",
        "location": "Hybrid · Austin, TX",
        "employment_type": "Full-time",
        "experience": "2+ years",
        "salary_range": "$70k–$92k",
        "skills": "HR, employee relations, onboarding, HRIS",
        "description": "Support people programs across the employee journey, from onboarding to development. Help make our workplace welcoming and effective.",
    },
    {
        "title": "Mobile Developer",
        "company": "Relay",
        "location": "Remote",
        "employment_type": "Full-time",
        "experience": "3+ years",
        "salary_range": "$120k–$158k",
        "skills": "React Native, TypeScript, mobile development",
        "description": "Build intuitive mobile experiences for iOS and Android. Work with design and backend partners to deliver reliable features to customers.",
    },
    {
        "title": "Project Manager",
        "company": "Civic Bridge",
        "location": "Hybrid · Portland, OR",
        "employment_type": "Contract",
        "experience": "3+ years",
        "salary_range": "$90k–$120k",
        "skills": "Project management, Agile, stakeholder communication",
        "description": "Guide cross-functional projects from kickoff to delivery. Keep teams aligned, surface risks early, and make progress visible.",
    },
    {
        "title": "Technical Writer",
        "company": "Cloudcraft",
        "location": "Remote",
        "employment_type": "Full-time",
        "experience": "2+ years",
        "salary_range": "$85k–$115k",
        "skills": "Technical writing, APIs, documentation, Git",
        "description": "Make technical concepts easy to understand. Create and maintain developer guides, API references, and product documentation.",
    },
    {
        "title": "Cloud Architect",
        "company": "Redwood Security",
        "location": "Remote",
        "employment_type": "Full-time",
        "experience": "7+ years",
        "salary_range": "$160k–$210k",
        "skills": "AWS, cloud architecture, security, Terraform",
        "description": "Shape secure, scalable cloud architecture and guide teams through thoughtful technical decisions across our platform.",
    },
    {
        "title": "Operations Coordinator",
        "company": "Venture & Co.",
        "location": "Hybrid · Chicago, IL",
        "employment_type": "Full-time",
        "experience": "1–3 years",
        "salary_range": "$58k–$76k",
        "skills": "Operations, organization, communication, Excel",
        "description": "Keep day-to-day operations running smoothly and help improve the systems that support our growing team.",
    },
    {
        "title": "Software Engineering Intern",
        "company": "Northstar Labs",
        "location": "Hybrid · New York, NY",
        "employment_type": "Internship",
        "experience": "Entry-level",
        "salary_range": "$35–$45 / hour",
        "skills": "Python, JavaScript, Git, problem solving",
        "description": "Work with experienced engineers on real product projects, build your technical skills, and learn how a collaborative team ships software.",
    },
    {
        "title": "Account Executive",
        "company": "Layerworks",
        "location": "Hybrid · Seattle, WA",
        "employment_type": "Full-time",
        "experience": "3+ years",
        "salary_range": "$100k–$150k OTE",
        "skills": "Account management, SaaS sales, negotiation",
        "description": "Build trusted customer relationships and help growing teams find the right solution. Own the sales cycle with support from a thoughtful team.",
    },
)

def main():
    password = os.getenv("DEMO_PASSWORD", "")
    if len(password) < 12:
        raise RuntimeError("Set DEMO_PASSWORD to at least 12 characters before creating demo accounts")
    with SessionLocal() as db:
        candidate = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if not candidate:
            candidate = User(email=DEMO_EMAIL, password_hash=password_hash.hash(password))
            candidate.profile = CandidateProfile(full_name="Demo Candidate", location="Remote", skills="Python, Figma, communication")
            db.add(candidate)
            db.flush()
        else:
            candidate.password_hash = password_hash.hash(password)
            candidate.is_active = True
        if candidate.profile:
            existing_skills = {item.name.casefold() for item in candidate.profile.skill_items}
            for skill in ("Python", "Figma", "communication"):
                if skill.casefold() not in existing_skills:
                    candidate.profile.skill_items.append(CandidateSkill(name=skill))
        for listing in SAMPLE_JOBS:
            ingest_local_job(db, listing, source="local-sample")
        if candidate:
            sample_statuses = {
                "Northstar Labs": ("Applied", "Under Review", "Shortlisted", "Interview Scheduled", "Selected"),
                "Orbit Systems": ("Applied", "Under Review", "Rejected"),
                "Fable": ("Applied", "Under Review", "Shortlisted", "Interview Scheduled"),
            }
            for company, statuses in sample_statuses.items():
                sample_job = db.scalar(select(Job).where(Job.company == company))
                if not sample_job:
                    continue
                existing_application = db.scalar(select(Application).where(
                    Application.candidate_id == candidate.id,
                    Application.job_id == sample_job.id,
                ))
                if existing_application:
                    application = existing_application
                else:
                    created_at = datetime.now(timezone.utc) - timedelta(days=len(statuses) - 1)
                    application = Application(
                        candidate_id=candidate.id,
                        job_id=sample_job.id,
                        status=statuses[-1],
                        created_at=created_at,
                        candidate_email=candidate.email,
                    )
                    db.add(application)
                    db.flush()
                    for index, status in enumerate(statuses):
                        db.add(ApplicationEvent(
                            application_id=application.id,
                            actor_id=candidate.id,
                            status=status,
                            created_at=created_at + timedelta(days=index),
                        ))
                    db.add(Notification(
                        user_id=candidate.id,
                        message=f"Your application for {sample_job.title} is now {statuses[-1]}.",
                        created_at=created_at + timedelta(days=len(statuses) - 1),
                    ))
                action_type = "interview" if application.status == "Interview Scheduled" else "offer" if application.status == "Selected" else ""
                existing_action = db.scalar(select(ApplicationAction).where(
                    ApplicationAction.application_id == application.id,
                    ApplicationAction.action_type == action_type,
                )) if action_type else None
                if action_type and not existing_action:
                    db.add(ApplicationAction(
                        application_id=application.id,
                        action_type=action_type,
                        meeting_url=("https://meet.example.com/mock-interview" if action_type == "interview" else ""),
                        details=("Select a time for your interview." if action_type == "interview"
                                 else "Your application has a new offer ready to review."),
                    ))
                elif action_type == "interview" and existing_action and not existing_action.meeting_url:
                    existing_action.meeting_url = "https://meet.example.com/mock-interview"
        db.commit()
    print("Candidate demo account, sample job listings, and a sample application are ready.")

if __name__ == "__main__":
    main()
