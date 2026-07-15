import os
import logger
import context_manager

from dotenv import load_dotenv
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logger = logger.setup_logging(__name__)
Base = declarative_base()

load_dotenv()
DEFAULT_SQLITE_URL = os.getenv('DB_URL')

# ------------------------------------------------------------
# DB Tables
# ------------------------------------------------------------
# TODO: target? coinbase_tx?
BLOCK_FIELDS_TO_EXCLUDE = ["tx", "nextblockhash", "target", "coinbase_tx"]
TRANSACTION_FIELDS_TO_EXCLUDE = ["vin", "vout"]
COINBASETX_FIELDS_TO_EXCLUDE = ["witness"]

#TODO: stale field regular sync loop
STALE_BLOCK_FIELDS = {
    "confirmations"
}

# what about "in_active_chain"?
STALE_TRANSACTION_FIELDS = {
    "confirmations"
}


class Blocks(Base):
    __tablename__ = "blocks"
    hash = Column(String, primary_key=True)
    height = Column(Integer)
    size = Column(Integer)
    strippedsize = Column(Integer)
    weight = Column(Integer)
    version = Column(Integer)
    versionHex = Column(String)
    merkleroot = Column(String)
    time = Column(Integer)
    mediantime = Column(Integer)
    confirmations = Column(Integer)
    nonce = Column(Integer)
    bits = Column(String)
    difficulty = Column(Float)
    chainwork = Column(String)
    nTx = Column(Integer)
    previousblockhash = Column(String)


class Transactions(Base):
    __tablename__ = "transactions"

    txid = Column(String, primary_key=True)
    hash = Column(String)
    in_active_chain = Column(Boolean)
    hex = Column(String)
    size = Column(Integer)
    vsize = Column(Integer)
    weight = Column(Integer)
    version = Column(Integer)
    locktime = Column(Integer)
    fee = Column(Integer)
    
    #TODO: to add, outside ["tx"]
    blockhash = Column(String, ForeignKey("blocks.hash"))

# TX_INPUTS / TX_OUTPUTS
# --> composite primary key: PRIMARY KEY (txid, input_index/output_index)
#   "vin" : [                          (json array)
#     {                                (json object)
#       "txid" : "hex",                (string) The transaction id
#       "vout" : n,                    (numeric) The output number
#       "scriptSig" : {                (json object) The script
#         "asm" : "str",               (string) asm
#         "hex" : "hex"                (string) hex
#       },
#       "sequence" : n,                (numeric) The script sequence number
#       "txinwitness" : [              (json array)
#         "hex",                       (string) hex-encoded witness data (if any)
#         ...
#       ]
#     },
#     ...
#   ],
#   "vout" : [                         (json array)
#     {                                (json object)
#       "value" : n,                   (numeric) The value in BTC
#       "n" : n,                       (numeric) index
#       "scriptPubKey" : {             (json object)
#         "asm" : "str",               (string) the asm
#         "hex" : "str",               (string) the hex
#         "reqSigs" : n,               (numeric) The required sigs
#         "type" : "str",              (string) The type, eg 'pubkeyhash'
#         "addresses" : [              (json array)
#           "str",                     (string) bitcoin address
#           ...
#         ]
#       }
#     },
#     ...
#   ],

class CoinbaseTx(Base):
    __tablename__ = "coinbasetx"

    blockhash = Column(String, ForeignKey("blocks.hash"), primary_key=True)
    version = Column(Integer)
    locktime = Column(Integer)
    sequence = Column(Integer)
    coinbase = Column(String)

# --------------
# DB Set Up
# --------------
def get_database_url() -> str:
    load_dotenv()
    return os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)

def create_db_engine(url: str | None = None):
    with context_manager.fail_on_error():
        logger.info(f"Creating Database Engine at {url}")
        url = url or get_database_url()
        connect_args = {}
        if url.startswith("sqlite"):
            #TODO: Required when the engine is shared across threads?
            connect_args["check_same_thread"] = False
        logger.info("Database Engine created.")
        return create_engine(url, echo=False, hide_parameters=True, connect_args=connect_args)

def create_tables(engine: Engine) -> None:
    #TODO: for later use Alembic instead
    with context_manager.fail_on_error():
        logger.info(f"Creating Tables...")
        Base.metadata.create_all(engine)
        table_names = inspect(engine).get_table_names()
        logger.info(f"Tables created: {table_names}")

def set_up_db() -> Engine:
    db_url=get_database_url()
    engine = create_db_engine(db_url)
    create_tables(engine)
    return engine


# --------------
# Insertion
# --------------
def insert_from_dict(list_dict: list[dict], table_class: type[Base], s: Session):
    with context_manager.fail_on_db_insert_error(s):
        if not issubclass(table_class, Base):
            raise TypeError("table_class arg must be a subclass of Base.")
        logger.info(f"Inserting {len(list_dict)} representations of the resource {table_class.__name__}...")
        pk_name = inspect(table_class).primary_key[0].name
        objects = []
        for data in list_dict:
            model = table_class(**data)
            objects.append(model)
            logger.debug(f"Inserting a representation of {table_class.__name__} with PK {pk_name}={getattr(model, pk_name)}")
        s.add_all(objects)
        s.commit()
        logger.info(f"Insertion done.")

def insert_all(block: dict, engine: Engine):
    logger.info(f"Adding Block height: {block["height"]} and all it's transactions...")
    txs = block['tx']
    block_hash = block["hash"]
    cb = block['coinbase_tx']
    cb={**cb, 'blockhash': block_hash}
    for field in BLOCK_FIELDS_TO_EXCLUDE:
        del block[field]
    for tx in txs:
        for field in TRANSACTION_FIELDS_TO_EXCLUDE:
            del tx[field]
    for field in COINBASETX_FIELDS_TO_EXCLUDE:
        del cb[field]
    with Session(engine) as s:
        insert_from_dict([block], Blocks, s)
        insert_from_dict(txs, Transactions, s)
        insert_from_dict([cb], CoinbaseTx, s)
        logger.info(f"Finished processing block {block['height']}.")
