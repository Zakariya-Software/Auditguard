import os
import httpx
from datetime import date
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

# Register SessionMiddleware right below app initialization to prevent request.session crashes
app.add_middleware(SessionMiddleware, secret_key="my_super_secret_random_key_12345")

# --- CONFIGURATION ---
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
BASE_URL = os.environ.get("BASE_URL", "https://web-production-b74c4.up.railway.app")

# --- IN-MEMORY STORAGE ---
USAGE_COUNTS = {}
PAID_USERS = set()

class ContractRequest(BaseModel):
    contract_text: str

# --- MOCK AI ANALYSIS LOGIC ---
def analyze_contract_liability(text: str):
    text_lower = text.lower()
    risk_score = "LOW"
    details = "The AI found no immediate high-risk clauses. This contract appears standard."
    
    risky_words = ["liable", "indemnify", "breach", "terminate", "penalty", "interest"]
    found = [word for word in risky_words if word in text_lower]
    
    if len(found) > 0:
        risk_score = "CRITICAL"
        details = f"Warning: Potential high-risk clauses found regarding: {', '.join(found)}. Review these carefully."
        
    return {"risk_score": risk_score, "details": details}

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuditGuard AI</title>
    
    <!-- PWA Meta Tags -->
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#38bdf8">
    <meta name="mobile-web-app-capable" content="yes">
    
    <style>
        body { font-family: sans-serif; background: #0b0e11; color: white; display: flex; justify-content: center; padding: 20px; }
        .card { width: 100%; max-width: 450px; background: #161a1e; padding: 25px; border-radius: 12px; border: 1px solid #38bdf8; margin-bottom: 5px; }
        h1 { color: #38bdf8; margin-bottom: 5px; }
        p { color: #94a3b8; font-size: 14px; }
        textarea { width: 100%; height: 150px; background: #0b0e11; color: #f8fafc; border: 1px solid #334155; border-radius: 8px; padding: 10px; font-size: 14px; }
        button { width: 100%; padding: 14px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; margin-top: 10px; }
        .btn-analyze { background: #0284c7; color: white; }
        .btn-pro { background: #16a34a; color: white; }
        #result { margin-top: 20px; padding: 15px; border-radius: 8px; display: none; background: #1e293b; border-left: 4px solid #38bdf8; }
    </style>
</head>
<body>
    <div class="card">
        <h1>AuditGuard</h1>
        <p>Paste your contract text below for an instant risk evaluation.</p>
        <textarea id="contractInput" placeholder="Paste contract text here..."></textarea>
        <button class="btn-analyze" onclick="submitAudit()">Analyze Contract</button>
        <button class="btn-pro" onclick="upgradeAccount()">Upgrade to Pro (Remove Limits)</button>
        <div id="result"></div>
    </div>

    <script>
        // Register PWA Service Worker
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/service-worker.js');
            });
        }

        async function submitAudit() {
            const text = document.getElementById('contractInput').value;
            const resDiv = document.getElementById('result');
            if (!text) return alert('Please paste a contract.');

            resDiv.style.display = 'block';
            resDiv.innerHTML = '<p>AI is scanning clauses...</p>';

            const response = await fetch('/audit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ contract_text: text })
            });
            const data = await response.json();

            if (response.status === 403) {
                resDiv.innerHTML = `<span style="color: #fb7185">${data.detail.error}</span><br><a href="${data.detail.redirect}" target="_blank" style="color: #38bdf8; font-weight: bold;">Click here to pay and unlock unlimited access</a>`;
            } else if (data.error) {
                resDiv.innerHTML = `<span style="color: #fb7185">${data.error}</span>`;
            } else {
                resDiv.innerHTML = `<strong>Status: ${data.analysis.risk_score}</strong><br>${data.analysis.details}`;
                resDiv.style.borderLeftColor = data.analysis.risk_score === 'CRITICAL' ? '#ef4444' : '#38bdf8';
            }
        }

        async function upgradeAccount() {
            const res = await fetch('/upgrade', { method: 'POST' });
            const data = await res.json();
            if (data.authorization_url) window.location.href = data.authorization_url;
            else alert('Unable to start payment. Check your internet.');
        }
    </script>
</body>
</html>
    """

# --- PWA FILE SERVERS ---
@app.get("/manifest.json")
async def get_manifest():
    return FileResponse("manifest.json")

@app.get("/service-worker.js")
async def get_sw():
    return FileResponse("service-worker.js")

# --- BACKEND LOGIC ---
@app.post("/audit")
async def audit_contract(request: Request, contract: ContractRequest):
    # Get current trial count from session, default to 0
    trials = request.session.get("trials", 0)

    # If user has reached 3 trials, block and return Paystack redirect
    if trials >= 3:
        raise HTTPException(
            status_code=403,
            detail={"error": "Trial limit reached", "redirect": "https://checkout.paystack.com/your-link"}
        )

    # Increment trial count for this session
    request.session["trials"] = trials + 1
    
    # Run the contract evaluation logic
    analysis = analyze_contract_liability(contract.contract_text)
    
    return {
        "success": True, 
        "trials_used": request.session["trials"],
        "analysis": analysis
    }

@app.post("/upgrade")
async def upgrade(req: Request):
    client_ip = req.client.host
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.paystack.co/transaction/initialize",
            json={
                "email": f"user_{client_ip.replace('.', '_')}@auditguard.com",
                "amount": "500000", # 500,000 subunits = 5,000 KES
                "callback_url": f"{BASE_URL}/verify",
                "metadata": {"ip": client_ip}
            },
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        )
    data = res.json()
    return data["data"] if data.get("status") else {"error": "failed"}

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
        return HTMLResponse("<h1>Upgrade Successful!</h1><p>You now have unlimited access.</p><a href='/'>Go back</a>")
    return HTMLResponse("<h1>Payment Failed</h1><a href='/'>Try again</a>")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

