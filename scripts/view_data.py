#!/usr/bin/env python3
"""View sample data from the database"""
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Parse DATABASE_URL
db_url = os.getenv("DATABASE_URL", "")
if "://" in db_url:
    db_url = db_url.split("://", 1)[1]

auth, location = db_url.split("@")
user, password = auth.split(":")
host_port, database = location.split("/")
if "?" in database:
    database = database.split("?")[0]
if ":" in host_port:
    host, port = host_port.split(":")
else:
    host, port = host_port, "5432"

# Connect
conn = psycopg2.connect(
    user=user,
    password=password,
    host=host,
    port=port,
    database=database
)

cur = conn.cursor()

print("=" * 80)
print("📊 SCPA Database - Sample Data View")
print("=" * 80)

# Users
print("\n👥 USERS")
print("-" * 80)
cur.execute("SELECT id, name, email, role, completion_percent, created_at FROM users LIMIT 5")
users = cur.fetchall()
if users:
    for user_data in users:
        user_id, name, email, role, completion, created = user_data
        print(f"  • {name}")
        print(f"    Email: {email}")
        print(f"    Role: {role} | Profile: {completion}% complete")
        print(f"    ID: {user_id}")
        print()
else:
    print("  No users found")

# Jobs
print("\n💼 JOBS")
print("-" * 80)
cur.execute("""
    SELECT id, title, company, location, type, 
           min_salary, max_salary, posted_at 
    FROM jobs 
    ORDER BY posted_at DESC 
    LIMIT 5
""")
jobs = cur.fetchall()
if jobs:
    for job_data in jobs:
        job_id, title, company, location, job_type, min_sal, max_sal, posted = job_data
        print(f"  • {title}")
        print(f"    Company: {company}")
        print(f"    Location: {location or 'Not specified'}")
        print(f"    Type: {job_type or 'Not specified'}")
        if min_sal and max_sal:
            print(f"    Salary: IDR {min_sal:,.0f} - {max_sal:,.0f}")
        print(f"    Posted: {posted}")
        print(f"    ID: {job_id}")
        print()
else:
    print("  No jobs found")

# User Skills
print("\n🎯 USER SKILLS")
print("-" * 80)
cur.execute("""
    SELECT us.skill, us.category, us.proficiency_level, u.name
    FROM user_skills us
    JOIN users u ON us.user_id = u.id
    ORDER BY u.name, us.skill
    LIMIT 10
""")
skills = cur.fetchall()
if skills:
    current_user = None
    for skill, category, proficiency, user_name in skills:
        if user_name != current_user:
            if current_user is not None:
                print()
            print(f"  {user_name}:")
            current_user = user_name
        print(f"    • {skill} ({category}) - {proficiency}")
else:
    print("  No skills found")

# Applications
print("\n📝 APPLICATIONS")
print("-" * 80)
cur.execute("""
    SELECT a.id, u.name, j.title, j.company, a.status, a.applied_at
    FROM applications a
    JOIN users u ON a.user_id = u.id
    JOIN jobs j ON a.job_id = j.id
    ORDER BY a.applied_at DESC
    LIMIT 5
""")
applications = cur.fetchall()
if applications:
    for app_id, user_name, job_title, company, status, applied in applications:
        print(f"  • {user_name} → {job_title} at {company}")
        print(f"    Status: {status}")
        print(f"    Applied: {applied}")
        print()
else:
    print("  No applications yet")

# User Interactions
print("\n🔄 USER INTERACTIONS")
print("-" * 80)
cur.execute("""
    SELECT ui.action_type, ui.target_type, u.name, ui.created_at
    FROM user_interactions ui
    JOIN users u ON ui.user_id = u.id
    ORDER BY ui.created_at DESC
    LIMIT 5
""")
interactions = cur.fetchall()
if interactions:
    for action, target, user_name, created in interactions:
        print(f"  • {user_name} {action} {target}")
        print(f"    Time: {created}")
        print()
else:
    print("  No interactions logged yet")

# Statistics
print("\n📈 DATABASE STATISTICS")
print("-" * 80)
cur.execute("SELECT COUNT(*) FROM users")
user_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM jobs")
job_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM applications")
app_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM user_skills")
skill_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM user_interactions")
interaction_count = cur.fetchone()[0]

print(f"  Total Users: {user_count}")
print(f"  Total Jobs: {job_count}")
print(f"  Total Applications: {app_count}")
print(f"  Total Skills: {skill_count}")
print(f"  Total Interactions: {interaction_count}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("✅ Data view complete!")
print("=" * 80)
