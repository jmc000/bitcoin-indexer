import logger
import rpc as rpc
import db as db

from sqlalchemy.engine import Engine

logger = logger.setup_logging(__name__)


def insert_block_with_txs(block_number: int, engine: Engine):
    block = rpc.Blocks()
    block_hash = block.get_block_hash(block_number)
    b = block.get_block(block_hash, verbosity=2)
    db.insert_all(b, engine)

if __name__ == "__main__":
    # -----------
    #  MVP
    # -----------
    block_number = 957354
    engine = db.set_up_db()
    insert_block_with_txs(block_number, engine)

