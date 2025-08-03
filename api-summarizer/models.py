from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import VECTOR
import datetime
from database import Base

class Documents(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(Integer)
    chunck_id = Column(Integer)
    title = Column(String)
    publisher = Column(String)
    publish_date = Column(DateTime, default=datetime.utcnow)
    author = Column(String)
    content = Column(String)
    embedding = Column(VECTOR(768))