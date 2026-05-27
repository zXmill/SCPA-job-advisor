"""Build hybrid Indonesian profile-job dataset for SCPA (root project).

Reads 539 real Indonesia seed jobs from SCPAv2, generates realistic
academic profiles, and produces 5.000+ labeled pairs in the exact
JSONL format expected by fine_tune_sbert.py and indonesian_dataset.py.

Usage:
    python services/sbert/training/build_hybrid_dataset_scpa.py
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

# Seed data from SCPAv2 (539 real Indonesia jobs)
SEED_FILE = Path(r"E:/TUGAS AKHIR/SCPA/SCPAv2/data/real_jobs/all_indonesia_real_ultraclean.jsonl")

# Output
DEFAULT_OUTPUT = Path("services/sbert/training/data/indonesian_profile_job_pairs_hybrid.jsonl")

# Indonesian academic programs mapped to target roles
PROGRAM_ROLE_MAP: dict[str, list[str]] = {
    "Teknik Informatika": ["Backend Developer", "Frontend Developer", "Fullstack Developer", "Software Engineer", "Web Developer"],
    "Sistem Informasi": ["Data Analyst", "Business Analyst", "System Analyst", "IT Consultant", "BI Analyst"],
    "Sastra Inggris": ["Content Writer", "Translator", "Copywriter", "English Teacher", "Technical Writer"],
    "Manajemen": ["Marketing Specialist", "HR Specialist", "Project Manager", "Operations Manager", "Business Development"],
    "Akuntansi": ["Financial Analyst", "Auditor", "Tax Consultant", "Accounting Staff", "Finance Manager"],
    "Psikologi": ["HR Recruiter", "Counselor", "Organizational Development", "Trainer", "People Analyst"],
    "Desain Komunikasi Visual": ["UI/UX Designer", "Graphic Designer", "Product Designer", "Visual Designer", "Creative Designer"],
    "Teknik Elektro": ["IoT Engineer", "Embedded Systems Engineer", "Electrical Engineer", "Automation Engineer", "Hardware Engineer"],
    "Hukum": ["Legal Officer", "Compliance Officer", "Contract Manager", "Corporate Legal", "Legal Consultant"],
    "Kedokteran": ["Medical Researcher", "Health Data Analyst", "Clinical Researcher", "Medical Writer", "Epidemiologist"],
    "Statistika": ["Data Scientist", "Statistician", "Quantitative Analyst", "Research Analyst", "Analytics Engineer"],
    "Matematika": ["Data Scientist", "Quantitative Analyst", "Actuary", "Algorithm Engineer", "Research Scientist"],
    "Teknik Industri": ["Supply Chain Analyst", "Operations Analyst", "Quality Assurance", "Process Engineer", "Project Coordinator"],
    "Teknik Sipil": ["Project Engineer", "Construction Manager", "Structural Engineer", "Site Engineer", "Quantity Surveyor"],
    "Ilmu Komunikasi": ["Digital Marketing", "Public Relations", "Social Media Manager", "Content Strategist", "Communications Specialist"],
    "Farmasi": ["Pharmacist", "Clinical Research Associate", "Regulatory Affairs", "Quality Control", "Medical Science Liaison"],
    "Teknik Kimia": ["Process Engineer", "Quality Control", "R&D Engineer", "Production Engineer", "Environmental Engineer"],
    "Biologi": ["Biotechnologist", "Research Scientist", "Bioinformatics", "Quality Assurance", "Lab Analyst"],
    "Fisika": ["Data Scientist", "Quantitative Analyst", "Physics Engineer", "Research Scientist", "Simulation Engineer"],
    "Ekonomi": ["Financial Analyst", "Economist", "Market Researcher", "Investment Analyst", "Risk Analyst"],
    "Perhotelan": ["Hotel Manager", "Operations Manager", "Guest Relations", "Event Coordinator", "Revenue Analyst"],
    "Pariwisata": ["Tourism Manager", "Destination Manager", "Event Coordinator", "Marketing Specialist", "Operations Analyst"],
    "Teknik Mesin": ["Mechanical Engineer", "Product Engineer", "Manufacturing Engineer", "Maintenance Engineer", "Design Engineer"],
    "Teknik Komputer": ["Embedded Engineer", "Hardware Engineer", "IoT Developer", "System Engineer", "Firmware Engineer"],
    "Kewirausahaan": ["Business Development", "Startup Founder", "Product Manager", "Strategy Consultant", "Growth Manager"],
    "Teknik Lingkungan": ["Environmental Engineer", "Sustainability Consultant", "Waste Management", "ESG Analyst", "Compliance Officer"],
    "Arsitektur": ["Architect", "Interior Designer", "Urban Planner", "Project Manager", "BIM Specialist"],
    "Teknik Geofisika": ["Geophysicist", "Data Analyst", "Exploration Engineer", "Research Scientist", "Energy Analyst"],
    "Teknik Pertambangan": ["Mining Engineer", "Geotechnical Engineer", "Safety Engineer", "Operations Manager", "Project Engineer"],
    "Keperawatan": ["Nurse", "Healthcare Coordinator", "Clinical Instructor", "Patient Care Manager", "Health Educator"],
    "Teknologi Pangan": ["Food Technologist", "Quality Assurance", "R&D Scientist", "Production Manager", "Regulatory Affairs"],
    "Agribisnis": ["Agricultural Analyst", "Supply Chain Manager", "Business Development", "Operations Manager", "Market Researcher"],
    "Peternakan": ["Animal Scientist", "Livestock Manager", "Quality Control", "Research Associate", "Operations Analyst"],
    "Perikanan": ["Aquaculture Manager", "Fisheries Analyst", "Quality Assurance", "Research Scientist", "Operations Coordinator"],
    "Kehutanan": ["Forestry Manager", "Conservation Analyst", "GIS Specialist", "Research Scientist", "Sustainability Consultant"],
}

# Universities
INDONESIAN_UNIVERSITIES = [
    "Institut Teknologi Bandung", "Universitas Indonesia", "Universitas Gadjah Mada",
    "Universitas Airlangga", "Universitas Padjadjaran", "Universitas Brawijaya",
    "Universitas Diponegoro", "Universitas Hasanuddin", "Universitas Negeri Malang",
    "Universitas Negeri Semarang", "Institut Teknologi Sepuluh Nopember",
    "Universitas Kristen Petra", "Universitas Pelita Harapan", "Universitas Bina Nusantara",
    "Universitas Gunadarma", "Universitas Islam Indonesia", "Universitas Andalas",
    "Universitas Sriwijaya", "Universitas Jember", "Universitas Lampung",
    "Universitas Mulawarman", "Universitas Negeri Makassar", "Universitas Negeri Yogyakarta",
    "Universitas Muhammadiyah Surakarta", "Universitas Islam Negeri Jakarta",
    "Universitas Cenderawasih", "Universitas Mataram", "Universitas Negeri Papua",
    "Universitas Syiah Kuala", "Universitas Riau",
]

# Skill taxonomy
SKILL_PATTERNS: dict[str, list[str]] = {
    "python": ["python"], "java": ["java", "java ee", "j2ee"],
    "javascript": ["javascript", "js", "es6"], "typescript": ["typescript", "ts"],
    "php": ["php", "laravel", "codeigniter"], "golang": ["golang", "go language"],
    "c++": ["c++", "cpp"], "c#": ["c#", "csharp", ".net"],
    "sql": ["sql", "postgresql", "postgres", "mysql", "oracle", "sql server", "mssql"],
    "mongodb": ["mongodb", "mongo db"], "redis": ["redis"],
    "react": ["react", "reactjs", "react.js"], "vue": ["vue", "vuejs", "vue.js"],
    "angular": ["angular"], "next.js": ["next.js", "nextjs"],
    "node.js": ["node.js", "nodejs", "node js"], "django": ["django"],
    "fastapi": ["fastapi", "fast api"], "flask": ["flask"],
    "spring boot": ["spring boot", "springboot"],
    "html": ["html", "html5"], "css": ["css", "css3", "sass", "scss"],
    "bootstrap": ["bootstrap"], "tailwind": ["tailwind css", "tailwindcss"],
    "aws": ["aws", "amazon web services"], "gcp": ["gcp", "google cloud"],
    "azure": ["azure", "microsoft azure"],
    "docker": ["docker", "containerization"], "kubernetes": ["kubernetes", "k8s"],
    "terraform": ["terraform"], "ansible": ["ansible"], "jenkins": ["jenkins"],
    "ci/cd": ["ci/cd", "cicd", "github actions", "gitlab ci"],
    "linux": ["linux", "ubuntu", "centos", "red hat"],
    "git": ["git", "github", "gitlab", "bitbucket"],
    "pandas": ["pandas"], "numpy": ["numpy"],
    "pytorch": ["pytorch", "torch"], "tensorflow": ["tensorflow", "tf", "keras"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikitlearn"],
    "machine learning": ["machine learning", "ml engineer", "ai"],
    "deep learning": ["deep learning", "neural network"],
    "tableau": ["tableau"], "power bi": ["power bi", "powerbi"],
    "looker": ["looker"], "excel": ["excel", "spreadsheet", "pivot table"],
    "etl": ["etl", "elt"], "airflow": ["airflow", "apache airflow"],
    "spark": ["apache spark", "pyspark", "spark"],
    "kafka": ["kafka", "apache kafka"], "hadoop": ["hadoop"],
    "bigquery": ["bigquery"], "data warehouse": ["data warehouse", "data warehousing"],
    "data pipeline": ["data pipeline", "data pipelines"],
    "agile": ["agile"], "scrum": ["scrum"], "jira": ["jira", "confluence"],
    "figma": ["figma"], "sketch": ["sketch"],
    "adobe": ["adobe", "photoshop", "illustrator", "xd"],
    "ui/ux": ["ui/ux", "ui ux", "user interface", "user experience"],
    "rest api": ["rest api", "restful api", "api design"],
    "graphql": ["graphql", "graph ql"], "grpc": ["grpc"],
    "microservices": ["microservices", "micro services"],
    "selenium": ["selenium"], "cypress": ["cypress"], "postman": ["postman"],
    "automation test": ["automation test", "automated testing", "test automation"],
    "manual test": ["manual test", "manual testing"],
    "qa": ["qa", "quality assurance"],
    "penetration testing": ["penetration testing", "pen test", "pentest"],
    "vulnerability": ["vulnerability assessment", "vulnerability scanning"],
    "compliance": ["compliance", "iso 27001", "pci dss", "gdpr", "pdpa"],
    "incident response": ["incident response"],
    "security audit": ["security audit", "audit"],
    "sap": ["sap"], "erp": ["erp", "enterprise resource planning"],
    "crm": ["crm", "salesforce", "dynamics", "hubspot"],
    "flutter": ["flutter"], "react native": ["react native"],
    "android": ["android", "android sdk"], "ios": ["ios", "iphone"],
    "swift": ["swift"], "kotlin": ["kotlin"],
    "network": ["network", "networking", "cisco", "ccna", "ccnp"],
    "firewall": ["firewall"], "vpn": ["vpn"],
    "prometheus": ["prometheus"], "grafana": ["grafana"],
    "elk": ["elk", "elastic stack"],
    "project management": ["project management", "project manager"],
    "stakeholder": ["stakeholder", "stakeholder management"],
    "roadmap": ["roadmap", "product roadmap"],
    "business analysis": ["business analysis", "business analyst"],
    "data analysis": ["data analysis", "data analyst"],
    "accounting": ["accounting", "akuntansi"],
    "finance": ["finance", "financial analysis"],
    "tax": ["tax", "pajak"], "budget": ["budget", "budgeting"],
    "forecasting": ["forecasting", "forecast"],
    "recruitment": ["recruitment", "recruiting", "talent acquisition"],
    "hr": ["hr", "human resources", "people operations"],
    "payroll": ["payroll"],
    "digital marketing": ["digital marketing"],
    "seo": ["seo", "search engine optimization"],
    "sem": ["sem", "search engine marketing"],
    "social media": ["social media", "social media marketing"],
    "google ads": ["google ads", "google adwords"],
    "meta ads": ["meta ads", "facebook ads"],
    "content marketing": ["content marketing"],
    "copywriting": ["copywriting", "copywriter"],
    "content writing": ["content writing"],
    "supply chain": ["supply chain"], "logistics": ["logistics"],
    "procurement": ["procurement"],
    "inventory": ["inventory", "inventory management"],
    "warehouse": ["warehouse"],
    "customer service": ["customer service", "customer support"],
    "helpdesk": ["helpdesk", "help desk"],
    "call center": ["call center"],
    "sales": ["sales", "sales executive"],
    "business development": ["business development", "bizdev"],
    "account management": ["account management", "account manager"],
    "public relations": ["public relations", "pr"],
    "communications": ["communications"],
    "event management": ["event management"],
    "teaching": ["teaching", "teacher", "guru", "pengajar"],
    "education": ["education", "pendidikan"],
    "medical": ["medical", "healthcare"],
    "legal": ["legal", "lawyer", "hukum"],
    "contract": ["contract", "kontrak", "perjanjian"],
    "regulatory": ["regulatory", "regulasi"],
    "english": ["english", "bahasa inggris"],
    "bahasa indonesia": ["bahasa indonesia", "indonesian language"],
    "mandarin": ["mandarin", "bahasa mandarin"],
    "microsoft office": ["microsoft office"],
    "word": ["word", "ms word"],
    "powerpoint": ["powerpoint", "ms powerpoint"],
    "problem solving": ["problem solving", "pemecahan masalah"],
    "critical thinking": ["critical thinking"],
    "communication": ["communication", "komunikasi"],
    "leadership": ["leadership", "kepemimpinan"],
    "teamwork": ["teamwork", "kerja sama", "kolaborasi"],
    "negotiation": ["negotiation", "negosiasi"],
    "presentation": ["presentation", "presentasi"],
    "time management": ["time management", "manajemen waktu"],
    "adaptability": ["adaptability", "adaptasi"],
    "research": ["research", "penelitian"],
    "statistics": ["statistics", "statistik"],
    "r": [" r ", " r,"], "scala": ["scala"],
    "blockchain": ["blockchain", "web3"], "solidity": ["solidity"],
    "iot": ["iot", "internet of things", "embedded"],
    "cad": ["cad", "autocad"], "bim": ["bim"],
    "gis": ["gis", "geographic information"],
}

EDU_PATTERNS = [
    (re.compile(r"\b(s1|sarjana|bachelor|undergraduate|university graduate)\b", re.I), "S1"),
    (re.compile(r"\b(s2|magister|master)\b", re.I), "S2"),
    (re.compile(r"\b(sma|senior high school|high school)\b", re.I), "SMA"),
    (re.compile(r"\b(smk|vocational)\b", re.I), "SMK"),
    (re.compile(r"\bdiploma\b", re.I), "Diploma"),
    (re.compile(r"\b(stpm|pre-university)\b", re.I), "STPM"),
    (re.compile(r"\b(phd|doctor|doktor)\b", re.I), "PhD"),
]

EXP_PATTERN = re.compile(r"(\d+)\+?\s*(?:tahun|years?|thn|pengalaman kerja)", re.IGNORECASE)

random.seed(42)


def _extract_skills(text: str) -> list[str]:
    text_lower = f" {text.lower()} "
    found: list[str] = []
    for skill_name, patterns in SKILL_PATTERNS.items():
        for pattern in patterns:
            if f" {pattern} " in text_lower or f" {pattern}," in text_lower or f" {pattern}." in text_lower:
                found.append(skill_name)
                break
    return found


def _detect_education(text: str) -> str | None:
    for pattern, edu in EDU_PATTERNS:
        if pattern.search(text):
            return edu
    return None


def _detect_experience(text: str) -> str | None:
    matches = EXP_PATTERN.findall(text)
    if matches:
        years = int(matches[0])
        if years <= 1:
            return "fresh graduate / 0-1 tahun"
        elif years <= 3:
            return f"{years} tahun pengalaman"
        elif years <= 5:
            return f"{years} tahun pengalaman"
        else:
            return f"{years}+ tahun pengalaman"
    return None


def _sanitize_text(text: str) -> str:
    """Replace line separator / paragraph separator chars that break JSONL."""
    return text.replace("\u2028", " ").replace("\u2029", " ")


def _load_seed_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with open(SEED_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            skills = _extract_skills(f"{r.get('title', '')} {r.get('description', '')}")
            if not skills:
                continue
            r["_skills"] = skills
            r["_edu"] = _detect_education(r.get("description", ""))
            r["_exp"] = _detect_experience(r.get("description", ""))
            records.append(r)
    return records


def _match_program_to_job(title: str, skills: list[str]) -> tuple[str, str]:
    """Return (program_studi, target_role) best matching a job title+skills."""
    title_lower = title.lower()
    skill_set = set(skills)

    # Programming / IT
    if any(k in title_lower for k in ["backend", "front end", "frontend", "fullstack", "web developer", "software engineer", "programmer", "developer"]):
        return "Teknik Informatika", "Software Developer"
    if any(k in title_lower for k in ["data analyst", "business analyst", "bi analyst", "system analyst"]):
        return "Sistem Informasi", "Data Analyst"
    if any(k in title_lower for k in ["data scientist", "machine learning", "ml engineer", "ai engineer"]):
        return "Statistika", "Data Scientist"
    if any(k in title_lower for k in ["devops", "sre", "cloud engineer", "infrastructure", "platform engineer"]):
        return "Teknik Informatika", "DevOps Engineer"
    if any(k in title_lower for k in ["security analyst", "cybersecurity", "penetration", "vulnerability", "incident response"]):
        return "Teknik Informatika", "Security Analyst"
    if any(k in title_lower for k in ["qa", "quality assurance", "tester", "automation test", "manual test"]):
        return "Teknik Informatika", "QA Engineer"
    if any(k in title_lower for k in ["mobile developer", "android", "ios", "flutter", "react native"]):
        return "Teknik Informatika", "Mobile Developer"
    if any(k in title_lower for k in ["database", "dba", "data engineer", "etl", "data pipeline", "warehouse"]):
        return "Sistem Informasi", "Data Engineer"
    if any(k in title_lower for k in ["ui/ux", "ui ux", "user interface", "user experience", "product designer"]):
        return "Desain Komunikasi Visual", "UI/UX Designer"
    if any(k in title_lower for k in ["graphic designer", "visual designer", "creative designer"]):
        return "Desain Komunikasi Visual", "Graphic Designer"

    # Finance
    if any(k in title_lower for k in ["financial analyst", "finance analyst", "accountant", "accounting", "auditor", "tax", "budget", "treasury", "controller"]):
        return "Akuntansi", "Financial Analyst"

    # HR
    if any(k in title_lower for k in ["hr", "human resources", "recruitment", "recruiter", "talent acquisition", "payroll", "people operations"]):
        return "Psikologi", "HR Specialist"

    # Marketing
    if any(k in title_lower for k in ["marketing", "digital marketing", "seo", "sem", "social media", "content marketing", "branding", "copywriter", "growth"]):
        return "Ilmu Komunikasi", "Marketing Specialist"

    # Sales
    if any(k in title_lower for k in ["sales", "account executive", "business development", "account manager", "sales executive", "sales manager", "key account"]):
        return "Manajemen", "Sales Executive"

    # Operations / Supply Chain
    if any(k in title_lower for k in ["operations", "supply chain", "logistics", "procurement", "inventory", "warehouse", "production", "manufacturing", "quality control", "process engineer"]):
        return "Teknik Industri", "Operations Analyst"

    # Customer Service
    if any(k in title_lower for k in ["customer service", "customer support", "helpdesk", "call center", "technical support", "service desk"]):
        return "Ilmu Komunikasi", "Customer Service"

    # Content / Writing
    if any(k in title_lower for k in ["content writer", "copywriter", "technical writer", "translator", "content strategist", "editor"]):
        return "Sastra Inggris", "Content Writer"

    # Project Management
    if any(k in title_lower for k in ["project manager", "program manager", "scrum master", "project coordinator"]):
        return "Manajemen", "Project Manager"

    # Research / Science
    if any(k in title_lower for k in ["research", "scientist", "r&d", "lab analyst", "research associate", "clinical research"]):
        return "Biologi", "Research Scientist"

    # Legal
    if any(k in title_lower for k in ["legal", "lawyer", "compliance", "contract", "regulatory", "paralegal"]):
        return "Hukum", "Legal Officer"

    # Medical
    if any(k in title_lower for k in ["medical", "healthcare", "nurse", "pharmacist", "clinical", "health data", "epidemiologist"]):
        return "Kedokteran", "Medical Researcher"

    # Engineering
    if any(k in title_lower for k in ["electrical engineer", "electronic", "iot", "embedded", "hardware engineer", "automation"]):
        return "Teknik Elektro", "IoT Engineer"
    if any(k in title_lower for k in ["mechanical engineer", "product engineer", "manufacturing engineer", "maintenance engineer", "design engineer", "cnc", "machinist"]):
        return "Teknik Mesin", "Mechanical Engineer"
    if any(k in title_lower for k in ["civil engineer", "construction manager", "structural engineer", "site engineer", "quantity surveyor", "project engineer"]):
        return "Teknik Sipil", "Civil Engineer"
    if any(k in title_lower for k in ["chemical engineer", "process engineer", "r&d engineer", "production engineer", "environmental engineer"]):
        return "Teknik Kimia", "Process Engineer"

    # Event / PR
    if any(k in title_lower for k in ["event", "public relations", "pr", "communications", "corporate communications", "media relations"]):
        return "Ilmu Komunikasi", "Public Relations"

    # Teaching
    if any(k in title_lower for k in ["teacher", "lecturer", "instructor", "tutor", "guru", "pengajar", "dosen"]):
        return "Pendidikan", "Teacher"

    # Default based on skills
    tech_skills = {"python", "java", "javascript", "sql", "docker", "kubernetes", "aws", "react", "node.js"}
    if skill_set & tech_skills:
        return "Teknik Informatika", "Software Developer"
    data_skills = {"excel", "sql", "tableau", "power bi", "data analysis", "statistics", "pandas"}
    if skill_set & data_skills:
        return "Sistem Informasi", "Data Analyst"
    design_skills = {"figma", "adobe", "ui/ux", "sketch", "photoshop", "illustrator"}
    if skill_set & design_skills:
        return "Desain Komunikasi Visual", "UI/UX Designer"
    business_skills = {"excel", "presentation", "communication", "business analysis", "stakeholder"}
    if skill_set & business_skills:
        return "Manajemen", "Business Analyst"

    return "Teknik Informatika", "Generalist"


def _build_profile_text(program_studi: str, target_role: str, skills: list[str]) -> str:
    parts = [program_studi, target_role]
    parts.extend(skills)
    return " ".join(parts)


def _build_job_text(job: dict[str, Any]) -> str:
    parts = [
        _sanitize_text(str(job.get("title", ""))),
        _sanitize_text(str(job.get("company", ""))),
        _sanitize_text(str(job.get("location", ""))),
        _sanitize_text(str(job.get("description", ""))),
        " ".join(job.get("_skills", [])),
    ]
    return " ".join(p for p in parts if p)


def _matched_skills(profile_skills: list[str], job_skills: list[str]) -> list[str]:
    ps = {s.lower() for s in profile_skills}
    js = {s.lower() for s in job_skills}
    return sorted(ps & js)


def _split_counts(size: int) -> dict[str, int]:
    if size < 3:
        return {"train": size, "validation": 0, "test": 0}
    validation = max(1, round(size * 0.15))
    test = max(1, round(size * 0.15))
    while validation + test >= size:
        if validation >= test and validation > 0:
            validation -= 1
        elif test > 0:
            test -= 1
    return {"train": size - validation - test, "validation": validation, "test": test}


def _assign_splits(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = _split_counts(len(records))
    ordered_ids = sorted(str(r["pair_id"]) for r in records)
    split_by_id: dict[str, str] = {}
    cursor = 0
    for split in ("test", "validation", "train"):
        count = counts[split]
        for pair_id in ordered_ids[cursor:cursor + count]:
            split_by_id[pair_id] = split
        cursor += count
    for r in records:
        r["split"] = split_by_id[str(r["pair_id"])]
    return records


def build_hybrid_dataset(target_positive: int = 5000) -> list[dict[str, Any]]:
    """Build hybrid dataset from real Indonesia seed jobs."""
    seed_records = _load_seed_records()
    print(f"Loaded {len(seed_records)} seed records with extractable skills")

    records: list[dict[str, Any]] = []
    all_pair_ids: set[str] = set()
    profile_counter = 0

    positive_records: list[dict[str, Any]] = []

    # For each seed, generate multiple profiles by skill-subset augmentation
    # to reach target_positive without hallucinating new jobs
    while len(positive_records) < target_positive:
        for seed in seed_records:
            if len(positive_records) >= target_positive:
                break

            title = str(seed.get("title", ""))
            skills = seed["_skills"]

            program_studi, target_role = _match_program_to_job(title, skills)

            # Skill-subset augmentation: pick 3-8 skills from the job (or all if fewer)
            max_skills = min(8, len(skills))
            n_skills = random.randint(min(3, max_skills), max_skills) if max_skills >= 1 else 1
            profile_skills = random.sample(skills, n_skills)
            profile_text = _build_profile_text(program_studi, target_role, profile_skills)

            profile_id = f"u-hybrid-{profile_counter:04d}"
            profile_counter += 1

            job_id = f"job-hybrid-{abs(hash(title)) % 100000:05d}"
            job_text = _build_job_text(seed)

            pair_id = f"{profile_id}__{job_id}"
            if pair_id in all_pair_ids:
                continue
            all_pair_ids.add(pair_id)

            positive_records.append({
                "pair_id": pair_id,
                "pair_kind": "positive",
                "profile_id": profile_id,
                "job_id": job_id,
                "profile_text": profile_text,
                "job_text": job_text,
                "profile_skills": profile_skills,
                "job_skills": skills,
                "matched_skills": _matched_skills(profile_skills, skills),
                "label": 1.0,
                "source_event": "apply",
                "source_label": 1.0,
                "provenance": "indonesian_profile_job_dataset_hybrid_v1",
                "_seed": seed,
                "_program_studi": program_studi,
                "_target_role": target_role,
            })

    print(f"Generated {len(positive_records)} positive pairs")

    # Generate negative pairs for each profile
    for pos in positive_records:
        profile_skills = set(s.lower() for s in pos["profile_skills"])
        pos_program = pos["_program_studi"]

        # Find negative candidates: seeds with different program match and low skill overlap
        negative_candidates = []
        for other_seed in seed_records:
            other_program, _ = _match_program_to_job(other_seed.get("title", ""), other_seed["_skills"])
            if other_program == pos_program:
                continue
            other_skills = set(s.lower() for s in other_seed["_skills"])
            overlap = len(profile_skills & other_skills)
            negative_candidates.append((other_seed, overlap))

        # Sort by overlap (prefer hard negatives: some overlap but low)
        negative_candidates.sort(key=lambda x: abs(x[1] - 1))

        n_negatives = random.randint(2, 3)
        chosen_negatives = negative_candidates[:n_negatives]

        for neg_seed, _ in chosen_negatives:
            neg_job_id = f"job-hybrid-{abs(hash(neg_seed.get('title',''))) % 100000:05d}"
            neg_pair_id = f"{pos['profile_id']}__{neg_job_id}"
            if neg_pair_id in all_pair_ids:
                continue
            all_pair_ids.add(neg_pair_id)

            neg_skills = neg_seed["_skills"]
            records.append({
                "pair_id": neg_pair_id,
                "pair_kind": "negative",
                "profile_id": pos["profile_id"],
                "job_id": neg_job_id,
                "profile_text": pos["profile_text"],
                "job_text": _build_job_text(neg_seed),
                "profile_skills": pos["profile_skills"],
                "job_skills": neg_skills,
                "matched_skills": _matched_skills(pos["profile_skills"], neg_skills),
                "label": 0.0,
                "source_event": "skip",
                "source_label": 0.0,
                "provenance": "indonesian_profile_job_dataset_hybrid_v1",
            })

        # Add hard negative to positive record
        if chosen_negatives:
            best_hard = chosen_negatives[0][0]
            pos["hard_negative_job_id"] = f"job-hybrid-{abs(hash(best_hard.get('title',''))) % 100000:05d}"
            pos["hard_negative_text"] = _build_job_text(best_hard)
            pos["hard_negative_skills"] = best_hard["_skills"]

        # Add the positive record
        clean_pos = {k: v for k, v in pos.items() if not k.startswith("_")}
        records.append(clean_pos)

    print(f"Total records (positive + negative): {len(records)}")

    # Assign splits
    records = _assign_splits(records)
    return records


def write_dataset(records: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False, sort_keys=True) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-positive", type=int, default=5000)
    args = parser.parse_args()

    records = build_hybrid_dataset(args.target_positive)
    write_dataset(records, args.output)

    split_counts = {"train": 0, "validation": 0, "test": 0}
    for r in records:
        split_counts[r["split"]] += 1

    positive_count = sum(1 for r in records if r["pair_kind"] == "positive")
    negative_count = sum(1 for r in records if r["pair_kind"] == "negative")
    hard_negative_count = sum(1 for r in records if r.get("hard_negative_job_id") and r["pair_kind"] == "positive")

    print(f"Wrote {len(records)} records to {args.output}")
    print(f"  Splits: {split_counts}")
    print(f"  Positive: {positive_count}")
    print(f"  Negative: {negative_count}")
    print(f"  With hard negative: {hard_negative_count}")

    # Domain distribution
    domains: Counter[str] = Counter()
    for r in records:
        if r["pair_kind"] == "positive":
            # Infer domain from profile_text first word
            program = r["profile_text"].split()[0] if r["profile_text"] else "unknown"
            domains[program] += 1
    print(f"  Top programs: {domains.most_common(10)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
