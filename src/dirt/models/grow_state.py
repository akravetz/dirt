from datetime import date

from sqlmodel import Field, SQLModel


class GrowState(SQLModel, table=True):
    """Singleton row (id=1) holding the current grow's identity dates.

    germination_date anchors "week N of the grow" and seeds from
    config.GROW_START on first boot. flower_start_date is the calendar day
    of the 12/12 light flip — None while in veg, set once by the user when
    flipping to flower. Flipping back later overwrites rather than keeping
    history; that's intentional for V1.
    """

    id: int = Field(default=1, primary_key=True)
    germination_date: date
    flower_start_date: date | None = None
