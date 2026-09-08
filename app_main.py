
import os
import httpx
from datetime import date
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI()

# --- CONFIGURATION ---
# Replace with your actual Paystack Secret Key
PAYSTACK_SECRET_KEY = "sk_test_xxxxxx" 
# The URL where your app is hosted (used for the payment redirect)
BASE_URL = "https://web-production-b74c4.up.railway.app" 

# --- IN-MEMORY DATABASE (For a quick launch tonight) ---
# Note: In a real production app, use a Database (PostgreSQL/Redis)
USAGE_COUNTS = {}  # { "ip_date": count }
PAID_USERS = set() # { "ip_address" }

class ContractRequest(BaseModel):
    contract_text: str

# --- MOCK ANALYSIS LOGIC ---
def analyze_contract_liability(text: str):
    # This is where your AI logic goes. 
    # For now, we return a mock evaluation.
    risk_score = "LOW"
    if "liable" in text.lower() or "indemnify" in text.lower():
        risk_score = "CRITICAL"
    
    return {
        "risk_score": risk_score,
        "summary": "AI Analysis complete.",
        "details": "Found potential liability clauses." if risk_score == "CRITICAL" else "No immediate red flags found."
    }

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # This renders the frontend you saw in your screenshot
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AuditGuard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: sans-serif; background: #0b0e11; color: white; padding: 20px; }
            .container { max-width: 500px; margin: auto; }
            h1 { color: #38bdf8; }
            textarea { width: 100%; height: 150px; background: #161a1e; color: white; border: 1px solid #334155; border-radius: 8px; padding: 10px; margin-bottom: 10px; box-sizing: border-box; }
            button { width: 100%; padding: 12px; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; margin-bottom: 10px; }
            .btn-analyze { background: #0284c7; color: white; }
            .btn-pro { background: #16a34a; color: white; }
            #result { margin-top: 20px; padding: 15px; border-radius: 8px; display: none; background: #161a1e; border: 1px solid #334155; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AuditGuard</h1>
            <p>Paste your contract text below for an instant risk evaluation.</p>
            <textarea id="contractInput" placeholder="Paste contract text here..."></textarea>
            <button class="btn-analyze" onclick="submitAudit()">Analyze Contract</button>
            <button class="btn-pro" onclick="upgradeAccount()">Upgrade to Pro (Remove Limits)</button>
            <div id="result"></div>
        </div>

        <script>
            async function submitAudit() {
                const text = document.getElementById('contractInput').value;
                const resultDiv = document.getElementById('result');
                if (!text) { alert('Please enter contract text'); return; }

                resultDiv.style.display = 'block';
                resultDiv.textContent = 'Analyzing...';

                const response = await fetch('/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ contract_text: text })
                });
                
                const data = await response.json();
                if (data.error) {
                    resultDiv.textContent = data.error;
                    resultDiv.style.borderColor = 'red';
                } else {
                    resultDiv.innerHTML = `<strong>Risk: ${data.risk_score}</strong><br>${data.details}`;
                    resultDiv.style.borderColor = data.risk_score === 'CRITICAL' ? '#ef4444' : '#38bdf8';
                }
            }

            async function upgradeAccount() {
                const response = await fetch('/upgrade', { method: 'POST' });
                const data = await response.json();
                if (data.authorization_url) {
                    window.location.href = data.authorization_url; // Redirect to Paystack
                } else {
                    alert('Payment initialization failed.');
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/audit")
async def audit(request: ContractRequest, req: Request):
    client_ip = req.client.host
    today_str = str(date.today())

    # 1. Check if user is Pro
    if client_ip in PAID_USERS:
        return analyze_contract_liability(request.contract_text)

    # 2. Check Daily Limit (3 audits)
    key = f"{client_ip}_{today_str}"
    current_count = USAGE_COUNTS.get(key, 0)

    if current_count >= 3:
        return {"error": "Daily limit reached (3/3 used). Please upgrade to Pro!"}

    # 3. Increment and Analyze
    USAGE_COUNTS[key] = current_count + 1
    return analyze_contract_liability(request.contract_text)

@app.post("/upgrade")
async def upgrade_account(req: Request):
    client_ip = req.client.host
    
    # Initialize Paystack Transaction
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    
    # We pass the IP in the metadata so we know who to upgrade later
    payload = {
        "email": f"user_{client_ip.replace('.', '_')}@auditguard.com", # Paystack requires an email
        "amount": "500000", # Example: 5000.00 in your local currency subunits
        "callback_url": f"{BASE_URL}/verify-payment",
        "metadata": {"ip_address": client_ip}
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        res_data = response.json()
        
        if res_data["status"]:
            return {"authorization_url": res_data["data"]["authorization_url"]}
        else:
            raise HTTPException(status_code=400, detail="Paystack initialization failed")

@app.get("/verify-payment")
async def verify_payment(reference: str):
    # Paystack redirects here after payment with a ?reference=...
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        res_data = response.json()

        if res_data["status"] and res_data["data"]["status"] == "success":
            # Payment successful! Get IP from metadata and upgrade
            client_ip = res_data["data"]["metadata"]["ip_address"]
            PAID_USERS.add(client_ip)
            return HTMLResponse("<h1>Success!</h1><p>Your account is upgraded. You can now close this and go back to AuditGuard.</p><a href='/'>Go Back</a>")
        else:
            return HTMLResponse("<h1>Payment Failed</h1><p>We could not verify your payment.</p>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
