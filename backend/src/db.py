import json
from pathlib import Path
from typing import Optional
from sqlmodel import Session, create_engine, SQLModel, select

from core.models import RecoveryState

DB_PATH = Path(__file__).parent.parent / "recovery.db"
sqlite_url = f"sqlite:///{DB_PATH}"

# Create the SQLAlchemy engine
engine = create_engine(sqlite_url)

def init_db():
    """Initialize the SQLModel database schema."""
    SQLModel.metadata.create_all(engine)

def save_state(state: RecoveryState):
    """Save or update the RecoveryState to the database."""
    init_db()
    with Session(engine, expire_on_commit=False) as session:
        # Check if it already exists
        existing_state = session.get(RecoveryState, state.case_id)
        if existing_state:
            # Update existing state
            for key, value in state.model_dump().items():
                setattr(existing_state, key, value)
            session.add(existing_state)
        else:
            # Add new state
            session.add(state)
        session.commit()

def load_state(case_id: str) -> Optional[RecoveryState]:
    """Load a RecoveryState by case_id."""
    init_db()
    with Session(engine, expire_on_commit=False) as session:
        return session.get(RecoveryState, case_id)
