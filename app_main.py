from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ai_studio_code import SessionLocal, AuditLog, analyze_contract_liability

app = FastAPI(title="Contract Liability Audit Engine")

class ContractRequest(BaseModel):
    contract_text: str

@app.get("/")
def read_root():
    return {"message": "Contract Liability Engine active on Android"}

@app.post("/audit")
def audit_contract(request: ContractRequest):
    return analyze_contract_liability(request.contract_text)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/history")
def get_audit_history(db: Session = Depends(get_db)):
    results = db.query(AuditLog).all()
    return results
