import json
import time
from pathlib import Path
from datetime import datetime, date
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
DATA = Path('trades.json')

ASSETS = {
    "Or": "XAUUSD=X",
    "Pétrole Brent": "BZ=F",
    "Nasdaq-100": "^NDX",
    "TotalEnergies": "TTE.PA",
}

_price_cache = {}
CACHE_TTL = 25

def fetch_live_price(asset):
    now = time.time()
    cached = _price_cache.get(asset)
    if cached and now - cached['t'] < CACHE_TTL:
        return cached['price']
    symbol = ASSETS.get(asset)
    if not symbol:
        return None
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        r = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        j = r.json()
        price = j["chart"]["result"][0]["meta"]["regularMarketPrice"]
        price = float(price)
        _price_cache[asset] = {"t": now, "price": price}
        return price
    except Exception:
        return cached['price'] if cached else None

def load_data():
    if DATA.exists():
        try:
            return json.loads(DATA.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_data(rows):
    DATA.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

def compute_open_metrics(row, live_price):
    amt = float(row.get("amountEUR", 0) or 0)
    fees = float(row.get("feesEUR", 0) or 0)
    target_net = float(row.get("targetNetEUR", 0) or 0)
    buy = float(row.get("buyPriceUsed", 0) or 0)
    qty = (amt / buy) if buy else 0
    be = ((amt + fees) / qty) if qty else 0
    target_sell = ((amt + fees + target_net) / qty) if qty else 0
    unreal = ((live_price - buy) * qty - fees) if (live_price and qty) else None
    dist = (target_sell - live_price) if (live_price and target_sell) else None
    return qty, be, target_sell, unreal, dist

INDEX_HTML = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Trade Hub</title>
<style>
  :root{--bg:#0b0d11;--card:#141821;--line:rgba(255,255,255,.08);--text:#f3f6fb;--muted:#93a1b5;--good:#4ade80;--bad:#fb7185;--warn:#f5a524;--accent:#59d8a8;}
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,Inter,system-ui,sans-serif;background:radial-gradient(1200px 800px at 20% -10%,#121722 0%,#0b0d11 60%);color:var(--text)}
  .wrap{max-width:1180px;margin:0 auto;padding:20px;display:grid;gap:18px}
  h1{margin:0;font-size:26px} h2{margin:0 0 14px;font-size:18px}
  .muted{color:var(--muted)}
  .card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
  .hero{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px}
  .pill{padding:6px 12px;border-radius:999px;background:#10151f;border:1px solid var(--line);font-size:13px;color:var(--muted)}
  .stats{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
  .kpi{background:#0f141d;border:1px solid var(--line);border-radius:14px;padding:14px}
  .kpi .l{font-size:12px;color:var(--muted);margin-bottom:6px}
  .kpi .v{font-size:24px;font-weight:800}
  .grid2{display:grid;gap:18px;grid-template-columns:1fr}
  .assets{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}
  .asset{padding:12px;border-radius:12px;border:1px solid var(--line);background:#0f141d;color:var(--text);cursor:pointer;text-align:left;font-weight:600}
  .asset.active{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
  .row{display:grid;gap:10px;grid-template-columns:1fr}
  input,select,button{font:inherit;border-radius:12px;border:1px solid var(--line);background:#0f141d;color:var(--text);padding:12px;width:100%}
  input::placeholder{color:#5b6b83}
  button{cursor:pointer;font-weight:700}
  .btn-primary{background:linear-gradient(180deg,#7df0c5,#4bcf9a);color:#052a1c;border:none}
  .btn-ghost{background:#10151f}
  .cards4{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
  .price-live{display:flex;align-items:center;gap:10px;font-size:14px;color:var(--muted)}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--good);box-shadow:0 0 8px var(--good)}
  table{width:100%;border-collapse:collapse;min-width:900px}
  th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;font-size:14px}
  th{color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--card)}
  .tbl-wrap{overflow:auto;border-radius:14px;border:1px solid var(--line)}
  .badge{padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700}
  .badge.open{background:rgba(89,216,168,.15);color:var(--accent)}
  .badge.closed{background:rgba(147,161,181,.15);color:var(--muted)}
  .ok{color:var(--good)} .err{color:var(--bad)}
  #toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:#10151f;border:1px solid var(--line);padding:10px 16px;border-radius:12px;font-size:14px;opacity:0;transition:.3s}
  #toast.show{opacity:1}
  @media(min-width:960px){
    .grid2{grid-template-columns:1.1fr .9fr}
    .assets{grid-template-columns:repeat(4,1fr)}
    .cards4{grid-template-columns:repeat(4,1fr)}
    .stats{grid-template-columns:repeat(4,1fr)}
    .row{grid-template-columns:repeat(2,1fr)}
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="card hero">
    <div><h1>Trade Hub</h1><p class="muted" style="margin:6px 0 0">Suivi de positions, prix en direct, break-even et objectif de gain.</p></div>
    <div class="pill" id="clock">--:--:--</div>
  </div>

  <div class="card">
    <h2>Résumé</h2>
    <div class="stats">
      <div class="kpi"><div class="l">Trades ouverts</div><div class="v" id="kOpen">0</div></div>
      <div class="kpi"><div class="l">Trades clôturés</div><div class="v" id="kClosed">0</div></div>
      <div class="kpi"><div class="l">PnL net réalisé</div><div class="v" id="kNet">0,00 €</div></div>
      <div class="kpi"><div class="l">Taux de réussite</div><div class="v" id="kWin">0 %</div></div>
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Nouveau trade</h2>
      <div class="assets" id="assets"></div>
      <div class="price-live" style="margin-top:10px">
        <span class="dot"></span>
        <span>Prix marché en direct : <b id="livePriceLabel">—</b></span>
      </div>
      <div class="row" style="margin-top:12px">
        <input id="date" type="date" />
        <input id="buyPrice" type="number" step="0.0001" placeholder="Prix d'achat" />
        <input id="amountEUR" type="number" step="0.01" placeholder="Montant investi €" />
        <input id="feesEUR" type="number" step="0.01" value="2" placeholder="Frais €" />
        <input id="targetNetEUR" type="number" step="0.01" value="2" placeholder="Objectif net €" />
        <input id="note" placeholder="Note (setup, raison...)" />
      </div>
      <div class="cards4" style="margin-top:12px">
        <div class="kpi"><div class="l">Quantité</div><div class="v" id="qtyOut">—</div></div>
        <div class="kpi"><div class="l">Break-even</div><div class="v" id="beOut">—</div></div>
        <div class="kpi"><div class="l">Vente cible</div><div class="v" id="targetOut">—</div></div>
        <div class="kpi"><div class="l">Distance objectif</div><div class="v" id="distOut">—</div></div>
      </div>
      <div class="row" style="margin-top:14px">
        <button class="btn-primary" id="saveBtn">Ajouter le trade</button>
        <button class="btn-ghost" id="refreshBtn">Rafraîchir</button>
      </div>
      <p class="muted" id="status" style="margin-top:8px"></p>
    </div>

    <div class="card">
      <h2>Fermer un trade</h2>
      <select id="openTrades"></select>
      <div class="row" style="margin-top:10px">
        <input id="closeDate" type="date" />
        <input id="closePrice" type="number" step="0.0001" placeholder="Prix de clôture" />
      </div>
      <input id="closeNote" placeholder="Note de clôture" style="margin-top:10px" />
      <div class="cards4" style="margin-top:12px">
        <div class="kpi"><div class="l">Gain net estimé</div><div class="v" id="closeNetOut">—</div></div>
        <div class="kpi"><div class="l">Durée</div><div class="v" id="closeDurOut">—</div></div>
      </div>
      <button class="btn-primary" id="closeBtn" style="margin-top:14px">Clôturer le trade</button>
    </div>
  </div>

  <div class="card">
    <h2>Historique des positions</h2>
    <div class="tbl-wrap">
      <table>
        <thead><tr>
          <th>Statut</th><th>Ouverture</th><th>Clôture</th><th>Durée</th><th>Actif</th>
          <th>Achat</th><th>Marché</th><th>Cible</th><th>Distance</th><th>Montant</th><th>Net</th><th>Note</th>
        </tr></thead>
        <tbody id="history"><tr><td colspan="12" class="muted">Aucune donnée</td></tr></tbody>
      </table>
    </div>
  </div>
</div>
<div id="toast"></div>

<script>
const ASSET_NAMES = ["Or","Pétrole Brent","Nasdaq-100","TotalEnergies"];
const $ = id => document.getElementById(id);
let asset = ASSET_NAMES[0];
let rows = [];
let livePrice = null;

function today(){ return new Date().toISOString().slice(0,10); }
$('date').value = today();
$('closeDate').value = today();

function toast(msg){ const t=$('toast'); t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2200); }
function n(v){ return Number(v) || 0; }
function fr(v,d=4){ return Number.isFinite(v) ? new Intl.NumberFormat('fr-FR',{maximumFractionDigits:d}).format(v) : '—'; }
function eur(v){ return Number.isFinite(v) ? new Intl.NumberFormat('fr-FR',{style:'currency',currency:'EUR',maximumFractionDigits:2}).format(v) : '—'; }

function renderAssetButtons(){
  $('assets').innerHTML = ASSET_NAMES.map(a => `<button class="asset ${a===asset?'active':''}" data-a="${a}">${a}</button>`).join('');
  document.querySelectorAll('.asset').forEach(b => b.onclick = () => { asset = b.dataset.a; renderAssetButtons(); refreshPrice(); });
}
renderAssetButtons();

async function refreshPrice(){
  try{
    const r = await fetch('/api/price/' + encodeURIComponent(asset));
    const d = await r.json();
    livePrice = d.price;
    $('livePriceLabel').textContent = livePrice ? fr(livePrice,4) : 'indisponible';
  }catch(e){ $('livePriceLabel').textContent = 'indisponible'; }
  updateCalc();
}

function updateCalc(){
  const bp = n($('buyPrice').value), amt = n($('amountEUR').value), fees = n($('feesEUR').value), target = n($('targetNetEUR').value);
  if(bp<=0 || amt<=0){ $('qtyOut').textContent='—'; $('beOut').textContent='—'; $('targetOut').textContent='—'; $('distOut').textContent='—'; return; }
  const qty = amt/bp;
  const be = (amt+fees)/qty;
  const targetSell = (amt+fees+target)/qty;
  const dist = livePrice ? targetSell - livePrice : null;
  $('qtyOut').textContent = fr(qty,6);
  $('beOut').textContent = fr(be,4);
  $('targetOut').textContent = fr(targetSell,4);
  $('distOut').textContent = dist===null ? '—' : (dist<=0 ? 'Objectif atteint' : fr(dist,4));
}

async function loadTrades(){
  const r = await fetch('/api/trades');
  const d = await r.json();
  rows = d.trades || [];
  renderStats(); renderHistory(); fillOpenSelect();
}

function renderStats(){
  const open = rows.filter(r=>r.status==='open');
  const closed = rows.filter(r=>r.status==='closed');
  const net = closed.reduce((s,r)=>s+n(r.realizedNetEUR),0);
  const wins = closed.filter(r=>n(r.realizedNetEUR)>0).length;
  $('kOpen').textContent = open.length;
  $('kClosed').textContent = closed.length;
  $('kNet').textContent = eur(net);
  $('kWin').textContent = closed.length ? fr((wins/closed.length)*100,1)+' %' : '0 %';
}

function fillOpenSelect(){
  const open = rows.filter(r=>r.status==='open');
  $('openTrades').innerHTML = open.length
    ? open.map(r=>`<option value="${r.id}">${r.asset} · ${r.date} · ${eur(n(r.amountEUR))}</option>`).join('')
    : '<option value="">Aucun trade ouvert</option>';
}

function renderHistory(){
  if(!rows.length){ $('history').innerHTML = '<tr><td colspan="12" class="muted">Aucune donnée</td></tr>'; return; }
  $('history').innerHTML = rows.slice().reverse().map(r=>{
    const isClosed = r.status==='closed';
    const badge = isClosed ? '<span class="badge closed">Clos</span>' : '<span class="badge open">Ouvert</span>';
    const net = n(isClosed ? r.realizedNetEUR : r.unrealizedNetEUR);
    const cls = net>0?'ok':net<0?'err':'';
    return `<tr>
      <td>${badge}</td><td>${r.date||''}</td><td>${r.closeDate||''}</td><td>${r.durationDays??''}</td>
      <td>${r.asset||''}</td><td>${fr(n(r.buyPriceUsed),4)}</td><td>${r.marketPriceNow?fr(n(r.marketPriceNow),4):(isClosed?fr(n(r.closePrice),4):'—')}</td>
      <td>${fr(n(r.targetSellPrice),4)}</td><td>${r.distance!=null?fr(n(r.distance),4):'—'}</td>
      <td>${eur(n(r.amountEUR))}</td><td class="${cls}">${eur(net)}</td><td>${r.closeNote||r.note||''}</td>
    </tr>`;
  }).join('');
}

async function saveTrade(){
  const bp=n($('buyPrice').value), amt=n($('amountEUR').value);
  if(bp<=0||amt<=0){ toast('Prix et montant requis'); return; }
  const payload = { date:$('date').value, asset, buyPriceUsed:bp, amountEUR:amt, feesEUR:n($('feesEUR').value), targetNetEUR:n($('targetNetEUR').value), note:$('note').value };
  const r = await fetch('/api/add', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const d = await r.json();
  toast(d.ok?'Trade ajouté':'Erreur'); await loadTrades();
  $('buyPrice').value=''; $('amountEUR').value=''; $('note').value='';
}

async function closeTradeFn(){
  const id = $('openTrades').value;
  if(!id){ toast('Aucun trade sélectionné'); return; }
  const payload = { id, closeDate:$('closeDate').value, closePrice:n($('closePrice').value), closeNote:$('closeNote').value };
  const r = await fetch('/api/close', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const d = await r.json();
  toast(d.ok?'Trade clôturé':'Erreur'); await loadTrades();
}

document.querySelectorAll('#buyPrice,#amountEUR,#feesEUR,#targetNetEUR').forEach(el=>el.addEventListener('input', updateCalc));
$('saveBtn').onclick = saveTrade;
$('closeBtn').onclick = closeTradeFn;
$('refreshBtn').onclick = () => { refreshPrice(); loadTrades(); };

function tickClock(){ $('clock').textContent = new Date().toLocaleTimeString('fr-FR'); }
setInterval(tickClock, 1000); tickClock();

refreshPrice();
loadTrades();
setInterval(refreshPrice, 30000);
setInterval(loadTrades, 30000);
</script>
</body>
</html>
"""

@app.get("/")
def home():
    return render_template_string(INDEX_HTML)

@app.get("/api/price/<asset>")
def api_price(asset):
    price = fetch_live_price(asset)
    return jsonify({"asset": asset, "price": price})

@app.get("/api/trades")
def api_trades():
    rows = load_data()
    for r in rows:
        live = fetch_live_price(r.get("asset", ""))
        qty, be, target_sell, unreal, dist = compute_open_metrics(r, live)
        r["quantity"] = round(qty, 6)
        r["breakEvenPrice"] = round(be, 4)
        r["targetSellPrice"] = round(target_sell, 4)
        r["marketPriceNow"] = live
        if r.get("status") == "open":
            r["unrealizedNetEUR"] = round(unreal, 4) if unreal is not None else None
            r["distance"] = round(dist, 4) if dist is not None else None
    return jsonify({"ok": True, "trades": rows})

@app.post("/api/add")
def api_add():
    data = request.get_json(force=True)
    rows = load_data()
    row = {
        "id": f"T{int(time.time()*1000)}",
        "status": "open",
        "date": data.get("date", ""),
        "closeDate": "",
        "closePrice": None,
        "durationDays": None,
        "asset": data.get("asset", ""),
        "buyPriceUsed": float(data.get("buyPriceUsed", 0) or 0),
        "amountEUR": float(data.get("amountEUR", 0) or 0),
        "feesEUR": float(data.get("feesEUR", 0) or 0),
        "targetNetEUR": float(data.get("targetNetEUR", 0) or 0),
        "realizedNetEUR": None,
        "note": data.get("note", ""),
        "closeNote": "",
        "createdAt": datetime.utcnow().isoformat(),
    }
    rows.append(row)
    save_data(rows)
    return jsonify({"ok": True, "id": row["id"]})

@app.post("/api/close")
def api_close():
    data = request.get_json(force=True)
    rows = load_data()
    found = False
    for r in rows:
        if r["id"] == data.get("id") and r.get("status") == "open":
            buy = float(r.get("buyPriceUsed", 0) or 0)
            amt = float(r.get("amountEUR", 0) or 0)
            fees = float(r.get("feesEUR", 0) or 0)
            qty = (amt / buy) if buy else 0
            close_price = float(data.get("closePrice", 0) or 0)
            net = (close_price - buy) * qty - fees
            try:
                d1 = date.fromisoformat(r.get("date") or data.get("closeDate"))
                d2 = date.fromisoformat(data.get("closeDate"))
                duration = (d2 - d1).days
            except Exception:
                duration = None
            r["status"] = "closed"
            r["closeDate"] = data.get("closeDate", "")
            r["closePrice"] = close_price
            r["durationDays"] = duration
            r["realizedNetEUR"] = round(net, 4)
            r["closeNote"] = data.get("closeNote", "")
            found = True
            break
    save_data(rows)
    return jsonify({"ok": found})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)