import os
import logger
import context_manager

from dotenv import load_dotenv
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, create_engine, event
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
    hash = Column(String, primary_key=True, unique=True)
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

    txid = Column(String, primary_key=True, unique=True)
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


# COINBASE TX (from getblock)
# TODO: remove witness (always 0)
# "coinbase_tx": {
#     "version": 1,
#     "locktime": 1106486620,
#     "sequence": 0,
#     "coinbase": "03aa9b0e2cfabe6d6d0282b99a5255e3a7f4ce5a902045550078aafc056ad84b1e20942c3a1b2f1a9710000000f09f909f092f4632506f6f6c2f640000000000000000000000000000000000000000000000000000000000000000000000050000302800",
#     "witness": "0000000000000000000000000000000000000000000000000000000000000000"
#   }


# --------------
# General
# --------------
def get_database_url() -> str:
    load_dotenv()
    return os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)

def create_db_engine(url: str | None = None):
    url = url or get_database_url()
    connect_args = {}
    if url.startswith("sqlite"):
        # Required when the engine is shared across threads?
        connect_args["check_same_thread"] = False
    return create_engine(url, echo=False, connect_args=connect_args)

def create_tables(engine: Engine) -> None:
    #TODO: for later use Alembic instead
    Base.metadata.create_all(engine)

def set_up_db() -> Engine:
    db_url=get_database_url()
    engine = create_db_engine(db_url)
    create_tables(engine)
    return engine

# --------------
# Block
# --------------
def insert_blocks(blocks: list[Blocks], s: Session):
    with context_manager.fail_on_db_error(s):
        s.add_all(blocks)
        s.commit()

def insert_blocks_from_dict(block_list: list[dict], s: Session):
    with context_manager.fail_on_db_error(s):
        blocks = []
        for data in block_list:
            b = Blocks(**data)
            blocks.append(b)
        s.add_all(blocks)
        s.commit()


# --------------
# Transaction
# --------------
def insert_txs(txs: list[Transactions], s: sessionmaker):
    with context_manager.fail_on_db_error(s):
        s.add_all(txs)
        s.commit()

def insert_transactions_from_dict(tx_list: list[dict], s: sessionmaker, block_hash : String = None):
    with context_manager.fail_on_db_error(s):
        txs = []
        for data in tx_list:
            if block_hash is not None:
                data={**data, 'blockhash': block_hash}
            t = Transactions(**data)
            txs.append(t)
        s.add_all(txs)
        s.commit()

# --------------
# Block + txs
# --------------
def insert_block_with_txs(block: dict, engine: Engine):
    txs = block['tx']
    block_hash = block["hash"]
    print(f"block hash: {block_hash}")

    for field in BLOCK_FIELDS_TO_EXCLUDE:
        del block[field]
    for tx in txs:
        for field in TRANSACTION_FIELDS_TO_EXCLUDE:
            del tx[field]
    
    with Session(engine) as s:
        #TODO: this method should still take a list of dict?
        insert_blocks_from_dict([block],s)
        insert_transactions_from_dict(txs, s, block_hash)
