import os
import hashlib
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "super-secret-key-change-this!"))

# CONFIGURATION
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://web-production-b74c4.up.railway.app")

# PERSISTENT DATABASE SETUP (SQLite)
DB_FILE = "auditguard.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            is_paid INTEGER NOT NULL DEFAULT 0,
            trials_used INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    # Safe check in case table already existed without trials_used
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [col[1] for col in cursor.fetchall()]
    if "trials_used" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN trials_used INTEGER NOT NULL DEFAULT 0")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT NOT NULL,
            date TEXT NOT NULL,
            snippet TEXT NOT NULL,
            full_text TEXT NOT NULL,
            risk TEXT NOT NULL,
            details TEXT NOT NULL,
            solutions TEXT NOT NULL
        )
    """)
    
    # Safe check in case history table existed without solutions
    cursor.execute("PRAGMA table_info(history)")
    history_columns = [col[1] for col in cursor.fetchall()]
    if "solutions" not in history_columns:
        cursor.execute("ALTER TABLE history ADD COLUMN solutions TEXT NOT NULL DEFAULT ''")
        
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
    solutions = "No specific remediation required. Standard terms look acceptable."
    
    risky_words = ["liable", "indemnify", "breach", "terminate", "penalty", "interest"]
    found = [word for word in risky_words if word in text_lower]
    
    if len(found) > 0:
        risk_score = "CRITICAL"
        details = f"Warning: Potential high-risk clauses found regarding: {', '.join(found)}."
        solutions = (
            "1. <strong>Termination Notice:</strong> Request a mandatory 14 to 30 days written notice period instead of immediate termination.<br>"
            "2. <strong>Liability Cap:</strong> Limit personal liability to direct damages or cap it at total fees paid.<br>"
            "3. <strong>Penalties:</strong> Remove strict personal legal penalties for accidental equipment loss."
        )
    return {
        "risk_score": risk_score,
        "details": details,
        "solutions": solutions
    }

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audit Guard AI - Contract Risk Analysis</title>
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#07080c">
    <meta name="mobile-web-app-capable" content="yes">
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: radial-gradient(circle at 15% 15%, rgba(244, 63, 94, 0.15) 0%, transparent 40%),
                        radial-gradient(circle at 85% 85%, rgba(59, 130, 246, 0.15) 0%, transparent 40%),
                        radial-gradient(circle at 50% 50%, rgba(16, 185, 129, 0.12) 0%, transparent 50%),
                        #07080c;
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
            background: rgba(13, 13, 18, 0.85);
            backdrop-filter: blur(12px);
            padding: 20px;
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(59, 130, 246, 0.08);
        }
        .header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
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
            background: linear-gradient(135deg, #38bdf8 0%, #34d399 50%, #f43f5e 100%);
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
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(6px);
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
            background: #0d0e14;
            border-right: 1px solid rgba(59, 130, 246, 0.2);
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
            background: linear-gradient(135deg, #38bdf8, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .close-sidebar {
            background: none;
            border: none;
            color: #94a3b8;
            font-size: 1.2rem;
            cursor: pointer;
        }
        .profile-section {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(59, 130, 246, 0.25);
            border-radius: 12px;
            padding: 14px;
            margin-bottom: 20px;
        }
        .profile-section input {
            width: 100%;
            padding: 10px;
            background: #07080c;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            color: #f8fafc;
            font-size: 0.8rem;
            margin-bottom: 8px;
            outline: none;
        }
        .profile-section input:focus {
            border-color: #38bdf8;
            box-shadow: 0 0 2px rgba(56, 189, 248, 0.5);
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
        .btn-signup { background: #f43f5e; color: #cbd5e1; }
        .btn-login { background: linear-gradient(135deg, #38bdf8, #34d399); color: white; }
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
            background: rgba(18, 20, 28, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 8px;
            padding: 10px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .history-item:hover {
            border-color: rgba(56, 189, 248, 0.4);
            background: rgba(24, 28, 38, 0.9);
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
        .workspace {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        .instruction-text {
            font-size: 0.85rem;
            color: #94a3b8;
            margin-bottom: 8px;
            font-weight: 400;
        }
        textarea {
            width: 100%;
            flex: 1;
            min-height: 220px;
            background: rgba(10, 11, 16, 0.9);
            color: #f8fafc;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 14px;
            font-size: 0.9rem;
            resize: none;
            outline: none;
            line-height: 1.5;
        }
        textarea:focus {
            border-color: #38bdf8;
            box-shadow: 0 0 3px rgba(56, 189, 248, 0.5);
        }
        textarea::placeholder { color: #64748b; }
        .footer-actions {
            margin-top: auto;
            display: flex;
            flex-direction: column;
            gap: 10px;
            padding-top: 12px;
        }
        .action-btn {
            width: 100%;
            padding: 14px;
            border-radius: 12px;
            font-size: 0.9rem;
            font-weight: 700;
            cursor: pointer;
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .btn-analyze {
            background: linear-gradient(135deg, #38bdf8 0%, #2563eb 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(56, 189, 248, 0.3);
        }
        .btn-pro {
            background: rgba(244, 63, 94, 0.15);
            border: 1px solid rgba(244, 63, 94, 0.3);
            color: #f43f5e;
        }
        #result {
            margin-top: 12px;
            padding: 14px;
            border-radius: 12px;
            background: rgba(14, 18, 26, 0.95);
            border-left: 4px solid #38bdf8;
            border-top: 1px solid rgba(59, 130, 246, 0.2);
            line-height: 1.5;
            max-height: 300px;
            overflow-y: auto;
            display: none;
        }
    </style>
</head>
<body>

    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <div class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h2>Menu & Profile</h2>
            <button class="close-sidebar" onclick="toggleSidebar()">×</button>
        </div>
        
        <div class="profile-section">
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
                <p id="currentUserEmail" style="font-size: 0.8rem; color: #38bdf8; margin-bottom: 8px; word-break: break-all;"></p>
                <button class="btn-login" onclick="handleLogout()" style="width: 100%; padding: 8px; background: rgba(244, 63, 94, 0.2); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.4);">Log Out</button>
            </div>
            <p id="authStatus" style="font-size: 0.75rem; margin-top: 6px; text-align: center; font-weight: 500;"></p>
        </div>

        <div class="history-container">
            <div class="history-title">Analysis History (<span id="HistoryCount">0</span>)</div>
            <div class="history-list" id="historyList">
                <p style="font-size: 0.75rem; color: #64748b;">No analyses yet.</p>
            </div>
        </div>
    </div>

    <div class="app-container">
        <div class="header-row">
            <div class="header-left">
                <button class="menu-btn" onclick="toggleSidebar()">☰</button>
                <h1>Audit Guard AI</h1>
            </div>
        </div>

        <div class="workspace">
            <p class="instruction-text">Paste your contract or compliance agreement below for an instant risk evaluation and solution guidance.</p>
            
            <div style="display: flex; gap: 8px; margin-bottom: 8px;">
                <button type="button" onclick="loadSample('nda')" style="background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.3); color: #93c5fd; padding: 6px 10px; border-radius: 6px; font-size: 0.75rem; cursor: pointer; font-weight: 600;">Load Sample NDA</button>
                <button type="button" onclick="loadSample('msa')" style="background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.3); color: #93c5fd; padding: 6px 10px; border-radius: 6px; font-size: 0.75rem; cursor: pointer; font-weight: 600;">Load Sample MSA</button>
            </div>

            <textarea id="contractInput" placeholder="Paste your contract or compliance agreement here to evaluate risk..."></textarea>
        </div>

        <div class="footer-actions">
            <button class="action-btn btn-analyze" onclick="submitAudit()">Analyze Contract & Find Solutions</button>
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

        function loadSample(type) {
            const input = document.getElementById('contractInput');
            if (type === 'nda') {
                input.value = "Mutual Non-Disclosure Agreement: Party A and Party B agree to protect confidential information for a period of 5 years. Data residency requirements are omitted and liability is unlimited.";
            } else if (type === 'msa') {
                input.value = "Master Services Agreement: Vendor will process customer PII on third-party servers. Subprocessors may be engaged without prior written notice or approval, and termination may occur immediately without cause.";
            }
        }

        async function loadHistory() {
            try {
                const res = await fetch('/history');
                const data = await res.json();
                const listEl = document.getElementById('historyList');
                const countEl = document.getElementById('HistoryCount');
                
                countEl.innerText = data.history.length;

                if (data.history.length === 0) {
                    listEl.innerHTML = '<p style="font-size: 0.75rem; color: #64748b;">No analyses in history yet.</p>';
                    return;
                }

                listEl.innerHTML = '';
                data.history.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'history-item';
                    div.innerHTML = `
                        <div class="history-item-header">
                            <span>${item.date}</span>
                            <span style="color: ${item.risk === 'CRITICAL' ? '#f43f5e' : '#34d399'}">${item.risk}</span>
                        </div>
                        <div class="history-item-snippet">${item.snippet}</div>
                    `;
                    div.onclick = () => {
                        document.getElementById('contractInput').value = item.full_text;
                        const resDiv = document.getElementById('result');
                        resDiv.style.display = 'block';
                        let badgeColor = item.risk === 'CRITICAL' ? '#ef4444' : '#10b981';
                        let badgeBg = item.risk === 'CRITICAL' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)';
                        resDiv.innerHTML = `
                            <div style="margin-bottom: 8px;"><strong style="color: #38bdf8;">Loaded from History:</strong></div>
                            <div style="margin-bottom: 8px;"><span style="background: ${badgeBg}; color: ${badgeColor}; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.75rem;">Risk Level: ${item.risk}</span></div>
                            <div style="margin-bottom: 6px; font-size: 0.85rem;"><strong>Findings:</strong> ${item.details}</div>
                            <div style="font-size: 0.8rem; color: #cbd5e1;"><strong>Solutions:</strong><br>${item.solutions}</div>
                        `;
                        toggleSidebar();
                    };
                    listEl.appendChild(div);
                });
            } catch (err) {
                console.error("Failed to load history");
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
                    statusEl.style.color = '#34d399';
                    statusEl.innerText = data.message;
                    setTimeout(() => {
                        checkSession();
                        loadHistory();
                        statusEl.innerText = '';
                    }, 1000);
                } else {
                    statusEl.style.color = '#f43f5e';
                    statusEl.innerText = data.detail || 'Authentication failed';
                }
            } catch (err) {
                statusEl.style.color = '#f43f5e';
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
            resDiv.innerHTML = '<div style="color: #93c5fd; padding: 8px;">⏳ Parsing clauses and checking regulatory gaps...</div>';

            try {
                const res = await fetch('/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ contract_text: text })
                });
                const data = await res.json();
                if (res.ok) {
                    let badgeColor = data.analysis.risk_score === 'CRITICAL' ? '#ef4444' : '#10b981';
                    let badgeBg = data.analysis.risk_score === 'CRITICAL' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)';
                    resDiv.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <span style="background: ${badgeBg}; color: ${badgeColor}; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem;">Risk Level: ${data.analysis.risk_score}</span>
                            <span style="font-size: 0.75rem; color: #94a3b8;">Status: Success | Trials: ${data.trials_used}</span>
                        </div>
                        <div style="margin-bottom: 8px; font-size: 0.85rem;"><strong>Findings:</strong> ${data.analysis.details}</div>
                        <div style="font-size: 0.8rem; color: #cbd5e1;"><strong>Remediation & Solutions:</strong><br>${data.analysis.solutions}</div>
                    `;
                } else {
                    resDiv.innerHTML = `<span style="color: #f43f5e;">${data.detail || 'Error connecting to server.'}</span>`;
                }
            } catch (err) {
                resDiv.innerHTML = '<span style="color: #f43f5e;">Error connecting to server.</span>';
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
    identifier = user_email if user_email else request.client.host

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    is_paid = 0
    if user_email:
        cursor.execute("SELECT is_paid FROM users WHERE email = ?", (user_email,))
        row = cursor.fetchone()
        if row and row[0] == 1:
            is_paid = 1

    cursor.execute("SELECT date, snippet, full_text, risk, details, solutions FROM history WHERE identifier = ? ORDER BY id DESC", (identifier,))
    rows = cursor.fetchall()
    conn.close()

    history_list = []
    for r in rows:
        history_list.append({
            "date": r[0],
            "snippet": r[1],
            "full_text": r[2],
            "risk": r[3],
            "details": r[4],
            "solutions": r[5]
        })

    return {"history": history_list, "is_paid": is_paid}

@app.post("/signup")
async def signup(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    pwd_hash = hash_password(password)
    cursor.execute("INSERT INTO users (email, password_hash, is_paid, trials_used) VALUES (?, ?, 0, 0)", (email, pwd_hash))
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
    cursor.execute("""
        INSERT INTO history (identifier, date, snippet, full_text, risk, details, solutions)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (identifier, date_str, snippet, contract.contract_text, analysis["risk_score"], analysis["details"], analysis["solutions"]))
    conn.commit()

    if user_email:
        cursor.execute("SELECT is_paid, trials_used FROM users WHERE email = ?", (user_email,))
        row = cursor.fetchone()
        if row:
            is_paid, trials_used = row[0], row[1]
            if is_paid == 1:
                conn.close()
                return {"success": True, "trials_used": "unlimited", "analysis": analysis}
            else:
                if trials_used >= 3:
                    conn.close()
                    raise HTTPException(status_code=403, detail="Free trial limit reached (3/3). Please upgrade to Pro to continue.")
                new_trials = trials_used + 1
                cursor.execute("UPDATE users SET trials_used = ? WHERE email = ?", (new_trials, user_email))
                conn.commit()
                conn.close()
                return {
                    "success": True,
                    "trials_used": f"{new_trials}/3",
                    "analysis": analysis
                }
    else:
        trials_cookie = request.cookies.get("trials", "0")
        try:
            trials = int(trials_cookie)
        except ValueError:
            trials = 0

        if trials >= 3:
            conn.close()
            raise HTTPException(status_code=403, detail="Free trial limit reached (3/3). Please log in or sign up to get 3 new free trials!")
        
        new_trials = trials + 1
        response.set_cookie(key="trials", value=str(new_trials))
        conn.close()
        return {
            "success": True,
            "trials_used": f"{new_trials}/3",
            "analysis": analysis
        }

@app.post("/upgrade")
async def upgrade(request: Request):
    user_email = request.session.get("user")
    if not user_email:
        raise HTTPException(status_code=401, detail="Please sign up or log in first before upgrading to Pro.")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = ?", (user_email,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=401, detail="Please sign up or log in first before upgrading to Pro.")
    conn.close()

    return {
        "success": True,
        "authorization_url": "https://checkout.paystack.com/sample-checkout-link"
    }
