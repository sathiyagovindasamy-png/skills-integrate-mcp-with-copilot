"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path

from sqlalchemy import (create_engine, Column, Integer, String, Table,
                        ForeignKey)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# --- Persistence setup (SQLite + SQLAlchemy) ---
DATABASE_URL = f"sqlite:///{os.path.join(current_dir, '..', 'data.db')}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

signups = Table(
    "signups",
    Base.metadata,
    Column("activity_id", ForeignKey("activities.id"), primary_key=True),
    Column("participant_id", ForeignKey("participants.id"), primary_key=True),
)


class Activity(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String)
    schedule = Column(String)
    max_participants = Column(Integer, default=0)
    participants = relationship("Participant", secondary=signups, back_populates="activities")


class Participant(Base):
    __tablename__ = "participants"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    activities = relationship("Activity", secondary=signups, back_populates="participants")


Base.metadata.create_all(bind=engine)

# Seed data (migrate in-memory data to DB on first run)
initial_activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    }
}


def seed_db():
    db = SessionLocal()
    try:
        existing = db.query(Activity).first()
        if existing:
            return

        for name, meta in initial_activities.items():
            activity = Activity(
                name=name,
                description=meta.get("description"),
                schedule=meta.get("schedule"),
                max_participants=meta.get("max_participants", 0),
            )
            db.add(activity)
            db.flush()  # ensure ID

            for email in meta.get("participants", []):
                participant = db.query(Participant).filter_by(email=email).first()
                if not participant:
                    participant = Participant(email=email)
                    db.add(participant)
                    db.flush()
                activity.participants.append(participant)

        db.commit()
    finally:
        db.close()


seed_db()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    db = SessionLocal()
    try:
        activities = {}
        for act in db.query(Activity).all():
            activities[act.name] = {
                "description": act.description,
                "schedule": act.schedule,
                "max_participants": act.max_participants,
                "participants": [p.email for p in act.participants]
            }
        return activities
    finally:
        db.close()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    db = SessionLocal()
    try:
        activity = db.query(Activity).filter_by(name=activity_name).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        # Check if already signed up
        if any(p.email == email for p in activity.participants):
            raise HTTPException(status_code=400, detail="Student is already signed up")

        # Check capacity
        if activity.max_participants and len(activity.participants) >= activity.max_participants:
            raise HTTPException(status_code=400, detail="Activity is full")

        participant = db.query(Participant).filter_by(email=email).first()
        if not participant:
            participant = Participant(email=email)
            db.add(participant)
            db.flush()

        activity.participants.append(participant)
        db.commit()
        return {"message": f"Signed up {email} for {activity_name}"}
    finally:
        db.close()


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    db = SessionLocal()
    try:
        activity = db.query(Activity).filter_by(name=activity_name).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        participant = db.query(Participant).filter_by(email=email).first()
        if not participant or participant not in activity.participants:
            raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

        activity.participants.remove(participant)
        db.commit()
        return {"message": f"Unregistered {email} from {activity_name}"}
    finally:
        db.close()
