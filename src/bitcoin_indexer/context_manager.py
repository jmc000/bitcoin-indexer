from contextlib import contextmanager
from requests import exceptions
from sqlalchemy.exc import IntegrityError

import logger

logger = logger.setup_logging(__name__)

@contextmanager
def fail_on_error():
    try:
        yield
    except exceptions.HTTPError as e:
        logger.error("HTTPError %s: %s - %s", e.response.status_code, e.response.reason, e.response.text)
    except (exceptions.RequestException, AttributeError) as e:
        logger.error(e)

@contextmanager
def fail_on_db_insert_error(session):
    try:
        yield
    except IntegrityError as e:
        session.rollback()
        logger.error({e})
