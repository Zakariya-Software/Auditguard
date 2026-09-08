from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import date
import json

# 1. Initialize the FastAPI app
app = FastAPI(title="AuditGuard Engine")

# 2. Define Data Models
class ContractRequest(BaseModel):
    contract_text: str

# 3. Global State (In-memory storage for this example)
# In a production app, you would use a database like PostgreSQL or Redis
PAID_USERS = set()
USAGE_COUNTS = {}

# 4. Core Logic Functions
def analyze_contract_liability(text: str):
    """
    Simulates AI contract analysis. 
    In a real app, this would call an LLM or a legal analysis engine.
    """
    # This is a placeholder for the logic shown in your image
    word_count = len(text.split())
    
    # Example logic: if the contract is very short, flag it
    risk_score = 'LOW'
    if word_count < 20:
        risk_score = 'CRITICAL'
    elif word_count > 500:
        risk_score = 'MEDIUM'

    return {
        "status": "success",
        "risk_score": risk_score,
        "analysis": f"Analysis complete for {word_count} words.",
        "details": "Liability clauses appear standard." if risk_score == 'LOW' else "Contract length or content requires manual review."
    }

# 5. Route Handlers

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serves the frontend interface."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AuditGuard - Contract Risk Analyzer</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; padding: 16px; margin: 0; }
            .container { width: 100%; max-width: 500px; margin: auto; background: #1e293b; padding: 20px; border-radius: 12px; }
            h1 { font-size: 1.4rem; margin-bottom: 4px; color: #38bdf8; }
            textarea { width: 100%; height: 100px; background: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 8px; margin-bottom: 16px; padding: 8px; box-sizing: border-box; }
            button { width: 100%; background: #0284c7; color: white; border: none; padding: 12px; font-weight: bold; border-radius: 8px; cursor: pointer; margin-top: 8px;}
            button:hover { background: #0369a1; }
            .btn-pro { background: #16a34a; }
            .btn-pro:hover { background: #15803d; }
            #result { margin-top: 16px; padding: 12px; background: #0f172a; border-radius: 8px; border: 1px solid #334155; white-space: pre-wrap; display: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AuditGuard</h1>
            <p>Paste your contract text below for an instant risk evaluation.</p>
            <textarea id="contractInput" placeholder="Paste contract text here..."></textarea>
            <button onclick="submitAudit()">Analyze Contract</button>
            <button class="btn-pro" onclick="upgradeAccount()">Upgrade to Pro (Remove Limits)</button>
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
                    
                    if (data.error) {
                        resultDiv.textContent = 'Error: ' + data.error;
                        resultDiv.style.borderColor = '#ef4444';
                    } else {
                        resultDiv.textContent = JSON.stringify(data, null, 2);
                        resultDiv.style.borderColor = data.risk_score === 'CRITICAL' ? '#ef4444' : '#38bdf8';
                    }
                } catch (err) {
                    resultDiv.textContent = 'Error: ' + err.message;
                }
            }

            async function upgradeAccount() {
                try {
                    const response = await fetch('/upgrade', { method: 'POST' });
                    const data = await response.json();
                    alert(data.message);
                } catch (err) {
                    alert('Upgrade failed.');
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/audit")
async def audit(request: ContractRequest, req: Request):
    client_ip = req.client.host
    today_str = str(date.today())

    # 1. Paid users bypass the daily limit
    if client_ip in PAID_USERS:
        return analyze_contract_liability(request.contract_text)

    # 2. Check free user daily limit (max 3 audits)
    key = f"{client_ip}_{today_str}"
    current_count = USAGE_COUNTS.get(key, 0)

    if current_count >= 3:
        return {"error": "Daily limit reached (3/3 free audits used). Please upgrade!"}

    # 3. Increment count and perform audit
    USAGE_COUNTS[key] = current_count + 1
    return analyze_contract_liability(request.contract_text)

@app.post("/upgrade")
async def upgrade_account(req: Request):
    """
    Simulates an upgrade. In a real app, this would follow a 
    successful payment confirmation.
    """
    client_ip = req.client.host
    PAID_USERS.add(client_ip)
    return {
        "status": "success", 
        "message": "Successfully upgraded to Pro! Your daily limit has been removed."
    }

# To run this:
# 1. Install fastapi and uvicorn: pip install fastapi uvicorn
# 2. Run the file: uvicorn app_main:app --reload

