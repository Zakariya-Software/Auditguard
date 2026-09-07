import os
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./audits.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    contract_text = Column(Text)
    risk_level = Column(String)
    summary = Column(Text)

Base.metadata.create_all(bind=engine)

def analyze_contract_liability(contract_text: str):
    risk = "High" if "indemnify" in contract_text.lower() else "Low"
    db = SessionLocal()
    log = AuditLog(contract_text=contract_text, risk_level=risk, summary="Analyzed successfully")
    db.add(log)
    db.commit()
    db.refresh(log)
    db.close()
    return {"id": log.id, "risk_level": risk, "summary": log.summary}
