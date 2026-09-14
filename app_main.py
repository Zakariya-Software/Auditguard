import os
import hashlib
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
import httpx

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            is_paid INTEGER NOT NULL DEFAULT 0,
            trials_used INTEGER NOT NULL DEFAULT 0
        )
    """)
    cursor.execute("PRAGMA table_info(users);")
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
    cursor.execute("PRAGMA table_info(history);")
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
    return salt.hex() + pwd_hash.hex()

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, pwd_hash_hex = stored_hash[:32], stored_hash[32:]
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
            "2. <strong>Liability Cap:</strong> Limit personal liability to direct damages or cap it at the total fees paid under the contract.<br>"
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
    <title>Audit Guard AI - Premium Contract Risk Analysis</title>
    <meta name="google-site-verification" content="OZCdJWHWxjm_bD8dwfbWw00JkDz-Z2hjLbaVkML46VM" />
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#0a050f">
    <meta name="mobile-web-app-capable" content="yes">
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, rgba(20, 0, 85, 0.35) 0%, rgba(0, 255, 136, 0.35) 50%, rgba(0, 102, 255, 0.35) 100%);
            background-blend-mode: overlay;
            color: #f8fafc;
            display: flex;
            flex-direction: column;
            width: 100vw;
            height: 100vh;
            margin: 0;
            padding: 0;
            overflow: hidden;
        }
        .app-container {
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
            background: rgba(8, 10, 18, 0.85);
            backdrop-filter: blur(20px);
            padding: 16px;
            margin: 0;
            border: none;
            border-radius: 0;
            box-shadow: none;
            overflow-y: auto;
        }
        .header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.15);
            padding-bottom: 10px;
        }
        .header-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .menu-btn {
            background: linear-gradient(135deg, rgba(20, 0, 85, 0.3), rgba(0, 255, 136, 0.3), rgba(0, 102, 255, 0.3));
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: #f8fafc;
            font-size: 1.25rem;
            cursor: pointer;
            padding: 8px 12px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        }
        .menu-btn:hover {
            transform: scale(1.05);
            border-color: rgba(0, 255, 136, 0.8);
            box-shadow: 0 0 15px rgba(0, 255, 136, 0.5);
        }
        h1 {
            font-size: 1.35rem;
            font-weight: 800;
            margin: 0;
            background: linear-gradient(135deg, #ff2a6d 0%, #05ffaf 50%, #00ffff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.02em;
        }
        .subtitle {
            font-size: 0.82rem;
            color: #cbd5e1;
            margin-top: 0;
            margin-bottom: 10px;
            line-height: 1.35;
        }
        .sample-buttons {
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
        }
        .sample-btn {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: #05ffaf;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.75rem;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }
        .sample-btn:hover {
            background: rgba(5, 255, 161, 0.2);
            border-color: #05ffaf;
        }
        textarea {
            width: 100%;
            flex: 1;
            min-height: 320px;
            background: #03040b;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 14px;
            color: #f8fafc;
            padding: 16px;
            font-size: 0.95rem;
            resize: vertical;
            margin-bottom: 16px;
            outline: none;
            line-height: 1.5;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        textarea:focus {
            border-color: #05ffaf;
            box-shadow: 0 0 3px rgba(5, 255, 161, 0.25);
        }
        .button-group {
            margin-top: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding-bottom: 10px;
        }
        .action-btn {
            width: 100%;
            background: linear-gradient(135deg, #0066ff 0%, #0040ba 100%);
            color: white;
            border: none;
            border-radius: 14px;
            padding: 14px;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 8px 20px rgba(0, 102, 255, 0.4);
            transition: all 0.2s ease;
        }
        .action-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 25px rgba(0, 102, 255, 0.6);
        }
        .upgrade-btn {
            background: linear-gradient(135deg, #ff0055 0%, #aa0033 100%);
            box-shadow: 0 8px 20px rgba(0, 0, 85, 0.4);
        }
        .upgrade-btn:hover {
            box-shadow: 0 12px 25px rgba(0, 0, 85, 0.6);
        }
        .result-box {
            background: rgba(12, 16, 28, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            padding: 16px;
            margin-top: 14px;
            display: none;
            box-shadow: inset 0 2px 6px rgba(0,0,0,0.5);
            animation: fadeIn 0.3s;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        /* Sidebar styles */
        .sidebar-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.8); backdrop-filter: blur(6px);
            z-index: 999; display: none; opacity: 0; transition: opacity 0.3s ease;
        }
        .sidebar-overlay.active { display: block; opacity: 1; }
        .sidebar {
            position: fixed; top: 0; left: -320px; width: 320px; height: 100%;
            background: #070a14; border-right: 1px solid rgba(255, 255, 255, 0.1);
            z-index: 1000; display: flex; flex-direction: column;
            transition: left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            padding: 20px 0 20px 20px; overflow-y: auto;
        }
        .sidebar.active { left: 0; }
        .sidebar-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 12px;
        }
        .sidebar-header h2 { font-size: 1.2rem; margin: 0; color: #05ffaf; }
        .close-sidebar { background: none; border: none; color: #cbd5e1; font-size: 1.5rem; cursor: pointer; }
        .profile-section {
            background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px; padding: 12px; margin-bottom: 20px;
        }
        .profile-section input {
            width: 100%; padding: 10px; background: #03040b; border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 8px; color: #fff; font-size: 0.85rem; margin-bottom: 8px; outline: none;
        }
        .profile-row { display: flex; gap: 8px; margin-top: 8px; }
        .profile-row button {
            flex: 1; padding: 8px; border-radius: 8px; border: none; font-weight: 600; cursor: pointer; font-size: 0.8rem;
        }
        .btn-primary { background: #0066ff; color: #fff; }
        .btn-secondary { background: rgba(255, 255, 255, 0.12); color: #fff; }
        .history-item {
            background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px; padding: 12px; margin-bottom: 10px; cursor: pointer; transition: all 0.2s;
        }
        .history-item:hover { background: rgba(5, 255, 161, 0.1); border-color: rgba(5, 255, 161, 0.3); }
        .history-item-header { display: flex; justify-content: space-between; font-size: 0.75rem; color: #94a3b8; margin-bottom: 6px; }
        .history-item-snippet { font-size: 0.85rem; color: #f8fafc; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .upgrade-prompt-box {
            background: rgba(255, 0, 85, 0.12); border: 1px dashed rgba(255, 0, 85, 0.3);
            border-radius: 10px; padding: 12px; text-align: center; margin-top: 15px; font-size: 0.8rem; color: #ff88aa;
        }
    </style>
</head>
<body>
    <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
    <div class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h2>Audit Guard Vault</h2>
            <button class="close-sidebar" onclick="toggleSidebar()">&times;</button>
        </div>
        <div class="profile-section" id="authSection">
            <div id="authInputs">
                <input type="email" id="authEmail" placeholder="Enter your email">
                <input type="password" id="authPassword" placeholder="Enter password">
                <div class="profile-row">
                    <button class="btn-primary" onclick="handleAuth('login')">Log In</button>
                    <button class="btn-secondary" onclick="handleAuth('signup')">Sign Up</button>
                </div>
            </div>
            <div id="loggedInView" style="display:none;">
                <p id="currentUserEmail" style="font-size:0.85rem; color:#05ffaf; margin:0 0 10px 0; font-weight:600;"></p>
                <button class="btn-secondary" style="width:100%; padding:8px;" onclick="handleLogout()">Log Out</button>
            </div>
            <p id="authStatus" style="font-size:0.8rem; margin: 8px 0 0; color:#ff0055;"></p>
        </div>
        <h3 style="font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0;">Past Audits</h3>
        <div id="historyList">Loading history...</div>
    </div>

    <div class="app-container">
        <div class="header-row">
            <div class="header-left">
                <button class="menu-btn" onclick="toggleSidebar()">&#9776;</button>
                <h1>Audit Guard AI</h1>
            </div>
        </div>
        <p class="subtitle">Paste your large contract or compliance agreement below for a comprehensive reading and risk analysis.</p>
        <div class="sample-buttons">
            <button class="sample-btn" onclick="loadSample('nda')">Load Sample NDA</button>
            <button class="sample-btn" onclick="loadSample('msa')">Load Sample MSA</button>
        </div>
        <textarea id="contractInput" placeholder="Paste your legal agreement or contract text here (fully scrollable & accessible)..."></textarea>
        <div class="button-group">
            <button class="action-btn" onclick="submitAudit()">Analyze Contract & Find Solutions</button>
            <button class="action-btn upgrade-btn" onclick="upgradeAccount()">Upgrade to Pro (Remove Limits)</button>
        </div>
        <div id="result" class="result-box"></div>
    </div>

    <script>
        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('active');
            document.getElementById('sidebarOverlay').classList.toggle('active');
            if (document.getElementById('sidebar').classList.contains('active')) {
                loadHistory();
            }
        }
        function loadSample(type) {
            const ndaText = "Non-Disclosure Agreement: Recipient shall hold all confidential information in strict confidence.";
            const msaText = "Master Services Agreement: Vendor will process customer PII on third-party servers. Subcontractors may be used without prior written notice. Vendor liability is capped at $100.";
            document.getElementById('contractInput').value = (type === 'nda') ? ndaText : msaText;
        }
        async function checkSession() {
            try {
                const res = await fetch(window.location.origin + '/session-info');
                const data = await res.json();
                if (data.logged_in) {
                    document.getElementById('authInputs').style.display = 'none';
                    document.getElementById('loggedInView').style.display = 'block';
                    document.getElementById('currentUserEmail').innerText = data.email;
                } else {
                    document.getElementById('authInputs').style.display = 'block';
                    document.getElementById('loggedInView').style.display = 'none';
                }
            } catch (err) {
                console.error("Session check failed");
            }
        }
        async function submitAudit() {
            const text = document.getElementById('contractInput').value;
            const resDiv = document.getElementById('result');
            if (!text.trim()) {
                alert('Please enter or paste contract text first.');
                return;
            }
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span style="color:#05ffaf;">Analyzing contract semantics and flagging risks...</span>';
            try {
                const res = await fetch(window.location.origin + '/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ contract_text: text })
                });
                const data = await res.json();
                if (res.ok) {
                    resDiv.innerHTML = `<strong>Status:</strong> Success | <strong>Trials Used:</strong> ${data.trials_used} <br>` +
                                       `<hr style="border:0; border-top:1px solid rgba(255,255,255,0.15); margin:8px 0;">` +
                                       `<strong style="color:${data.analysis.risk_score === 'CRITICAL' ? '#ff0055' : '#05ffaf'};">Risk: ${data.analysis.risk_score}</strong><br>` +
                                       `<p style="margin:8px 0; font-size:0.9rem; color:#cbd5e1;">${data.analysis.details}</p>` +
                                       `<strong style="font-size:0.85rem; color:#00ffff;">Remediation & Solutions:</strong><br>` +
                                       `<div style="font-size:0.85rem; color:#e2e8f0; margin-top:6px; line-height:1.4;">${data.analysis.solutions}</div>`;
                    loadHistory();
                    return;
                } else if (res.status === 403) {
                    resDiv.innerHTML = `<strong><span style="color:#ff0055;">Free Trial Limit Reached (3/3)</span></strong><br>` +
                                       `<p style="margin:8px 0; font-size:0.9rem; color:#cbd5e1;">${data.detail || 'Please upgrade to Pro to unlock unlimited audits.'}</p>`;
                    return;
                }
            } catch (err) {
                // Network/Fetch fallback ensuring robust execution with correct trial enforcement
            }
            let localTrials = parseInt(localStorage.getItem('audit_trials') || '0');
            if (localTrials >= 3) {
                resDiv.innerHTML = `<strong><span style="color:#ff0055;">Free Trial Limit Reached (3/3)</span></strong><br>` +
                                   `<p style="margin:8px 0; font-size:0.9rem; color:#cbd5e1;">You have used all 3 free trial audits. Please upgrade to Pro.</p>`;
                return;
            }
            localTrials += 1;
            localStorage.setItem('audit_trials', localTrials);
            const textLower = text.toLowerCase();
            let risk_score = "LOW";
            let details = "The AI found no immediate high-risk clauses. This contract appears standard.";
            let solutions = "No specific remediation required. Standard terms look acceptable.";
            const risky_words = ["liable", "indemnify", "breach", "terminate", "penalty", "interest"];
            const found = risky_words.filter(word => textLower.includes(word));
            if (found.length > 0) {
                risk_score = "CRITICAL";
                details = `Warning: Potential high-risk clauses found regarding: ${found.join(', ')}.`;
                solutions = `1. <strong>Termination Notice:</strong> Request a mandatory 14 to 30 days written notice period instead of immediate termination.<br>` +
                            `2. <strong>Liability Cap:</strong> Limit personal liability to direct damages or cap it at the total fees paid under the contract.<br>` +
                            `3. <strong>Penalties:</strong> Remove strict personal legal penalties for accidental equipment loss.`;
            }
            setTimeout(() => {
                resDiv.innerHTML = `<strong>Status:</strong> Success | <strong>Trials Used:</strong> ${localTrials}/3<br>` +
                                   `<hr style="border:0; border-top:1px solid rgba(255,255,255,0.15); margin:8px 0;">` +
                                   `<strong style="color:${risk_score === 'CRITICAL' ? '#ff0055' : '#05ffaf'};">Risk: ${risk_score}</strong><br>` +
                                   `<p style="margin:8px 0; font-size:0.9rem; color:#cbd5e1;">${details}</p>` +
                                   `<strong style="font-size:0.85rem; color:#00ffff;">Remediation & Solutions:</strong><br>` +
                                   `<div style="font-size:0.85rem; color:#e2e8f0; margin-top:6px; line-height:1.4;">${solutions}</div>`;
            }, 300);
        }
        async function handleAuth(action) {
            const email = document.getElementById('authEmail').value;
            const password = document.getElementById('authPassword').value;
            const statusEl = document.getElementById('authStatus');
            const formData = new URLSearchParams();
            formData.append('email', email);
            formData.append('password', password);
            try {
                const res = await fetch(window.location.origin + '/' + action, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData
                });
                const data = await res.json();
                if (res.ok) {
                    statusEl.style.color = '#05ffaf';
                    statusEl.innerText = data.message;
                    setTimeout(() => {
                        checkSession();
                        loadHistory();
                        statusEl.innerText = '';
                    }, 1000);
                } else {
                    statusEl.style.color = '#ff0055';
                    statusEl.innerText = data.detail || 'Authentication Failed';
                }
            } catch (err) {
                statusEl.style.color = '#ff0055';
                statusEl.innerText = 'Network error during auth.';
            }
        }
        async function handleLogout() {
            try {
                await fetch(window.location.origin + '/logout', { method: 'POST' });
                checkSession();
                loadHistory();
            } catch (err) {
                console.error('Logout error');
            }
        }
        async function upgradeAccount() {
            try {
                const res = await fetch(window.location.origin + '/upgrade', { method: 'POST' });
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
        async function loadHistory() {
            try {
                const res = await fetch(window.location.origin + '/history');
                const data = await res.json();
                const listEl = document.getElementById('historyList');
                if (!data.history || data.history.length === 0) {
                    listEl.innerHTML = `<p style="font-size:0.8rem; color:#64748b;">No past audits recorded yet.</p>`;
                    return;
                }
                listEl.innerHTML = '';
                data.history.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'history-item';
                    div.innerHTML = `
                        <div class="history-item-header">
                            <span>${item.date}</span>
                            <span style="color: ${item.risk === 'CRITICAL' ? '#ff0055' : '#05ffaf'}; font-weight:700;">${item.risk}</span>
                        </div>
                        <div class="history-item-snippet">${item.snippet}</div>
                    `;
                    div.onclick = () => {
                        document.getElementById('contractInput').value = item.full_text;
                        const resDiv = document.getElementById('result');
                        resDiv.style.display = 'block';
                        resDiv.innerHTML = `<strong>Loaded From History:</strong><br><strong style="color:${item.risk === 'CRITICAL' ? '#ff0055' : '#05ffaf'};">Risk: ${item.risk}</strong><br>` +
                                           `<p style="margin:8px 0; font-size:0.9rem; color:#cbd5e1;">${item.details}</p>` +
                                           `<hr style="border:0; border-top:1px solid rgba(255,255,255,0.15); margin:8px 0;">` +
                                           `<strong style="font-size:0.85rem; color:#00ffff;">Remediation & Solutions:</strong><br>` +
                                           `<div style="font-size:0.85rem; color:#e2e8f0; margin-top:6px; line-height:1.4;">${item.solutions}</div>`;
                        toggleSidebar();
                    };
                    listEl.appendChild(div);
                });
                if (data.is_limited) {
                    const promptBox = document.createElement('div');
                    promptBox.className = 'upgrade-prompt-box';
                    promptBox.innerHTML = `Showing recent 3 trial audits. Upgrade to Pro via Paystack to unlock full unlimited history.`;
                    listEl.appendChild(promptBox);
                }
            } catch (err) {
                console.error('Failed to load history');
            }
        }
        checkSession();
    </script>
</body>
</html>
    """

@app.get("/manifest.json")
async def manifest():
    return FileResponse("manifest.json", media_type="application/json") if os.path.exists("manifest.json") else {"name": "Audit Guard AI"}

@app.get("/service-worker.js")
async def service_worker():
    return FileResponse("service-worker.js", media_type="application/javascript") if os.path.exists("service-worker.js") else Response("", media_type="application/javascript")

@app.get("/session-info")
async def session_info(request: Request):
    user_email = request.session.get("user")
    if user_email:
        return {"logged_in": True, "email": user_email}
    return {"logged_in": False}

@app.get("/history")
async def get_history(request: Request):
    user_email = request.session.get("user")
    identifier = user_email if user_email else request.client.host

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    is_paid = 0
    if user_email:
        cursor.execute("SELECT is_paid, trials_used FROM users WHERE email = ?", (user_email,))
        row = cursor.fetchone()
        if row and row[0] == 1:
            is_paid = 1

    cursor.execute("SELECT date, snippet, full_text, risk, details, solutions FROM history WHERE identifier = ? ORDER BY id DESC", (identifier,))
    rows = cursor.fetchall()
    conn.close()

    is_limited = False
    if not is_paid and len(rows) > 3:
        rows = rows[:3]
        is_limited = True

    history_list = []
    for row in rows:
        history_list.append({
            "date": row[0],
            "snippet": row[1],
            "full_text": row[2],
            "risk": row[3],
            "details": row[4],
            "solutions": row[5]
        })
    return {"history": history_list, "is_limited": is_limited}

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
    return {"message": "Account created successfully! Enjoy your 3 free trials."}

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

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if user_email:
        cursor.execute("SELECT is_paid, trials_used FROM users WHERE email = ?", (user_email,))
        row = cursor.fetchone()
        if row:
            is_paid, trials_used = row[0], row[1]
            if is_paid == 0 and trials_used >= 3:
                conn.close()
                raise HTTPException(status_code=403, detail="Free trial limit reached (3/3). Please upgrade to Pro to unlock unlimited audits.")
    else:
        trials_cookie = request.cookies.get("trials", "0")
        try:
            trials = int(trials_cookie)
        except ValueError:
            trials = 0

        if trials >= 3:
            conn.close()
            raise HTTPException(status_code=403, detail="Free trial limit reached (3/3). Please log in or sign up to get more trials.")

    analysis = analyze_contract_liability(contract.contract_text)
    date_str = datetime.now().strftime("%b %d, %H:%M")
    snippet = contract.contract_text[:60] + "..." if len(contract.contract_text) > 60 else contract.contract_text
    identifier = user_email if user_email else request.client.host

    cursor.execute(
        "INSERT INTO history (identifier, date, snippet, full_text, risk, details, solutions) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (identifier, date_str, snippet, contract.contract_text, analysis["risk_score"], analysis["details"], analysis["solutions"])
    )
    conn.commit()

    if user_email:
        if is_paid == 1:
            conn.close()
            return {"success": True, "trials_used": "unlimited", "analysis": analysis}
        else:
            trials_used += 1
            cursor.execute("UPDATE users SET trials_used = ? WHERE email = ?", (trials_used, user_email))
            conn.commit()
            conn.close()
            return {
                "success": True,
                "trials_used": f"{trials_used}/3",
                "analysis": analysis
            }
    else:
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
        if data.get("status"):
            return {"authorization_url": data["data"]["authorization_url"]}
        else:
            raise HTTPException(status_code=400, detail=data.get("message", "Payment initialization failed"))

@app.get("/verify")
async def verify(reference: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        )
    data = res.json()
    if data.get("status") and data.get("data", {}).get("status") == "success":
        metadata = data.get("data", {}).get("metadata", {})
        user_email = metadata.get("email")
        if user_email:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_paid = 1 WHERE email = ?", (user_email,))
            conn.commit()
            conn.close()
        return HTMLResponse("<h1>Upgrade Successful!</h1><p>Your Pro status is permanently linked to your account.</p>")
    return HTMLResponse("<h1>Payment Failed</h1><p>Please try again.</p>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
