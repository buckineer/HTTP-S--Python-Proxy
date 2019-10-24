import sqlalchemy as db
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session
from sqlalchemy import Column, Integer, String

Base = declarative_base()

class User(Base):
    __tablename__ = 'UserAdmin_user'
    # Here we define columns for the table person
    # Notice that each column is also a normal Python instance attribute.
    id = Column(Integer, primary_key=True)
    username = Column(String(250), nullable=False)
    password = Column(String(250))


def init(database_url):
    try:
        engine = db.create_engine(database_url)
        Base.metadata.bind = engine
        DBSession = sessionmaker(bind=engine)
        ScopedSession = scoped_session(DBSession)        
        return (True, ScopedSession)
    except Exception as e:
        print(e)
        print("Database Initialization Failed")
        return (False, None)
