from fastapi.responses import HTMLResponse
from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ai_studio_code import SessionLocal, AuditLog, analyze_contract_liability
from fastapi import Request
from datetime import datetime, date

app = FastAPI(title="Contract Liability Audit Engine")

class ContractRequest(BaseModel):
    contract_text: str

@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AuditGuard - Contract Risk Analyzer</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; padding: 16px; margin: 0; display: flex; justify-content: center; }
            .container { width: 100%; max-width: 500px; background: #1e293b; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.4); }
            h1 { font-size: 1.4rem; margin-bottom: 4px; color: #38bdf8; }
            p { color: #94a3b8; font-size: 0.85rem; margin-bottom: 16px; }
            textarea { width: 100%; height: 140px; background: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 8px; padding: 12px; font-size: 0.9rem; box-sizing: border-box; resize: vertical; }
            button { background: #38bdf8; color: #0f172a; border: none; padding: 12px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%; margin-top: 12px; font-size: 1rem; }
            #result { margin-top: 16px; background: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #334155; white-space: pre-wrap; display: none; font-family: monospace; font-size: 0.8rem; color: #34d399; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AuditGuard</h1>
            <p>Paste your contract text below for an instant risk evaluation.</p>
            <textarea id="contractInput" placeholder="Paste contract text here..."></textarea>
            <button onclick="submitAudit()">Analyze Contract</button>
            <div id="result"></div>
        </div>
        <script>
            async function submitAudit() {
                const text = document.getElementById('contractInput').value;
                const resultDiv = document.getElementById('result');
                if (!text) { alert('Please enter contract text'); return; }
                resultDiv.style.display = 'block';
                resultDiv.textContent = 'Analyzing contract...';
                try {
                    const response = await fetch('/audit', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ contract_text: text })
                    });
                    const data = await response.json();
                    resultDiv.textContent = JSON.stringify(data, null, 2);
                } catch (err) {
                    resultDiv.textContent = 'Error: ' + err.message;
                }
            }
        </script>
    </body>
    </html>
   def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/audit")
def audit_contract(request: ContractRequest, req: Request, db: Session = Depends(get_db)):
    client_ip = req.client.host
    today = date.today()

    daily_count = db.query(AuditLog).filter(
        AuditLog.ip_address == client_ip,
        AuditLog.created_at >= datetime.combine(today, datetime.min.time())
    ).count()

    if daily_count >= 3:
        return {"error": "Daily limit reached (3/3 free audits used). Please upgrade!"}

    return analyze_contract_liability(request.contract_text)

@app.get("/history")
def get_audit_history(db: Session = Depends(get_db)):
    results = db.query(AuditLog).all()
    return results
