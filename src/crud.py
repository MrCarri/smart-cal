"""Crud functions module"""

from datetime import timedelta

from sqlmodel import Session, col, select

from helpers import from_utc_to_local, to_utc_naive
from models import Category, Event

import dateparser


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
        start_date: str,
        end_date: str | None = None,
    ) -> dict:
        """Creates event in DB

        Args:
            title (str): Event to be added to the database
            start_date(str): Event start time.
            end_date(str): Event end time,
            category_name(str): Assigned category to the event.
        Returns:
            dict: Success status and the created event basic data.
        """
        start_date_utc = to_utc_naive(date_str=start_date)
        if not end_date or not end_date.strip():
            end_date_utc = start_date_utc + timedelta(hours=1)
        else:
            end_date_utc = to_utc_naive(date_str=end_date)
        category = self.get_or_create_category(name=category_name)
        event = Event(
            title=title,
            start_date=start_date_utc,
            end_date=end_date_utc,
            category_model=category,
        )

        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return {
            "status": "success",
            "message": f"Event '{event.title}' created successfully.",
            "id": event.id,
            "start": from_utc_to_local(event.start_date).strftime("%Y-%m-%d %H:%M"),
            "end": from_utc_to_local(event.end_date).strftime("%Y-%m-%d %H:%M"),
            "category": category.name,
        }

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

    def get_events(self, start_date: str, end_date: str | None = None) -> list[dict]:
        """Gets events on DB matching the range

        Args:
            start_date(str): Start date of the range
            end_date(str | None): End date of the range. Can be None or "" depending on AI Agent.

        Returns:
            list[dict]: List of found events.

        """
        dt_start = dateparser.parse(
            start_date, settings={"PREFER_DATES_FROM": "future"}
        )

        if not dt_start:
            return []
        start_utc = to_utc_naive(f"{dt_start.strftime('%Y-%m-%d %H:%M')}")
        if not end_date or end_date == "":
            end_utc = to_utc_naive(dt_start.strftime("%Y-%m-%d 23:59"))
        else:
            dt_end = dateparser.parse(
                end_date, settings={"PREFER_DATES_FROM": "future"}
            )
            end_utc = to_utc_naive(f"{dt_end}")
        statement = (
            select(Event)
            .where(Event.start_date >= start_utc, Event.start_date <= end_utc)
            .order_by(col(Event.start_date))
        )
        events = list(self.session.exec(statement).all())
        formatted_results = []
        for event in events:
            local_start = from_utc_to_local(event.start_date)
            local_end = from_utc_to_local(event.end_date)
            formatted_results.append(
                {
                    "id": event.id,
                    "title": event.title,
                    "start": local_start.strftime("%Y-%m-%d %H:%M"),
                    "end": local_end.strftime("%Y-%m-%d %H:%M"),
                    "category": event.category_model.name,
                }
            )

        return formatted_results

    def delete_event(self, event_id: int) -> dict:
        """Deletes event by id

        Args:
            event_id(int): Id of the event to be deleted
        Returns:
            dict: Status and message
        """
        event = self.session.get(Event, event_id)
        if not event:
            return {"status": "error", "message": f"No event found with ID {event_id}."}
        title_backup = event.title
        self.session.delete(event)
        self.session.commit()
        return {
            "status": "success",
            "message": f"Event '{title_backup}' deleted successfully.",
            "id": event_id,
        }
