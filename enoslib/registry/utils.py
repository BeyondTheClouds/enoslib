import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

MAX_CRONJOB_LENGTH = 998
logger = logging.getLogger(__name__)


def check_cron_cmd(cmd: str):
    """
    Verify that a command can be scheduled using cron.
    """
    if len(cmd) > MAX_CRONJOB_LENGTH:
        raise ValueError("Command to long for a cronjob.")


def check_cron_date(date: datetime, delay: timedelta = timedelta(minutes=1)) -> None:
    """
    Verify that a cronjob will not be scheduled to early.
    """
    time_now = datetime.now()

    if (time_now + delay) > date:
        raise ValueError("Time span smaller than now + 1min. Cronjob can't be launch.")


def check_args(
    signum: Optional[int] = None,
    number: Optional[int] = None,
    start_at: Optional[datetime] = None,
    start_in: Optional[timedelta] = None,
    is_async: bool = False,
    interval: Optional[timedelta] = None,
) -> None:
    """
    Check the consistency of each passed argument.
    """
    if signum is not None and not isinstance(signum, int):
        raise TypeError("signum must be a signal constant.")

    if start_at is not None:
        if not isinstance(start_at, datetime):
            raise TypeError("start_at must be a datetime.datetime object.")

    elif start_in is not None:
        if not isinstance(start_in, timedelta):
            raise TypeError("start_in must be a datetime.timedelta object.")

    elif is_async:
        logger.error("A time object is needed to launch a cronjob.")

    if number is not None and number <= 0:
        raise ValueError(
            "A strictly positive number is needed to choose the processes to kill."
        )

    if interval is not None and interval.total_seconds() < 0:
        raise ValueError("The interval must be positive.")


class State(Enum):
    """
    A class that define the possible states of a process.
    """

    ALIVE = 0
    DEAD = 1
    UNKNOWN = 2
