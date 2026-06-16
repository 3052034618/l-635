from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class ArchiveCategory(Base):
    __tablename__ = "archive_categories"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("archive_categories.id"))
    description = Column(String(500))
    retention_period = Column(Integer, default=30)

    parent = relationship("ArchiveCategory", remote_side=[id])
    archives = relationship("Archive", back_populates="category")
