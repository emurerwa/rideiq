import duckdb
import pandas as pd

from .config import RAW, SQL_DIR


def connect(trips_path=None, stations_path=None) -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with `trips` and `stations` views over the raw parquet files."""
    trips_path = trips_path or RAW / "trips.parquet"
    stations_path = stations_path or RAW / "stations.parquet"
    con = duckdb.connect()
    con.execute(f"CREATE VIEW trips AS SELECT * FROM read_parquet('{trips_path}')")
    con.execute(f"CREATE VIEW stations AS SELECT * FROM read_parquet('{stations_path}')")
    return con


def query(con, name: str) -> pd.DataFrame:
    """Run sql/<name>.sql and return a DataFrame. SQL stays in .sql files."""
    return con.execute((SQL_DIR / f"{name}.sql").read_text()).df()
