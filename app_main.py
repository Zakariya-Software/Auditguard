from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime, date
import json

# --- IMPROVED ANALYSIS LOGIC ---
def analyze_contract_liability(text):
    text = text.lower()
    findings = []
    risk_score = "Low"
    
    # Define Red Flags
    red_flags = {
        "indemnify": "High risk: Broad indemnification clause detected.",
        "hold harmless": "High risk: One-sided liability protection.",
        "perpetuity": "High risk: Rights granted forever without end.",
        "sole discretion": "Medium risk: Gives one party absolute control.",
        "exclusive": "Medium risk: Prevents you from working with others.",
        "unlimited liability": "High risk: No cap on potential financial loss.",
        "waive": "Medium risk: Giving up legal rights."
    }

    # Scan text for red flags
    for keyword, message in red_flags.items():
        if keyword in text:
            findings.append(message)

    # Determine Score
    if len(findings) > 2:
        risk_score = "CRITICAL"
    elif len(findings) > 0:
        risk_score = "High"
    else:
        findings.append("No common red-flag keywords detected.")

    return {
        "risk_score": risk_score,
        "findings_count": len(findings),
        "findings": findings,
        "timestamp": str(datetime.now())
    }

app = FastAPI(title="AuditGuard Engine")

class ContractRequest(BaseModel):
    contract_text: str

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AuditGuard - Contract Risk Analyzer</title>
        <style>
            body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; padding: 16px; margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
            .container { width: 100%; max-width: 500px; background: #1e293b; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
            h1 { font-size: 1.4rem; margin-bottom: 4px; color: #38bdf8; }
            p { color: #94a3b8; font-size: 0.85rem; margin-bottom: 16px; }
            textarea { width: 100%; height: 140px; background: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 8px; padding: 12px; box-sizing: border-box; outline: none; }
            button { margin-top: 16px; width: 100%; background: #0284c7; color: white; border: none; padding: 12px; font-weight: bold; border-radius: 8px; cursor: pointer; transition: 0.2s; }
            button:hover { background: #0369a1; }
            .btn-pro { background: #16a34a; margin-top: 8px; }
            .btn-pro:hover { background: #15803d; }
            #result { margin-top: 16px; background: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #334155; white-space: pre-wrap; display: none; font-family: monospace; font-size: 0.85rem; border-left: 4px solid #38bdf8; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AuditGuard</h1>
            <p>Paste your contract text below for an instant risk evaluation.</p>
            <textarea id="contractInput" placeholder="Paste contract text here..."></textarea>
            <button onclick="submitAudit()">Analyze Contract</button>
            <button class="btn-pro" onclick="alert('Pro features coming soon! Includes AI-powered deep scanning.')">Upgrade to Pro</button>
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
                    resultDiv.style.borderLeftColor = data.risk_score === 'CRITICAL' ? '#ef4444' : '#38bdf8';
                } catch (err) {
                    resultDiv.textContent = 'Error: ' + err.message;
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/audit")
async def audit(request: ContractRequest):
    return analyze_contract_liability(request.contract_text)
