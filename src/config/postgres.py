from configparser import ConfigParser
from pathlib import Path
import psycopg

_POSTGRES_INI = Path(__file__).resolve().parents[2] / "src" / "config" / "postgres.ini"
def config(filename=_POSTGRES_INI, section='postgresql'):
    parser = ConfigParser()
    parser.read(filename)

    db = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))

    return db

def connect() -> psycopg.connect:
    """Connect to the PostgreSQL database"""
    db = config(filename=_POSTGRES_INI, section='postgresql')
    conn = psycopg.connect(**db)
    return conn