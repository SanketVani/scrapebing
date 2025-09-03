from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class SearchResult(Base):
    __tablename__ = 'search_results'
    id = Column(Integer, primary_key=True)
    query = Column(String)
    title = Column(String)
    url = Column(String)
    snippet = Column(String)

def get_session():
    engine = create_engine('postgresql://postgres:123789@localhost:5432/bingdb')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
