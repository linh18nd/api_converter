# import uuid
# from sqlalchemy import Column, DateTime, String, Text, create_engine, func
# from sqlalchemy.orm import Session
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
# from databases import Database

# from api.models import Lang
# username = "root"
# password = "linh2002"
# host = "localhost"
# port = 3306
# database = "documents"
# DATABASE_URL =  "mysql+mysqlconnector://root:linh2002@localhost/documents"


# database = Database(DATABASE_URL)
# engine = create_engine(DATABASE_URL)
# # SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# try:
#     engine.connect()
#     print("Kết nối thành công!")
# except Exception as e:
#     print("Lỗi kết nối:", e)

# Base = declarative_base()
# class Documents(Base):
#     __tablename__ = "documents"

#     id = Column(String, primary_key=True, default=uuid.uuid4, index=True)

#     lang = Column(String, nullable=False, server_default=Lang.eng.value)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     pdf_path = Column(String, nullable=False)
#     ocr_content = Column(Text)
#     file_name = Column(String, nullable=False)
    
#     def as_dict(self):
#         return {column.name: getattr(self, column.name) for column in self.__table__.columns}


# Base.metadata.create_all(bind=engine)

# def save_document_to_database(db: Session, document_data):
#     document_instance = Documents(**document_data)
#     db.add(document_instance)
#     db.commit()
#     db.refresh(document_instance)
#     return document_instance
        