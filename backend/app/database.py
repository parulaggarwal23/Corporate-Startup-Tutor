import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from backend.app.models import Course, Group, SessionSchedule, Fortnight, NewsItem, PromptLog, Reflection

    Base.metadata.create_all(bind=engine)

    # Auto-migration for SQLite explanation column if missing
    try:
        with engine.connect() as conn:
            conn.execute(Base.metadata.tables["reflections"].select())
    except Exception:
        pass

    import sqlite3
    if DATABASE_URL.startswith("sqlite"):
        try:
            db_file = DATABASE_URL.replace("sqlite:///", "")
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(reflections)")
            cols = [info[1] for info in cursor.fetchall()]
            if "explanation" not in cols:
                cursor.execute("ALTER TABLE reflections ADD COLUMN explanation TEXT;")
                conn.commit()
            conn.close()
        except Exception:
            pass

    def parse_date(val):
        if not val:
            return datetime.datetime.utcnow()
        if isinstance(val, (datetime.datetime, datetime.date)):
            return val
        try:
            return datetime.datetime.fromisoformat(val)
        except Exception:
            pass
        for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.datetime.strptime(val, fmt)
            except Exception:
                pass
        return datetime.datetime.utcnow()

    db = SessionLocal()

    # 1. Seed Courses (Course 1: Corporate Startup Synergies, Course 2: Engineering Philosophy of Technology)
    course1 = db.query(Course).filter(Course.id == 1).first()
    if not course1:
        course1 = Course(
            id=1,
            code="ENT 3805",
            name="Designing Corporate Startup Synergies",
            description="Continuous Assessment tutor for corporate-startup collaboration, CVC models, accelerators, and joint development agreements.",
            icon="📊"
        )
        db.add(course1)
        db.commit()
        db.refresh(course1)

    course2 = db.query(Course).filter(Course.id == 2).first()
    if not course2:
        course2 = Course(
            id=2,
            code="ENG 4101",
            name="Engineering Philosophy of Technology",
            description="Continuous Assessment tutor for engineering epistemology, technological determinism, ethics, mediation, and design philosophy.",
            icon="⚙️"
        )
        db.add(course2)
        db.commit()
        db.refresh(course2)

    # 2. Seed Default Group
    group = db.query(Group).first()
    if not group:
        group = Group(
            id=1,
            name="Syndicate 1",
            course_name="Designing Corporate Startup Synergies",
            description="Official Continuous Assessment syndicate group."
        )
        db.add(group)
        db.commit()
        db.refresh(group)

    # 3. Automatic Seeding of All Real Coursework Sessions, Reflections, Logs & News
    # Checks if sessions or reflections need to be seeded (e.g. fresh deployment or new database)
    total_sessions = db.query(SessionSchedule).count()
    total_reflections = db.query(Reflection).count()

    from backend.app.config import DATA_DIR
    import json
    import os

    seed_file = os.path.join(DATA_DIR, "seed_data.json")
    if (total_sessions == 0 or total_reflections == 0) and os.path.exists(seed_file):
        try:
            with open(seed_file, "r", encoding="utf-8") as f:
                seed_data = json.load(f)

            for row in seed_data.get("courses", []):
                row_copy = dict(row)
                row_copy["created_at"] = parse_date(row_copy.get("created_at"))
                db.merge(Course(**row_copy))

            for row in seed_data.get("groups", []):
                row_copy = dict(row)
                row_copy["created_at"] = parse_date(row_copy.get("created_at"))
                db.merge(Group(**row_copy))

            for row in seed_data.get("session_schedules", []):
                row_copy = dict(row)
                row_copy["created_at"] = parse_date(row_copy.get("created_at"))
                db.merge(SessionSchedule(**row_copy))

            for row in seed_data.get("fortnights", []):
                row_copy = dict(row)
                row_copy["created_at"] = parse_date(row_copy.get("created_at"))
                db.merge(Fortnight(**row_copy))

            for row in seed_data.get("news_items", []):
                row_copy = dict(row)
                row_copy["created_at"] = parse_date(row_copy.get("created_at"))
                db.merge(NewsItem(**row_copy))

            for row in seed_data.get("prompt_logs", []):
                row_copy = dict(row)
                row_copy["timestamp"] = parse_date(row_copy.get("timestamp"))
                db.merge(PromptLog(**row_copy))

            for row in seed_data.get("reflections", []):
                row_copy = dict(row)
                row_copy["created_at"] = parse_date(row_copy.get("created_at"))
                db.merge(Reflection(**row_copy))

            for row in seed_data.get("student_notes", []):
                row_copy = dict(row)
                row_copy["created_at"] = parse_date(row_copy.get("created_at"))
                row_copy["updated_at"] = parse_date(row_copy.get("updated_at"))
                db.merge(StudentNote(**row_copy))

            db.commit()
            print("[init_db] Successfully loaded all student coursework data from seed_data.json!")
        except Exception as e:
            db.rollback()
            print(f"[init_db] Warning: Failed to load seed_data.json: {e}")

    # 4. Ensure any records without course_id are associated with Course 1
    db.query(SessionSchedule).filter(SessionSchedule.course_id == None).update({SessionSchedule.course_id: 1})
    db.query(PromptLog).filter(PromptLog.course_id == None).update({PromptLog.course_id: 1})
    db.query(Reflection).filter(Reflection.course_id == None).update({Reflection.course_id: 1})
    db.query(Fortnight).filter(Fortnight.course_id == None).update({Fortnight.course_id: 1})
    db.query(NewsItem).filter(NewsItem.course_id == None).update({NewsItem.course_id: 1})
    db.commit()

    db.close()
