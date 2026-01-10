"""Crud functions module"""

from datetime import datetime, timedelta
from typing import Sequence

from sqlmodel import Session, col, select

from models import Category, Event


class CalendarRepository:
    """Generic repository for CRUD"""

    def __init__(self, session: Session):
        """Creates base repository

        Args:
            session (Session): DB session object
        """
        self.session = session

    def create_event(
        self,
        title: str,
        category_name: str,
        start_date: datetime,
        end_date: datetime | None = None,
    ) -> Event:
        """Creates event in DB

        Args:
            title (str): Event to be added to the database
            start_date(datetime): Event start time.
            end_date(datetime): Event end time,
            category_name(str): Assigned category to the event.
        Returns:
            Event: The created event object
        """
        if not end_date:
            end_date = start_date + timedelta(hours=1)
        category = self.get_or_create_category(name=category_name)
        event = Event(
            title=title,
            start_date=start_date,
            end_date=end_date,
            category_model=category,
        )

        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def create_category(self, name: str) -> Category:
        """Creates category in DB

        Args:
            name (str): Category to be added to the database

        Returns:
            Category: created category
        """
        category = Category(name=name.lower())
        self.session.add(category)
        self.session.commit()
        self.session.refresh(category)
        return category

    def get_or_create_category(self, name: str) -> Category:
        """Gets category by name from db or creates it.

        Args:
            name (str): Category name to be added /fetched to the database

        Returns:
            Category: Found Category
        """

        statement = select(Category).where(Category.name == name.lower())
        category = self.session.exec(statement).first()
        if not category:
            return self.create_category(name=name)
        return category

    def get_events(self, start_date: datetime, end_date: datetime) -> Sequence[Event]:
        statement = (
            select(Event)
            .where(Event.start_date >= start_date, Event.end_date <= end_date)
            .order_by(col(Event.start_date))
        )
        return self.session.exec(statement).all()

    def delete_event(self, event_id: int) -> bool:
        """Deletes event by id

        Returns:
            bool: True if deleted, False if nonexistent.
        """
        event = self.session.get(Event, event_id)
        if not event:
            return False

        self.session.delete(event)
        self.session.commit()
        return True
