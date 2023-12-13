from sqlalchemy import create_engine, Column, String, Text, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from databases import Database
from datetime import datetime
import uuid

DATABASE_URL = "sqlite:///./test.db"
database = Database(DATABASE_URL)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True,
                default=str(uuid.uuid4()), index=True)
    lang = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    pdf_path = Column(String, nullable=False)
    ocr_content = Column(Text)
    file_name = Column(String, nullable=False)


Base.metadata.create_all(bind=engine)


def save_document_to_database(document_data):
    with SessionLocal() as session:
        document_instance = Document(**document_data)
        session.add(document_instance)
        session.commit()
