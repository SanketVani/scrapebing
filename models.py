from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config_secret import DATABASE_URL  

Base = declarative_base()

class SearchResult(Base):
    __tablename__ = 'search_results'
    id = Column(Integer, primary_key=True)
    query = Column(String)
    title = Column(String)
    url = Column(String)
    snippet = Column(String)

def get_session():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
