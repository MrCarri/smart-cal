from pathlib import Path

from sqlmodel import SQLModel, create_engine

import models  # noqa: F401

sqlite_path = Path("data/")
sqlite_file_name = "calendar.db"
sqlite_file_path = sqlite_path / sqlite_file_name
sqlite_url = f"sqlite:///{sqlite_file_path}"

engine = create_engine(sqlite_url, echo=False)


def create_db_and_tables():
    """Creates database enigne and creates tables using the models."""
    sqlite_path.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
