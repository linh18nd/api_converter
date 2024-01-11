# api/database.py
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from databases import Database
from sqlalchemy import select, func
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

DATABASE_URL = "sqlite:///./test.db"

# Create a Database instance
database = Database(DATABASE_URL)

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create a metadata object
metadata = MetaData()

# Declare the Base for SQLAlchemy models
Base = declarative_base(metadata=metadata)

class DBDocument(Base):
    __tablename__ = "documents"

    pid = Column(String, primary_key=True, index=True, nullable=False, unique=True, default=lambda: str(uuid4()))
    lang = Column(String, nullable=False)
    status = Column(String, nullable=False)
    input = Column(String, nullable=False)
    output = Column(String, nullable=False)
    output_json = Column(String, nullable=False)
    output_txt = Column(String, nullable=False)
    result = Column(String, nullable=True)
    created = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processing = Column(DateTime(timezone=True), nullable=True)
    expire = Column(DateTime(timezone=True), nullable=False)
    finished = Column(DateTime(timezone=True), nullable=True)
    file_name = Column(String, nullable=True)

    def __repr__(self):
        return f"<Document(pid={self.pid}, status={self.status}, ...)>"
    
Base.metadata.create_all(bind=engine)

# This function will be used to connect to the database
async def connect():
    await database.connect()

# This function will be used to disconnect from the database
async def disconnect():
    await database.disconnect()

async def execute(query):
    return await database.execute(query)

async def fetch_all(query):
    return await database.fetch_all(query)

async def get_all_documents():
    query = select(DBDocument)
    return await database.fetch_all(query)
