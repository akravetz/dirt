from datetime import date, time

from sqlmodel import Field, SQLModel


class GrowState(SQLModel, table=True):
    """Singleton row (id=1) holding the current grow's identity + schedule.

    germination_date anchors "week N of the grow" and seeds from
    config.GROW_START on first boot. flower_start_date is the calendar day
    of the 12/12 light flip — None while in veg, set once by the user when
    flipping to flower. Flipping back later overwrites rather than keeping
    history; that's intentional for V1.

    lights_on_local / lights_off_local are tent-local times (`America/Denver`,
    see `services.grow_state.TENT_TZ`) used by the humidifier loop's
    feedforward. Standard photoperiods: veg 18/6 → (05:00, 23:00),
    flower 12/12 → (11:00, 23:00). Update via SQL when the photoperiod
    changes (future: UI field).
    """

    id: int = Field(default=1, primary_key=True)
    germination_date: date
    flower_start_date: date | None = None
    lights_on_local: time = Field(default=time(5, 0))
    lights_off_local: time = Field(default=time(23, 0))
