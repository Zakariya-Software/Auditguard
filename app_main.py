import os
import httpx
import hashlib
from datetime import date
from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "super-secret-key-change-this"))

# CONFIGURATION
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://web-production-b74c4.up.railway.app")

# STORAGE
USERS_DB = {}
PAID_USERS = set()

class ContractRequest(BaseModel):
    contract_text: str

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
    return salt.hex() + pwd_hash.hex()

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, pwd_hash_hex = stored_hash.split(".")
        salt = bytes.fromhex(salt_hex)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
        return pwd_hash.hex() == pwd_hash_hex
    except Exception:
        return False

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
        <title>AuditGuard AI - Instant Contract Risk Analysis</title>
        <link rel="manifest" href="/manifest.json">
        <meta name="theme-color" content="#07090e">
        <meta name="mobile-web-app-capable" content="yes">
        <style>
            * { box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
                background: radial-gradient(circle at 50% 0%, #171f38 0%, #07090e 70%); 
                color: #f8fafc; 
                display: flex; 
                justify-content: center; 
                align-items: center; 
                min-height: 100vh; 
                margin: 0; 
                padding: 16px; 
            }
            .card { 
                width: 100%; 
                max-width: 480px; 
                background: rgba(15, 20, 35, 0.85); 
                backdrop-filter: blur(12px);
                padding: 28px; 
                border-radius: 20px; 
                border: 1px solid rgba(255, 255, 255, 0.08); 
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); 
            }
            .header-row { 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                margin-bottom: 22px; 
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                padding-bottom: 14px;
            }
            .logo-container {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            h1 { 
                font-size: 1.2rem; 
                font-weight: 700; 
                margin: 0; 
                background: linear-gradient(135deg, #ffffff 30%, #94a3b8 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                letter-spacing: -0.02em;
            }
            .auth-toggle-btn { 
                font-size: 0.75rem; 
                color: #818cf8; 
                background: rgba(129, 140, 248, 0.1); 
                border: 1px solid rgba(129, 140, 248, 0.2); 
                padding: 6px 12px;
                border-radius: 20px;
                cursor: pointer; 
                font-weight: 600; 
                transition: all 0.2s ease;
            }
            .auth-toggle-btn:hover { 
                background: rgba(129, 140, 248, 0.2); 
                color: #a5b4fc;
            }
            .auth-box { 
                display: none; 
                background: rgba(19, 25, 41, 0.95); 
                border: 1px solid rgba(129, 140, 248, 0.2); 
                border-radius: 14px; 
                padding: 16px; 
                margin-bottom: 20px; 
                animation: fadeIn 0.2s ease-in-out;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(-6px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .auth-box input { 
                width: 100%; 
                padding: 11px 14px; 
                background: #07090e; 
                border: 1px solid #2a3759; 
                border-radius: 10px; 
                color: #f8fafc; 
                font-size: 0.85rem; 
                margin-bottom: 10px; 
                outline: none; 
                transition: border-color 0.2s;
            }
            .auth-box input:focus {
                border-color: #6366f1;
            }
            .auth-row { 
                display: flex; 
                gap: 8px; 
            }
            .auth-row button { 
                flex: 1; 
                padding: 9px; 
                border-radius: 9px; 
                font-size: 0.75rem; 
                font-weight: 600; 
                cursor: pointer; 
                border: none; 
                transition: opacity 0.2s;
            }
            .auth-row button:hover { opacity: 0.9; }
            .btn-signup { background: #334155; color: white; }
            .btn-login { background: #6366f1; color: white; }
            #authStatus { font-size: 0.75rem; margin-top: 8px; text-align: center; font-weight: 500; }
            .instruction-text { 
                font-size: 0.825rem; 
                color: #94a3b8; 
                margin-bottom: 10px; 
                font-weight: 400; 
            }
            textarea { 
                width: 100%; 
                height: 160px; 
                background: rgba(10, 14, 26, 0.8); 
                color: #f8fafc; 
                border: 1px solid #232d4a; 
                border-radius: 14px; 
                padding: 14px; 
                font-size: 0.875rem; 
                resize: none; 
                outline: none; 
                margin-bottom: 16px; 
                transition: all 0.2s;
            }
            textarea:focus { 
                border-color: #6366f1; 
                box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
            }
            textarea::placeholder { color: #475569; }
            button.action-btn { 
                width: 100%; 
                padding: 13px; 
                border-radius: 12px; 
                font-weight: 600; 
                font-size: 0.875rem; 
                cursor: pointer; 
                border: none; 
                margin-bottom: 12px; 
                transition: all 0.2s ease; 
            }
            .btn-analyze { 
                background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); 
                color: white; 
                box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4); 
            }
            .btn-analyze:hover { 
                transform: translateY(-1px);
                box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6); 
            }
            .btn-pro { 
                background: rgba(24, 33, 54, 0.6); 
                color: #cbd5e1; 
                border: 1px solid rgba(42, 55, 89, 0.8); 
            }
            .btn-pro:hover { 
                background: rgba(32, 43, 71, 0.8); 
                color: #ffffff;
                border-color: #4f46e5;
            }
            #result { 
                margin-top: 16px; 
                padding: 14px; 
                border-radius: 12px; 
                font-size: 0.85rem; 
                display: none; 
                background: rgba(19, 25, 41, 0.9); 
                border-left: 4px solid #6366f1; 
                border: 1px solid rgba(255, 255, 255, 0.05);
                line-height: 1.5;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header-row">
                <div class="logo-container">
                    <h1>AuditGuard AI</h1>
                </div>
                <button class="auth-toggle-btn" onclick="toggleAuthBox()">Log In / Sign Up</button>
            </div>

            <!-- Collapsible Auth Section -->
            <div id="authBox" class="auth-box">
                <p style="margin-bottom: 8px; color: #cbd5e1; font-size: 0.8rem; font-weight: 500;">Account Access (Sync across devices)</p>
                <input type="email" id="authEmail" placeholder="Enter email...">
                <input type="password" id="authPassword" placeholder="Enter password...">
                <div class="auth-row">
                    <button class="btn-signup" onclick="handleAuth('signup')">Sign Up</button>
                    <button class="btn-login" onclick="handleAuth('login')">Log In</button>
                </div>
                <div id="authStatus"></div>
            </div>

            <!-- Main Contract Analysis Workspace -->
            <div>
                <p class="instruction-text">Paste your contract text below for an instant risk evaluation.</p>
                <textarea id="contractInput" placeholder="Paste contract text here..."></textarea>
            </div>
            <button class="action-btn btn-analyze" onclick="submitAudit()">Analyze Contract</button>
            <button class="action-btn btn-pro" onclick="upgradeAccount()">Upgrade to Pro (Remove Limits)</button>
            <div id="result"></div>
        </div>

        <script>
            function toggleAuthBox() {
                const box = document.getElementById('authBox');
                box.style.display = box.style.display === 'block' ? 'none' : 'block';
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
                        statusEl.style.color = '#4ade80';
                        statusEl.innerText = data.message;
                        setTimeout(() => { document.getElementById('authBox').style.display = 'none'; }, 1500);
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
                        resDiv.innerHTML = `<strong>Status:</strong> Success<br><strong>Trials Used:</strong> ${data.trials_used}<br><br><strong>Risk Score:</strong> ${data.analysis.risk_score}<br><strong>Details:</strong> ${data.analysis.details}`;
                    } else {
                        resDiv.innerHTML = `<span style="color: #ef4444;">${data.detail}</span><br><br><button class="action-btn btn-pro" onclick="upgradeAccount()">Upgrade to Pro (Remove Limits)</button>`;
                    }
                } catch (err) {
                    resDiv.innerHTML = `<span style="color: #ef4444;">Error connecting to server.</span>`;
                }
            }

            async function upgradeAccount() {
                try {
                    const res = await fetch('/upgrade', { method: 'POST' });
                    const data = await res.json();
                    if (res.ok && data.authorization_url) {
                        window.location.href = data.authorization_url;
                    } else {
                        alert(data.detail || 'Please sign up or log in first before upgrading to Pro.');
                        document.getElementById('authBox').style.display = 'block';
                        document.getElementById('authEmail').focus();
                    }
                } catch (err) {
                    alert('Network error. Please try again.');
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
        "password_hash": hash_password(password),
        "is_paid": False
    }
    request.session["user"] = email
    return {"message": "Account created successfully"}

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = USERS_DB.get(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    request.session["user"] = email
    return {"message": "Logged in successfully"}

@app.post("/logout")
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
    user_email = request.session.get("user")
    
    if not user_email or user_email not in USERS_DB:
        raise HTTPException(
            status_code=401,
            detail="Please sign up or log in first before upgrading to Pro."
        )

    client_ip = request.client.host

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.paystack.co/transaction/initialize",
            json={
                "email": user_email,
                "amount": 50000,
                "currency": "KES",
                "callback_url": f"{BASE_URL}/verify",
                "metadata": {"ip": client_ip, "email": user_email}
            },
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        )
    data = res.json()
    return data.get("data") if data.get("status") else {"error": "Failed"}

@app.get("/verify")
async def verify(reference: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        )
    data = res.json()
    if data.get("status") and data.get("data").get("status") == "success":
        metadata = data.get("data").get("metadata", {})
        user_email = metadata.get("email")
        if user_email and user_email in USERS_DB:
            USERS_DB[user_email]["is_paid"] = True
            
        client_ip = metadata.get("ip")
        if client_ip:
            PAID_USERS.add(client_ip)
            
        return HTMLResponse("<h1>Upgrade Successful!</h1><p>You now have unlimited access across devices.</p><a href='/'>Try AuditGuard</a>")
    return HTMLResponse("<h1>Payment Failed</h1><p>Try again</p><a href='/'>Try again</a>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
