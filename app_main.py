import os
import httpx
from datetime import date
from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "super-secret-key-change-this"))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# CONFIGURATION
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
BASE_URL = os.environ.get("BASE_URL", "https://web-production-b74c4.up.railway.app")

# STORAGE
USERS_DB = {}  
PAID_USERS = set()  

class ContractRequest(BaseModel):
    contract_text: str

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

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuditGuard AI</title>
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#38bdf8">
    <meta name="mobile-web-app-capable" content="yes">
    <style>
        body { font-family: sans-serif; background: #0b0e11; color: white; display: flex; justify-content: center; padding: 20px; }
        .card { width: 100%; max-width: 450px; background: #161a1e; padding: 25px; border-radius: 12px; border: 1px solid #334155; }
        h1 { color: #38bdf8; margin-bottom: 15px; }
        p { color: #94a3b8; font-size: 14px; }
        textarea { width: 100%; height: 150px; background: #0b0e11; color: #f8fafc; border: 1px solid #334155; border-radius: 8px; padding: 12px; resize: none; margin-bottom: 15px; }
        button { width: 100%; padding: 12px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; margin-bottom: 10px; }
        .btn-analyze { background: #0284c7; color: white; }
        .btn-pro { background: #16a34a; color: white; }
        #result { margin-top: 20px; padding: 15px; border-radius: 8px; display: none; background: #0b0e11; border-left: 4px solid #38bdf8; }
        .auth-box { margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #334155; }
        .auth-box input { width: 100%; padding: 10px; margin-bottom: 8px; background: #0b0e11; border: 1px solid #334155; color: white; border-radius: 6px; }
        .auth-row { display: flex; gap: 8px; }
        .auth-row button { background: #334155; color: white; }
    </style>
</head>
<body>
    <div class="card">
        <h1>AuditGuard AI</h1>
        
        <div class="auth-box">
            <p>Account Access (Sync across devices):</p>
            <input type="email" id="authEmail" placeholder="Enter email...">
            <input type="password" id="authPassword" placeholder="Enter password...">
            <div class="auth-row">
                <button onclick="handleAuth('signup')">Sign Up</button>
                <button onclick="handleAuth('login')">Log In</button>
            </div>
            <div id="authStatus" style="font-size: 12px; color: #38bdf8; margin-top: 5px;"></div>
        </div>

        <p>Paste your contract text below for an instant risk evaluation.</p>
        <textarea id="contractInput" placeholder="Paste contract text here..."></textarea>
        <button class="btn-analyze" onclick="submitAudit()">Analyze Contract</button>
        <button class="btn-pro" onclick="upgradeAccount()">Upgrade to Pro (Remove Limits)</button>
        <div id="result"></div>
    </div>

    <script>
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/service-worker.js');
            });
        }

        async function handleAuth(action) {
            const email = document.getElementById('authEmail').value;
            const password = document.getElementById('authPassword').value;
            const statusEl = document.getElementById('authStatus');
            
            const formData = new URLSearchParams();
            formData.append('email', email);
            formData.append('password', password);

            try {
                const res = await fetch('/' + action, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData
                });
                const data = await res.json();
                if (res.ok) {
                    statusEl.style.color = '#16a34a';
                    statusEl.innerText = data.message;
                } else {
                    statusEl.style.color = '#ef4444';
                    statusEl.innerText = data.detail || 'Authentication failed';
                }
            } catch (err) {
                statusEl.style.color = '#ef4444';
                statusEl.innerText = 'Network error during auth';
            }
        }

        async function submitAudit() {
            const text = document.getElementById('contractInput').value;
            const resDiv = document.getElementById('result');
            resDiv.style.display = 'block';
            resDiv.innerHTML = 'Analyzing contract...';
            
            try {
                const res = await fetch('/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ contract_text: text })
                });
                const data = await res.json();
                if (res.ok) {
                    resDiv.innerHTML = `<strong>Status:</strong> ${data.success ? 'Success' : 'Failed'}<br><strong>Trials Used:</strong> ${data.trials_used}<br><span style="color: #38bdf8">${data.analysis.details}</span>`;
                } else {
                    resDiv.innerHTML = `<span style="color: #ef4444">${data.detail}</span><br><button class="btn-pro" onclick="upgradeAccount()">Upgrade to Continue</button>`;
                }
            } catch (err) {
                resDiv.innerHTML = '<span style="color: #ef4444">Error connecting to server.</span>';
            }
        }

        async function upgradeAccount() {
            const res = await fetch('/upgrade', { method: 'POST' });
            const data = await res.json();
            if (data.authorization_url) {
                window.location.href = data.authorization_url;
            } else {
                alert('Unable to start payment. Check your internet or Paystack keys.');
            }
        }
    </script>
</body>
</html>
    """

@app.get("/manifest.json")
async def get_manifest():
    return FileResponse("manifest.json")

@app.get("/service-worker.js")
async def get_sw():
    return FileResponse("service-worker.js")

@app.post("/signup")
async def signup(request: Request, email: str = Form(...), password: str = Form(...)):
    if email in USERS_DB:
        raise HTTPException(status_code=400, detail="Email already registered")
    USERS_DB[email] = {
        "password_hash": pwd_context.hash(password),
        "is_paid": False
    }
    request.session["user"] = email
    return {"message": "Account created successfully"}

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = USERS_DB.get(email)
    if not user or not pwd_context.verify(password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    request.session["user"] = email
    return {"message": "Logged in successfully"}

@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return {"message": "Logged out successfully"}

@app.post("/audit")
async def audit_contract(request: Request, response: Response, contract: ContractRequest):
    user_email = request.session.get("user")
    
    if user_email and user_email in USERS_DB and USERS_DB[user_email]["is_paid"]:
        analysis = analyze_contract_liability(contract.contract_text)
        return {"success": True, "trials_used": "unlimited", "analysis": analysis}
    
    client_ip = request.client.host
    if client_ip in PAID_USERS:
        analysis = analyze_contract_liability(contract.contract_text)
        return {"success": True, "trials_used": "unlimited", "analysis": analysis}

    trials_cookie = request.cookies.get("trials", "0")
    try:
        trials = int(trials_cookie)
    except ValueError:
        trials = 0

    if trials >= 3:
        raise HTTPException(
            status_code=403,
            detail="Free trial limit reached (3/3). Please log in or upgrade to continue."
        )

    new_trials = trials + 1
    response.set_cookie(key="trials", value=str(new_trials))
    
    analysis = analyze_contract_liability(contract.contract_text)
    return {
        "success": True,
        "trials_used": new_trials,
        "analysis": analysis
    }

@app.post("/upgrade")
async def upgrade(request: Request):
    client_ip = request.client.host
    user_email = request.session.get("user", f"user_{client_ip.replace('.', '_')}@auditguard.com")
    
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.paystack.co/transaction/initialize",
            json={
                "email": user_email,
                "amount": "50000",
                "currency": "KES",
                "callback_url": f"{BASE_URL}/verify",
                "metadata": {"ip": client_ip, "email": user_email}
            },
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        )
    data = res.json()
    return data.get("data") if data.get("status") else {"error": "failed"}

@app.get("/verify")
async def verify(reference: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        )
    data = res.json()
    if data.get("data") and data.get("data")["status"] == "success":
        metadata = data["data"].get("metadata", {})
        user_email = metadata.get("email")
        if user_email and user_email in USERS_DB:
            USERS_DB[user_email]["is_paid"] = True
        
        client_ip = metadata.get("ip")
        if client_ip:
            PAID_USERS.add(client_ip)
            
        return HTMLResponse("<h1>Upgrade Successful!</h1><p>You now have unlimited access across devices.</p><a href='/'>Go back</a>")
    return HTMLResponse("<h1>Payment Failed</h1><a href='/'>Try again</a>")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
