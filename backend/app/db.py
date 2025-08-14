import psycopg2
from psycopg2 import pool
from .config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

_conn_pool: pool.SimpleConnectionPool | None = None

def init_pool():
    global _conn_pool
    if _conn_pool is None:
        _conn_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            host=DB_HOST,
            port=int(DB_PORT),
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )

def get_conn():
    if _conn_pool is None:
        init_pool()
    return _conn_pool.getconn()

def put_conn(conn):
    if _conn_pool:
        _conn_pool.putconn(conn)
