import os
import httpx
from datetime import date
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

# --- CONFIGURATION ---
# We will set these in the Railway "Variables" tab for security
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "your_test_key_here")
BASE_URL = os.environ.get("BASE_URL", "https://web-production-b74c4.up.railway.app")

USAGE_COUNTS = {}  
PAID_USERS = set() 

class ContractRequest(BaseModel):
    contract_text: str

def analyze_contract_liability(text: str):
    risk_score = "LOW"
    if any(word in text.lower() for word in ["liable", "indemnify", "breach", "terminate"]):
        risk_score = "CRITICAL"
    return {
        "risk_score": risk_score,
        "details": "High risk clauses found regarding liability." if risk_score == "CRITICAL" else "No immediate high-risk clauses detected."
    }

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AuditGuard</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0b0e11; color: white; display: flex; justify-content: center; padding: 20px; }
            .card { width: 100%; max-width: 450px; background: #161a1e; padding: 25px; border-radius: 12px; border: 1px solid #334155; }
            h1 { color: #38bdf8; margin-bottom: 5px; }
            textarea { width: 100%; height: 150px; background: #0b0e11; color: #f8fafc; border: 1px solid #334155; border-radius: 8px; padding: 12px; margin: 15px 0; box-sizing: border-box; font-size: 14px; }
            button { width: 100%; padding: 14px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.3s; margin-bottom: 10px; }
            .btn-analyze { background: #0284c7; color: white; }
            .btn-analyze:hover { background: #0369a1; }
            .btn-pro { background: #16a34a; color: white; }
            #result { margin-top: 20px; padding: 15px; border-radius: 8px; display: none; background: #1e293b; border-left: 5px solid #38bdf8; line-height: 1.5; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>AuditGuard</h1>
            <p style="color: #94a3b8; font-size: 14px;">Instant AI risk evaluation for your contracts.</p>
            <textarea id="contractInput" placeholder="Paste contract text here..."></textarea>
            <button class="btn-analyze" onclick="submitAudit()">Analyze Contract</button>
            <button class="btn-pro" onclick="upgradeAccount()">Upgrade to Pro (Remove Limits)</button>
            <div id="result" id="resultBox"></div>
        </div>

        <script>
            async function submitAudit() {
                const text = document.getElementById('contractInput').value;
                const resDiv = document.getElementById('result');
                if (!text) return alert('Please paste a contract.');

                resDiv.style.display = 'block';
                resDiv.innerHTML = '<em>AI is scanning clauses...</em>';

                const response = await fetch('/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ contract_text: text })
                });
                const data = await response.json();
                
                if (data.error) {
                    resDiv.innerHTML = `<span style="color: #fb7185">${data.error}</span>`;
                } else {
                    resDiv.innerHTML = `<strong>Status: ${data.risk_score}</strong><br>${data.details}`;
                    resDiv.style.borderLeftColor = data.risk_score === 'CRITICAL' ? '#ef4444' : '#38bdf8';
                }
            }

            async function upgradeAccount() {
                const res = await fetch('/upgrade', { method: 'POST' });
                const data = await res.json();
                if (data.authorization_url) window.location.href = data.authorization_url;
                else alert('Checkout failed to load.');
            }
        </script>
    </body>
    </html>
    """

@app.post("/audit")
async def audit(request: ContractRequest, req: Request):
    client_ip = req.client.host
    today = str(date.today())
    
    if client_ip in PAID_USERS:
        return analyze_contract_liability(request.contract_text)

    key = f"{client_ip}_{today}"
    count = USAGE_COUNTS.get(key, 0)

    if count >= 3:
        return {"error": "Daily limit reached (3/3). Please upgrade to Pro for unlimited scans!"}

    USAGE_COUNTS[key] = count + 1
    return analyze_contract_liability(request.contract_text)

@app.post("/upgrade")
async def upgrade(req: Request):
    client_ip = req.client.host
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.paystack.co/transaction/initialize",
            json={
                "email": f"user_{client_ip.replace('.', '_')}@auditguard.app",
                "amount": "500000", # Set your price here (in subunits)
                "callback_url": f"{BASE_URL}/verify",
                "metadata": {"ip": client_ip}
            },
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        )
        return res.json()["data"] if res.json().get("status") else {"error": "failed"}

@app.get("/verify")
async def verify(reference: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        )
        data = res.json()
        if data.get("status") and data["data"]["status"] == "success":
            ip = data["data"]["metadata"]["ip"]
            PAID_USERS.add(ip)
            return HTMLResponse("<h1>Upgrade Successful!</h1><p>You now have unlimited access.</p><a href='/'>Return to AuditGuard</a>")
    return HTMLResponse("<h1>Payment failed</h1>")

if __name__ == "__main__":
    import uvicorn
    # CRITICAL: Railway provides the port via an environment variable
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
