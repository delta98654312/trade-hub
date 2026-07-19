import json
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime

app = Flask(__name__)
DATA = Path('trades.json')

HTML = """<!doctype html>
<html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Trade Hub Python</title>
<style>
body{margin:0;font-family:system-ui;background:#0b0d11;color:#eef3fb} .wrap{max-width:1200px;margin:0 auto;padding:16px;display:grid;gap:16px} .card{background:#151922;border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:16px} input,select,button{width:100%;padding:12px;border-radius:12px;border:1px solid rgba(255,255,255,.08);background:#0f1319;color:#eef3fb;margin:6px 0} button{background:linear-gradient(180deg,#7df0c5,#59d8a8);color:#082117;font-weight:800;cursor:pointer} .grid{display:grid;gap:12px;grid-template-columns:repeat(2,minmax(0,1fr))} table{width:100%;border-collapse:collapse} td,th{border-bottom:1px solid rgba(255,255,255,.08);padding:10px;text-align:left;white-space:nowrap} .muted{opacity:.75}
@media(min-width:900px){.two{display:grid;grid-template-columns:1.2fr .8fr;gap:16px}}</style></head><body><div class='wrap'>
<div class='card'><h1>Trade Hub Python</h1><p class='muted'>JSON local + app Python. Simple, rapide, sans Netlify.</p></div>
<div class='two'><div class='card'><h2>Nouveau trade</h2><div class='grid'><input id='date' type='date'><select id='asset'><option>Or</option><option>Pétrole Brent</option><option>Nasdaq-100</option><option>TotalEnergies</option></select><input id='buyPrice' type='number' step='0.0001' placeholder='Prix achat'><input id='marketPrice' type='number' step='0.0001' placeholder='Prix marché'><input id='amountEUR' type='number' step='0.01' placeholder='Montant €'><input id='feesEUR' type='number' step='0.01' value='2'><input id='targetNetEUR' type='number' step='0.01' value='2'><input id='note' placeholder='Note'></div><button onclick='addTrade()'>Ajouter</button><button onclick='refreshAll()'>Rafraîchir</button><p id='status'></p></div><div class='card'><h2>Stats</h2><div id='stats'></div><h2>Fermer trade</h2><select id='openTrades'></select><input id='closeDate' type='date'><input id='closePrice' type='number' step='0.0001' placeholder='Prix de clôture'><input id='closeNote' placeholder='Note de clôture'><button onclick='closeTrade()'>Close</button></div></div>
<div class='card'><h2>Historique</h2><table><thead><tr><th>Status</th><th>Date</th><th>Actif</th><th>Achat</th><th>Marché</th><th>Montant</th><th>Net</th><th>Note</th></tr></thead><tbody id='history'></tbody></table></div></div>
<script>
function n(v){return Number(v)||0}
async function j(u,o){const r=await fetch(u,o); return await r.json()}
function today(){return new Date().toISOString().slice(0,10)}
date.value=today(); closeDate.value=today();
async function refreshAll(){ const d=await j('/api/trades'); render(d.trades||[]); }
function render(rows){ const open=rows.filter(r=>r.status==='open'); const closed=rows.filter(r=>r.status==='closed'); const net=closed.reduce((s,r)=>s+n(r.realizedNetEUR),0); stats.innerHTML=`<div>Ouverts: <b>${open.length}</b></div><div>Clos: <b>${closed.length}</b></div><div>PnL net: <b>${net.toFixed(2)} €</b></div>`; openTrades.innerHTML=open.length?open.map((r,i)=>`<option value='${r.id}'>${r.asset} | ${r.date}</option>`).join(''):'<option>Aucun trade ouvert</option>'; history.innerHTML=rows.slice().reverse().map(r=>`<tr><td>${r.status==='closed'?'Clos':'Ouvert'}</td><td>${r.date||''}</td><td>${r.asset||''}</td><td>${n(r.buyPriceUsed).toFixed(4)}</td><td>${n(r.marketPrice).toFixed(4)}</td><td>${n(r.amountEUR).toFixed(2)} €</td><td>${n(r.realizedNetEUR||r.unrealizedNetEUR).toFixed(2)} €</td><td>${r.note||r.closeNote||''}</td></tr>`).join(''); }
async function addTrade(){ const payload={date:date.value,asset:asset.value,buyPriceUsed:n(buyPrice.value),marketPrice:n(marketPrice.value),amountEUR:n(amountEUR.value),feesEUR:n(feesEUR.value),targetNetEUR:n(targetNetEUR.value),note:note.value}; const d=await j('/api/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); status.textContent=d.ok?'Ajouté':'Erreur'; refreshAll(); }
async function closeTrade(){ const payload={id:openTrades.value,closeDate:closeDate.value,closePrice:n(closePrice.value),closeNote:closeNote.value}; const d=await j('/api/close',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); status.textContent=d.ok?'Clos':'Erreur'; refreshAll(); }
refreshAll();
</script></body></html>"""

def load_data():
    if DATA.exists():
        return json.loads(DATA.read_text(encoding='utf-8'))
    return []

def save_data(rows):
    DATA.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')

@app.get('/')
def home():
    return render_template_string(HTML)

@app.get('/api/trades')
def trades():
    return jsonify({'ok': True, 'trades': load_data()})

@app.post('/api/add')
def add():
    rows = load_data()
    data = request.get_json(force=True)
    row = {
        'id': f"T{int(datetime.utcnow().timestamp()*1000)}",
        'status': 'open',
        'date': data.get('date',''),
        'closeDate': '',
        'durationDays': '',
        'asset': data.get('asset',''),
        'buyPriceUsed': float(data.get('buyPriceUsed',0) or 0),
        'marketPrice': float(data.get('marketPrice',0) or 0),
        'amountEUR': float(data.get('amountEUR',0) or 0),
        'feesEUR': float(data.get('feesEUR',0) or 0),
        'targetNetEUR': float(data.get('targetNetEUR',0) or 0),
        'realizedNetEUR': 0,
        'unrealizedNetEUR': 0,
        'note': data.get('note',''),
        'closeNote': '',
        'createdAt': datetime.utcnow().isoformat()
    }
    rows.append(row)
    save_data(rows)
    return jsonify({'ok': True})

@app.post('/api/close')
def close():
    rows = load_data()
    data = request.get_json(force=True)
    for r in rows:
        if r['id'] == data.get('id'):
            qty = (r['amountEUR'] / r['buyPriceUsed']) if r['buyPriceUsed'] else 0
            net = ((float(data.get('closePrice',0) or 0) - r['buyPriceUsed']) * qty) - r['feesEUR']
            r['status'] = 'closed'
            r['closeDate'] = data.get('closeDate','')
            r['closePrice'] = float(data.get('closePrice',0) or 0)
            r['realizedNetEUR'] = round(net, 4)
            r['closeNote'] = data.get('closeNote','')
            break
    save_data(rows)
    return jsonify({'ok': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)