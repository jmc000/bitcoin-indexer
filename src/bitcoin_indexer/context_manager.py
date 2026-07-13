from contextlib import contextmanager
from requests import exceptions
from sqlalchemy.exc import IntegrityError

import logger

logger = logger.setup_logging(__name__)


@contextmanager
def fail_on_error():
    try:
        yield
    except (exceptions.RequestException, OSError, RuntimeError, AttributeError) as e:
        logger.error(f"{e}")

# TODO: parse more carefully the insert (and other db) error message for better log readability
@contextmanager
def fail_on_db_error(session):
    try:
        yield
    except IntegrityError as e:
        session.rollback()
        logger.error(f"{e}")
