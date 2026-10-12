from sqlalchemy import create_engine

from .config import settings
from .schema import make_metadata

engine = create_engine(settings.database_url, pool_pre_ping=True)
metadata = make_metadata()
runs, companies, people, sources, claims, evidence = (
    metadata.tables[name]
    for name in ("runs", "companies", "people", "sources", "claims", "evidence")
)
