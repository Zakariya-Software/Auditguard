import os
import httpx
import hashlib
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "super-secret-key-change-this"))

# CONFIGURATION
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://web-production-b74c4.up.railway.app")

# PERSISTENT DATABASE SETUP (SQLite)
DB_FILE = "auditguard.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            is_paid INTEGER NOT NULL DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT NOT NULL,
            date TEXT NOT NULL,
            snippet TEXT NOT NULL,
            full_text TEXT NOT NULL,
            risk TEXT NOT NULL,
            details TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class ContractRequest(BaseModel):
    contract_text: str

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
    return salt.hex() + "." + pwd_hash.hex()

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
        <title>AuditGuard AI - Contract Risk Analysis</title>
        <link rel="manifest" href="/manifest.json">
        <meta name="theme-color" content="#090a0f">
        <meta name="mobile-web-app-capable" content="yes">
        <style>
            * { box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
                background: radial-gradient(circle at 50% 0%, #1f1315 0%, #090a0f 70%); 
                color: #f8fafc; 
                display: flex; 
                flex-direction: column;
                min-height: 100vh; 
                margin: 0; 
                padding: 16px; 
            }
            .app-container { 
                width: 100%; 
                flex: 1;
                display: flex;
                flex-direction: column;
                background: rgba(15, 12, 14, 0.9); 
                padding: 20px; 
                border-radius: 16px; 
                border: 1px solid rgba(239, 68, 68, 0.15); 
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.8); 
            }
            .header-row { 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                margin-bottom: 16px; 
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                padding-bottom: 12px;
            }
            .header-left {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .menu-btn {
                background: none;
                border: none;
                color: #f8fafc;
                font-size: 1.4rem;
                cursor: pointer;
                padding: 0;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            h1 { 
                font-size: 1.3rem; 
                font-weight: 800; 
                margin: 0; 
                background: linear-gradient(135deg, #ffffff 30%, #fca5a5 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                letter-spacing: -0.02em;
            }
            
            /* Sidebar Drawer Styles */
            .sidebar-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(4px);
                z-index: 999;
                display: none;
                opacity: 0;
                transition: opacity 0.3s ease;
            }
            .sidebar-overlay.active {
                display: block;
                opacity: 1;
            }
            .sidebar {
                position: fixed;
                top: 0;
                left: -300px;
                width: 300px;
                height: 100%;
                background: #120d0f;
                border-right: 1px solid rgba(239, 68, 68, 0.2);
                z-index: 1000;
                display: flex;
                flex-direction: column;
                transition: left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                box-shadow: 10px 0 30px rgba(0, 0, 0, 0.9);
                padding: 20px;
                overflow-y: auto;
            }
            .sidebar.active {
                left: 0;
            }
            .sidebar-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                padding-bottom: 12px;
            }
            .sidebar-header h2 {
                font-size: 1.1rem;
                margin: 0;
                color: #fca5a5;
            }
            .close-sidebar {
                background: none;
                border: none;
                color: #94a3b8;
                font-size: 1.2rem;
                cursor: pointer;
            }
            .profile-section {
                background: rgba(239, 68, 68, 0.08);
                border: 1px solid rgba(239, 68, 68, 0.2);
                border-radius: 12px;
                padding: 14px;
                margin-bottom: 20px;
            }
            .profile-section input {
                width: 100%;
                padding: 10px;
                background: #090a0f;
                border: 1px solid #3f1d22;
                border-radius: 8px;
                color: #f8fafc;
                font-size: 0.8rem;
                margin-bottom: 8px;
                outline: none;
            }
            .profile-section input:focus {
                border-color: #ef4444;
            }
            .profile-row {
                display: flex;
                gap: 6px;
                margin-top: 6px;
            }
            .profile-row button {
                flex: 1;
                padding: 8px;
                border-radius: 8px;
                font-size: 0.75rem;
                font-weight: 600;
                cursor: pointer;
                border: none;
            }
            .btn-signup { background: #332729; color: #cbd5e1; }
            .btn-login { background: #ef4444; color: white; }
            .history-container {
                flex: 1;
                display: flex;
                flex-direction: column;
            }
            .history-title {
                font-size: 0.85rem;
                font-weight: 700;
                color: #cbd5e1;
                margin-bottom: 10px;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }
            .history-list {
                display: flex;
                flex-direction: column;
                gap: 8px;
                max-height: calc(100vh - 280px);
                overflow-y: auto;
            }
            .history-item {
                background: rgba(22, 15, 17, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 8px;
                padding: 10px;
                cursor: pointer;
                transition: all 0.2s;
            }
            .history-item:hover {
                border-color: rgba(239, 68, 68, 0.4);
                background: rgba(30, 20, 23, 0.9);
            }
            .history-item-header {
                display: flex;
                justify-content: space-between;
                font-size: 0.75rem;
                color: #94a3b8;
                margin-bottom: 4px;
            }
            .history-item-snippet {
                font-size: 0.8rem;
                color: #e2e8f0;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            #authStatus { font-size: 0.75rem; margin-top: 6px; text-align: center; font-weight: 500; }

            .instruction-text { 
                font-size: 0.85rem; 
                color: #94a3b8; 
                margin-bottom: 8px; 
                font-weight: 400; 
            }
            .workspace {
                flex: 1;
                display: flex;
                flex-direction: column;
            }
            textarea { 
                width: 100%; 
                flex: 1;
                min-height: 280px; 
                background: rgba(14, 11, 13, 0.85); 
                color: #f8fafc; 
                border: 1px solid #32191d; 
                border-radius: 12px; 
                padding: 14px; 
                font-size: 0.9rem; 
                resize: none; 
                outline: none; 
                margin-bottom: 16px; 
                line-height: 1.5;
            }
            textarea:focus { 
                border-color: #ef4444; 
                box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15);
            }
            textarea::placeholder { color: #4b5563; }
            .footer-actions {
                margin-top: auto;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            button.action-btn { 
                width: 100%; 
                padding: 14px; 
                border-radius: 12px; 
                font-weight: 700; 
                font-size: 0.9rem; 
                cursor: pointer; 
                border: none; 
                transition: all 0.2s ease; 
            }
            .btn-analyze { 
                background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%); 
                color: white; 
                box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4); 
            }
            .btn-analyze:hover { 
                opacity: 0.95;
                box-shadow: 0 6px 20px rgba(239, 68, 68, 0.6); 
            }
            .btn-pro { 
                background: rgba(28, 20, 22, 0.8); 
                color: #fca5a5; 
                border: 1px solid rgba(239, 68, 68, 0.25); 
            }
            .btn-pro:hover { 
                background: rgba(43, 27, 30, 0.9); 
                color: #ffffff;
            }
            #result { 
                margin-top: 12px; 
                padding: 14px; 
                border-radius: 10px; 
                font-size: 0.85rem; 
                display: none; 
                background: rgba(22, 15, 17, 0.95); 
                border-left: 4px solid #ef4444; 
                border: 1px solid rgba(239, 68, 68, 0.2);
                line-height: 1.5;
            }
        </style>
    </head>
    <body>
        <!-- Sidebar Menu Drawer -->
        <div id="sidebarOverlay" class="sidebar-overlay" onclick="toggleSidebar()"></div>
        <div id="sidebar" class="sidebar">
            <div class="sidebar-header">
                <h2>Menu & Profile</h2>
                <button class="close-sidebar" onclick="toggleSidebar()">✕</button>
            </div>

            <!-- Profile / Auth Section on Top -->
            <div class="profile-section" id="profileSection">
                <p id="userStatusText" style="margin-bottom: 8px; color: #cbd5e1; font-size: 0.75rem; font-weight: 600;">Account / Profile</p>
                <div id="authInputs">
                    <input type="email" id="authEmail" placeholder="Email address...">
                    <input type="password" id="authPassword" placeholder="Password...">
                    <div class="profile-row">
                        <button class="btn-signup" onclick="handleAuth('signup')">Sign Up</button>
                        <button class="btn-login" onclick="handleAuth('login')">Log In</button>
                    </div>
                </div>
                <div id="loggedInView" style="display: none;">
                    <p id="currentUserEmail" style="font-size: 0.8rem; color: #fca5a5; margin-bottom: 8px; word-break: break-all;"></p>
                    <button class="btn-login" style="width: 100%; padding: 8px;" onclick="handleLogout()">Log Out</button>
                </div>
                <div id="authStatus"></div>
            </div>

            <!-- History Section Down Below (Visible only for Paid / Pro Users) -->
            <div class="history-container">
                <div class="history-title">Analysis History (<span id="historyCount">0</span>)</div>
                <div id="historyList" class="history-list">
                    <p style="font-size: 0.75rem; color: #64748b;">Upgrade to Pro to view analysis history.</p>
                </div>
            </div>
        </div>

        <div class="app-container">
            <div class="header-row">
                <div class="header-left">
                    <button class="menu-btn" onclick="toggleSidebar()">☰</button>
                    <h1>AuditGuard AI</h1>
                </div>
            </div>

            <!-- Main Contract Analysis Workspace -->
            <div class="workspace">
                <p class="instruction-text">Paste your contract text below for an instant risk evaluation.</p>
                <textarea id="contractInput" placeholder="Paste contract text here..."></textarea>
            </div>

            <!-- Footer Action Buttons -->
            <div class="footer-actions">
                <button class="action-btn btn-analyze" onclick="submitAudit()">Analyze Contract</button>
                <button class="action-btn btn-pro" onclick="upgradeAccount()">Upgrade to Pro (Remove Limits)</button>
            </div>
            
            <div id="result"></div>
        </div>

        <script>
            function toggleSidebar() {
                const sidebar = document.getElementById('sidebar');
                const overlay = document.getElementById('sidebarOverlay');
                sidebar.classList.toggle('active');
                overlay.classList.toggle('active');
                if (sidebar.classList.contains('active')) {
                    loadHistory();
                }
            }

            async function loadHistory() {
                try {
                    const res = await fetch('/history');
                    const data = await res.json();
                    const listEl = document.getElementById('historyList');
                    const countEl = document.getElementById('historyCount');
                    
                    countEl.innerText = data.history.length;
                    
                    if (data.history.length === 0) {
                        listEl.innerHTML = '<p style="font-size: 0.75rem; color: #64748b;">Upgrade to Pro to view analysis history.</p>';
                        return;
                    }
                    
                    listEl.innerHTML = '';
                    data.history.forEach((item) => {
                        const div = document.createElement('div');
                        div.className = 'history-item';
                        div.innerHTML = `
                            <div class="history-item-header">
                                <span>${item.date}</span>
                                <span style="color: ${item.risk === 'CRITICAL' ? '#ef4444' : '#4ade80'}">${item.risk}</span>
                            </div>
                            <div class="history-item-snippet">${item.snippet}</div>
                        `;
                        div.onclick = () => {
                            document.getElementById('contractInput').value = item.full_text;
                            const resDiv = document.getElementById('result');
                            resDiv.style.display = 'block';
                            resDiv.innerHTML = `<strong>Loaded from History:</strong><br><strong>Risk Score:</strong> ${item.risk}<br><strong>Details:</strong> ${item.details}`;
                            toggleSidebar();
                        };
                        listEl.appendChild(div);
                    });
                } catch (err) {
                    console.error('Failed to load history');
                }
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
                        setTimeout(() => { 
                            checkSession();
                            loadHistory();
                            statusEl.innerText = '';
                        }, 1000);
                    } else {
                        statusEl.style.color = '#ef4444';
                        statusEl.innerText = data.detail || 'Authentication failed';
                    }
                } catch (err) {
                    statusEl.style.color = '#ef4444';
                    statusEl.innerText = 'Network error during auth';
                }
            }

            async function handleLogout() {
                try {
                    await fetch('/logout', { method: 'POST' });
                    checkSession();
                    loadHistory();
                } catch (err) {
                    console.error('Logout error');
                }
            }

            async function checkSession() {
                try {
                    const res = await fetch('/session-info');
                    const data = await res.json();
                    if (data.logged_in) {
                        document.getElementById('authInputs').style.display = 'none';
                        document.getElementById('loggedInView').style.display = 'block';
                        document.getElementById('currentUserEmail').innerText = data.email;
                        document.getElementById('userStatusText').innerText = 'Signed In Profile';
                    } else {
                        document.getElementById('authInputs').style.display = 'block';
                        document.getElementById('loggedInView').style.display = 'none';
                        document.getElementById('userStatusText').innerText = 'Account / Profile';
                    }
                } catch (err) {
                    console.error('Session check failed');
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
                        toggleSidebar();
                        document.getElementById('authEmail').focus();
                    }
                } catch (err) {
                    alert('Network error. Please try again.');
                }
            }

            // Initialize session info on load
            checkSession();
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

@app.get("/session-info")
async def session_info(request: Request):
    user_email = request.session.get("user")
    if user_email:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE email = ?", (user_email,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"logged_in": True, "email": row[0]}
    return {"logged_in": False}

@app.get("/history")
async def get_history(request: Request):
    user_email = request.session.get("user")
    if not user_email:
        return {"history": []}
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT is_paid FROM users WHERE email = ?", (user_email,))
    row = cursor.fetchone()
    
    # If the user has not paid, do not return history items
    if not row or row[0] != 1:
        conn.close()
        return {"history": []}
    
    cursor.execute("SELECT date, snippet, full_text, risk, details FROM history WHERE identifier = ? ORDER BY id DESC", (user_email,))
    rows = cursor.fetchall()
    conn.close()
    
    history_list = []
    for row in rows:
        history_list.append({
            "date": row[0],
            "snippet": row[1],
            "full_text": row[2],
            "risk": row[3],
            "details": row[4]
        })
    return {"history": history_list}

@app.post("/signup")
async def signup(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    
    pwd_hash = hash_password(password)
    cursor.execute("INSERT INTO users (email, password_hash, is_paid) VALUES (?, ?, 0)", (email, pwd_hash))
    conn.commit()
    conn.close()
    
    request.session["user"] = email
    return {"message": "Account created successfully"}

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not verify_password(password, row[0]):
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
    analysis = analyze_contract_liability(contract.contract_text)
    
    date_str = datetime.now().strftime("%b %d, %H:%M")
    snippet = contract.contract_text[:60] + "..." if len(contract.contract_text) > 60 else contract.contract_text
    identifier = user_email if user_email else request.client.host

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO history (identifier, date, snippet, full_text, risk, details) VALUES (?, ?, ?, ?, ?, ?)",
        (identifier, date_str, snippet, contract.contract_text, analysis["risk_score"], analysis["details"])
    )
    conn.commit()

    if user_email:
        cursor.execute("SELECT is_paid FROM users WHERE email = ?", (user_email,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] == 1:
            return {"success": True, "trials_used": "unlimited", "analysis": analysis}
    else:
        conn.close()

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
    
    return {
        "success": True,
        "trials_used": new_trials,
        "analysis": analysis
    }

@app.post("/upgrade")
async def upgrade(request: Request):
    user_email = request.session.get("user")
    
    if not user_email:
        raise HTTPException(
            status_code=401,
            detail="Please sign up or log in first before upgrading to Pro."
        )

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = ?", (user_email,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(
            status_code=401,
            detail="Please sign up or log in first before upgrading to Pro."
        )
    conn.close()

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.paystack.co/transaction/initialize",
            json={
                "email": user_email,
                "amount": 50000,
                "currency": "KES",
                "callback_url": f"{BASE_URL}/verify",
                "metadata": {"email": user_email}
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
        if user_email:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_paid = 1 WHERE email = ?", (user_email,))
            conn.commit()
            conn.close()
            
        return HTMLResponse("<h1>Upgrade Successful!</h1><p>Your Pro status is permanently linked to your account database.</p><a href='/'>Return to AuditGuard</a>")
    return HTMLResponse("<h1>Payment Failed</h1><p>Please try again.</p><a href='/'>Return to AuditGuard</a>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
