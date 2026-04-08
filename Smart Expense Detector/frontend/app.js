// ============================================================
// app.js — LeakSense Frontend Logic
// Connects to the Smart Expense Leak Detector FastAPI backend
// ============================================================

const API = 'http://localhost:8000';

// ── State ──────────────────────────────────────────────────────────────────
let expenses = [];   // local expense rows (before upload)
let rowId    = 0;
let lastAnalysis = null; // cache last pipeline result

const CATEGORIES = [
  'Food','Subscriptions','Utilities','Transport','Shopping',
  'Entertainment','Healthcare','SaaS','Travel','Consulting',
  'Office Supplies','Marketing','Accommodation','Gifts','Parking',
  'Rent','Restaurant','Groceries','Education','Others'
];

// ── Custom cursor ──────────────────────────────────────────────────────────
const cur  = document.getElementById('cursor');
const ring = document.getElementById('cursor-ring');
let mx=0, my=0, rx=0, ry=0;

document.addEventListener('mousemove', e => {
  mx = e.clientX; my = e.clientY;
  cur.style.left = mx + 'px'; cur.style.top = my + 'px';
});
(function animRing() {
  rx += (mx - rx) * 0.12; ry += (my - ry) * 0.12;
  ring.style.left = rx + 'px'; ring.style.top = ry + 'px';
  requestAnimationFrame(animRing);
})();

// ── API Status check ───────────────────────────────────────────────────────
async function checkAPIStatus() {
  const dot  = document.getElementById('apiDot');
  const txt  = document.getElementById('apiTxt');
  try {
    const res = await fetch(`${API}/health`, { signal: AbortSignal.timeout(3000) });
    const data = await res.json();
    if (data.status === 'healthy' || data.status === 'online') {
      dot.className = 'api-dot online';
      txt.textContent = 'API online';
    } else {
      throw new Error('unhealthy');
    }
  } catch {
    dot.className = 'api-dot offline';
    txt.textContent = 'API offline';
  }
}
checkAPIStatus();
setInterval(checkAPIStatus, 15000);

// ── Navigation helpers ─────────────────────────────────────────────────────
function scrollToAnalyze() {
  document.getElementById('analyze').scrollIntoView({ behavior: 'smooth' });
}

// ── Toast ──────────────────────────────────────────────────────────────────
function showToast(msg, isError = false) {
  const t = document.getElementById('toast');
  document.getElementById('toastMsg').textContent = msg;
  t.classList.toggle('error', isError);
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2800);
}

// ── Row management ─────────────────────────────────────────────────────────
function addRow(desc = '', amt = '', cat = 'Others', date = '', vendor = '') {
  const today = date || new Date().toISOString().split('T')[0];
  const id    = ++rowId;
  const div   = document.createElement('div');
  div.className = 'expense-row';
  div.id        = 'row-' + id;
  // Use vendor if provided, else fall back to desc for the vendor column
  const vendorVal = vendor || desc;
  div.innerHTML = `
    <input placeholder="e.g. Netflix monthly subscription" value="${desc}" id="desc-${id}" oninput="updateExpense(${id})"/>
    <input placeholder="0" type="number" value="${amt}" id="amt-${id}" oninput="updateExpense(${id})"/>
    <select class="col-cat" id="cat-${id}" onchange="updateExpense(${id})">
      ${CATEGORIES.map(c => `<option value="${c}" ${c === cat ? 'selected' : ''}>${c}</option>`).join('')}
    </select>
    <input class="col-date" type="date" value="${today}" id="date-${id}" oninput="updateExpense(${id})"/>
    <button class="delete-btn" onclick="deleteRow(${id})">✕</button>
  `;
  document.getElementById('expenseRows').appendChild(div);
  expenses.push({ id, desc, vendor: vendorVal, amt: parseFloat(amt) || 0, cat, date: today });
}

function updateExpense(id) {
  const i = expenses.findIndex(e => e.id === id);
  if (i === -1) return;
  expenses[i].desc   = document.getElementById('desc-' + id).value;
  expenses[i].vendor = document.getElementById('desc-' + id).value; // desc = vendor name
  expenses[i].amt    = parseFloat(document.getElementById('amt-' + id).value) || 0;
  expenses[i].cat    = document.getElementById('cat-' + id).value;
  expenses[i].date   = document.getElementById('date-' + id).value;
}

function deleteRow(id) {
  document.getElementById('row-' + id)?.remove();
  expenses = expenses.filter(e => e.id !== id);
  showToast('Row removed');
}

// ── Demo data ──────────────────────────────────────────────────────────────
function loadDemo() {
  document.getElementById('expenseRows').innerHTML = '';
  expenses = []; rowId = 0;
  const demo = [
    { d:'Lunch order',     a:'250',   c:'Food',          v:'Zomato',    dt:'2026-03-01' },
    { d:'Office commute',  a:'1200',  c:'Transport',     v:'Uber',      dt:'2026-03-01' },
    { d:'Headphones',      a:'5000',  c:'Shopping',      v:'Amazon',    dt:'2026-03-02' },
    { d:'Dinner',          a:'300',   c:'Food',          v:'Swiggy',    dt:'2026-03-03' },
    { d:'Monthly rent',    a:'15000', c:'Rent',          v:'Landlord',  dt:'2026-03-04' },
    { d:'Subscription',    a:'700',   c:'Entertainment', v:'Netflix',   dt:'2026-03-05' },
    { d:'Snacks',          a:'450',   c:'Food',          v:'Zomato',    dt:'2026-03-06' },
    { d:'Clothes',         a:'2000',  c:'Shopping',      v:'Flipkart',  dt:'2026-03-07' },
    { d:'Travel',          a:'800',   c:'Transport',     v:'Ola',       dt:'2026-03-08' },
    { d:'Family dinner',   a:'1200',  c:'Food',          v:'Restaurant',dt:'2026-03-09' },
    { d:'Shoes',           a:'3000',  c:'Shopping',      v:'Amazon',    dt:'2026-03-10' },
    { d:'Movie tickets',   a:'600',   c:'Entertainment', v:'BookMyShow',dt:'2026-03-11' },
    { d:'Lunch',           a:'400',   c:'Food',          v:'Swiggy',    dt:'2026-03-12' },
    { d:'Monthly bill',    a:'2500',  c:'Utilities',     v:'Electricity',dt:'2026-03-13'},
    { d:'Party order',     a:'1800',  c:'Food',          v:'Zomato',    dt:'2026-03-14' },
    { d:'Airport ride',    a:'900',   c:'Transport',     v:'Uber',      dt:'2026-03-15' },
    { d:'Jacket',          a:'2200',  c:'Shopping',      v:'Myntra',    dt:'2026-03-16' },
    { d:'Coffee',          a:'350',   c:'Food',          v:'Local Cafe',dt:'2026-03-17' },
    { d:'Subscription',    a:'500',   c:'Entertainment', v:'Spotify',   dt:'2026-03-18' },
    { d:'Friends outing',  a:'2700',  c:'Food',          v:'Restaurant',dt:'2026-03-19' },
  ];
  demo.forEach(r => addRow(r.d, r.a, r.c, r.dt, r.v));
  showToast('Demo data loaded — 20 rows. Hit Analyze →');
  document.getElementById('analyze').scrollIntoView({ behavior: 'smooth' });
}

// ── CSV upload: parse locally → send as bulk JSON ──────────────────────────
function handleCSV(input) {
  const file = input.files[0];
  if (!file) return;

  showToast('Parsing CSV…');
  const reader = new FileReader();
  reader.onload = e => {
    const lines = e.target.result.split('\n').filter(l => l.trim());
    if (lines.length < 2) { showToast('CSV is empty!', true); return; }

    // Detect header columns (case-insensitive)
    const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/"/g,''));

    document.getElementById('expenseRows').innerHTML = '';
    expenses = []; rowId = 0;

    let loaded = 0;
    lines.slice(1).forEach(line => {
      const cols = line.split(',').map(s => s.trim().replace(/"/g, ''));
      if (cols.length < 2) return;

      // Map by header name, with numeric fallbacks
      const get = (name, fallback) => {
        const idx = headers.indexOf(name);
        return idx >= 0 ? (cols[idx] || '') : (cols[fallback] || '');
      };

      const desc   = get('description', 0);
      const amt    = get('amount', 1);
      const cat    = get('category', 2) || 'Others';
      const date   = get('date', 3) || '';
      const vendor = get('vendor', 4) || desc;
      // id column is intentionally skipped — backend assigns its own IDs

      if (desc && parseFloat(amt) > 0) {
        addRow(desc, amt, cat, date, vendor);
        loaded++;
      }
    });

    showToast(`✅ Loaded ${loaded} rows from ${file.name}`);
    // Clear the file input so same file can be re-selected
    input.value = '';
  };
  reader.readAsText(file);
}

// Drag-and-drop support
const uploadZone = document.getElementById('uploadZone');
uploadZone.addEventListener('dragover',  e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  const dt = e.dataTransfer;
  if (dt?.files[0]) {
    const inp = document.getElementById('fileInput');
    // Use DataTransfer to set files on the input
    inp.files = dt.files;
    handleCSV(inp);
  }
});

// ── Loading overlay helpers ────────────────────────────────────────────────
function showLoading(stageText = '') {
  document.getElementById('loadingOverlay').classList.add('active');
  setLoadingStage(stageText);
}
function hideLoading() {
  document.getElementById('loadingOverlay').classList.remove('active');
}
function setLoadingStage(txt) {
  const el = document.getElementById('loadingStage');
  if (el) el.textContent = txt;
}

// ── Reset database ─────────────────────────────────────────────────────────
async function resetDatabase() {
  if (!confirm('This will DELETE ALL expenses and alerts from the database. Are you sure?')) return;
  showLoading('Resetting database…');
  try {
    const res = await fetch(`${API}/expenses`, { method: 'DELETE' });
    const data = await res.json();
    hideLoading();
    // Clear UI
    document.getElementById('expenseRows').innerHTML = '';
    expenses = []; rowId = 0;
    document.getElementById('results').style.display = 'none';
    document.getElementById('results').classList.remove('visible');
    document.getElementById('resultsContainer').innerHTML = '';
    showToast(`Database cleared — ${data.message}`);
  } catch (err) {
    hideLoading();
    showToast('Failed to reset database: ' + err.message, true);
  }
}

// ── Main analysis flow ─────────────────────────────────────────────────────
async function analyzeExpenses() {
  const rows = expenses.filter(e => (e.desc || e.vendor) && e.amt > 0);
  if (rows.length < 1) { showToast('Add at least 1 expense!', true); return; }

  const btn = document.querySelector('.analyze-btn');
  btn.disabled = true;
  showLoading('Uploading expenses…');

  try {
    // ── Step 1: Upload expenses to backend ──────────────────────────────
    setLoadingStage('Step 1/3 — Uploading expenses to backend…');
    const uploadPayload = {
      expenses: rows.map(r => ({
        date:        r.date,
        amount:      r.amt,
        category:    r.cat,
        vendor:      r.vendor || r.desc || 'Unknown',
        description: r.desc || r.vendor || '',
      }))
    };

    const uploadRes = await fetch(`${API}/expenses/upload/bulk`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(uploadPayload),
    });

    if (!uploadRes.ok) {
      const err = await uploadRes.json().catch(() => ({}));
      throw new Error(err.detail || `Upload failed (${uploadRes.status})`);
    }
    const uploadData = await uploadRes.json();
    showToast(`✅ Uploaded ${uploadData.inserted_count} expense(s) | ${uploadData.alerts_generated} alerts generated`);

    // ── Step 2: Run the unified analysis pipeline ───────────────────────
    setLoadingStage('Step 2/3 — Running Graph + CSP + A* pipeline…');
    const analysisRes = await fetch(`${API}/analyze-expenses?top_anomalies=10`);
    if (!analysisRes.ok) throw new Error(`Analysis failed (${analysisRes.status})`);
    const analysis = await analysisRes.json();
    lastAnalysis = analysis;

    // ── Step 3: Render results ──────────────────────────────────────────
    setLoadingStage('Step 3/3 — Building your report…');
    await new Promise(r => setTimeout(r, 500));

    renderResults(analysis, rows);

    hideLoading();
    document.getElementById('results').scrollIntoView({ behavior: 'smooth' });

  } catch (err) {
    hideLoading();
    showToast(`Error: ${err.message}`, true);
    console.error('[LeakSense] Pipeline error:', err);

    // Graceful fallback — local analysis
    if (rows.length > 0) {
      showToast('Showing local analysis (backend unavailable)', true);
      renderLocalFallback(rows);
    }
  } finally {
    btn.disabled = false;
  }
}

// ── Render pipeline results from backend ───────────────────────────────────
function renderResults(analysis, rows) {
  const el  = document.getElementById('results');
  const con = document.getElementById('resultsContainer');
  el.style.display = 'block'; el.classList.add('visible');

  const { meta, graph_insights, csp_violations, ranked_anomalies, alerts, summary } = analysis;

  // Compliance → health score
  const compliance = summary.compliance_pct || csp_violations?.compliance_score_pct || 0;
  const score      = Math.round(compliance);
  const grade      = score >= 85 ? 'A' : score >= 70 ? 'B' : score >= 55 ? 'C' : score >= 40 ? 'D' : 'F';
  const verdict    = score >= 85 ? 'Excellent — spending well in control'      :
                     score >= 70 ? 'Good shape, a few leaks worth fixing'      :
                     score >= 55 ? 'Several leaks draining your budget'        :
                     score >= 40 ? 'Significant financial leakage detected'    : 'Critical — money is flowing out fast';

  const gradeColor = grade === 'A' ? 'var(--accent)' : grade === 'B' ? '#64c8ff' :
                     grade === 'C' ? 'var(--warn)' : 'var(--accent2)';
  const circum = 2 * Math.PI * 54;

  // Build category spend map from CSP violations + uploaded rows
  const catSpend = {};
  rows.forEach(r => { catSpend[r.cat] = (catSpend[r.cat] || 0) + r.amt; });
  const catEntries = Object.entries(catSpend).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const maxCat     = catEntries[0]?.[1] || 1;
  const BAR_COLORS = ['var(--accent)','var(--accent3)','var(--warn)','var(--accent2)','#64c8ff','#f0a0ff','#80ffaa','#ffaa80'];

  // Top alerts (severity sorted)
  const topAlerts = (alerts || []).slice(0, 9);
  const totalEstSaving = Math.round(
    (ranked_anomalies?.top_anomalies || []).reduce((s,a) => s + (a.g_score || 0), 0) * 0.4
  );
  const totalAnomalies = ranked_anomalies?.total_detected || 0;
  const cspViolCount   = csp_violations?.violations_count || 0;
  const topCat         = graph_insights?.bfs?.top_spend_categories?.[0];
  const topAnom        = ranked_anomalies?.top_anomalies?.[0];

  con.innerHTML = `
    <!-- Score Card -->
    <div class="section-tag">// Results</div>
    <h2 class="section-title" style="margin-bottom:32px">Your Financial <em>Health Report</em></h2>

    <div class="score-hero">
      <div class="score-ring-wrap">
        <svg class="score-svg" viewBox="0 0 120 120">
          <circle class="score-ring-bg" cx="60" cy="60" r="54"/>
          <circle class="score-ring-fg" id="scoreRing" cx="60" cy="60" r="54"
            stroke="${gradeColor}" stroke-dasharray="${circum}" stroke-dashoffset="${circum}"/>
          <text x="60" y="56" text-anchor="middle" fill="${gradeColor}" font-family="Syne,sans-serif" font-weight="800" font-size="28">${score}</text>
          <text x="60" y="70" text-anchor="middle" fill="#5a6070" font-family="DM Mono,monospace" font-size="9">/100</text>
        </svg>
      </div>
      <div class="score-info">
        <div class="score-grade" style="color:${gradeColor}">${grade}</div>
        <div class="score-verdict">${verdict}</div>
        <div class="score-meta">
          <div class="score-meta-item">
            <div class="label">Total Spend</div>
            <div class="value">₹${meta.total_spend.toLocaleString('en-IN')}</div>
          </div>
          <div class="score-meta-item">
            <div class="label">Transactions</div>
            <div class="value">${meta.expense_count}</div>
          </div>
          <div class="score-meta-item">
            <div class="label">CSP Violations</div>
            <div class="value" style="color:var(--accent2)">${cspViolCount}</div>
          </div>
          <div class="score-meta-item">
            <div class="label">Anomalies Found</div>
            <div class="value" style="color:var(--warn)">${totalAnomalies}</div>
          </div>
          <div class="score-meta-item">
            <div class="label">Est. Recoverable</div>
            <div class="value" style="color:var(--accent)">₹${totalEstSaving.toLocaleString('en-IN')}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Pipeline Stage Summary Cards -->
    <div class="section-tag" style="margin-top:48px">// Pipeline Engine Output</div>
    <div class="pipeline-stages">
      <div class="stage-card">
        <div class="stage-label">📊 Graph Nodes</div>
        <div class="stage-value">${graph_insights?.node_count || 0}</div>
        <div class="stage-sub">${graph_insights?.category_count || 0} categories · ${graph_insights?.vendor_count || 0} vendors</div>
      </div>
      <div class="stage-card">
        <div class="stage-label">🔍 BFS Top Category</div>
        <div class="stage-value">${topCat?.to?.replace('Category:','') || '—'}</div>
        <div class="stage-sub">₹${(topCat?.total_amount || 0).toLocaleString('en-IN')} total spend</div>
      </div>
      <div class="stage-card">
        <div class="stage-label">🧵 DFS Chains</div>
        <div class="stage-value">${graph_insights?.dfs?.total_chains_found || 0}</div>
        <div class="stage-sub">Deepest: ₹${(graph_insights?.dfs?.highest_spend_chain?.total_amount || 0).toLocaleString('en-IN')}</div>
      </div>
      <div class="stage-card">
        <div class="stage-label">⚖️ CSP Compliance</div>
        <div class="stage-value">${compliance}%</div>
        <div class="stage-sub">${csp_violations?.satisfied_count || 0}/${csp_violations?.total_vars_checked || 0} budgets passed</div>
      </div>
      <div class="stage-card">
        <div class="stage-label">⭐ A* Top Priority</div>
        <div class="stage-value">${topAnom ? 'f=' + (topAnom.f_score || 0).toFixed(0) : '—'}</div>
        <div class="stage-sub">${topAnom?.anomaly_type || 'No anomalies'} · rank #1</div>
      </div>
      <div class="stage-card">
        <div class="stage-label">🚨 Total Alerts</div>
        <div class="stage-value">${summary?.total_alerts || 0}</div>
        <div class="stage-sub">${summary?.by_severity?.CRITICAL || 0} critical · ${summary?.by_severity?.HIGH || 0} high</div>
      </div>
    </div>

    <!-- Detected Leak Alerts -->
    <div class="section-tag" style="margin-top:48px">// Detected Leaks (Severity-Sorted)</div>
    <h3 class="section-title" style="font-size:28px;margin-bottom:0">
      ${topAlerts.length} leak alert${topAlerts.length !== 1 ? 's' : ''} <em>detected</em>
    </h3>
    ${topAlerts.length === 0 ? '<p style="color:var(--muted);margin-top:16px">No leaks detected — your spending is within budget! 🎉</p>' : ''}
    <div class="leaks-grid">
      ${topAlerts.map((a, i) => {
        const amount = a.overspent || a.g_score || 0;
        const name   = a.vendor || a.category || 'Spending Alert';
        return `
        <div class="leak-card leak-${a.severity}" style="animation-delay:${i * 0.07}s">
          <div class="leak-source-badge">${a.source}</div>
          <div class="leak-severity"><div class="sev-dot"></div>${a.severity}</div>
          <div class="leak-name">${name}</div>
          <div class="leak-amount">₹${amount.toLocaleString('en-IN')}</div>
          <div class="leak-tip">${a.message}</div>
          ${a.month ? `<div class="leak-meta">📅 ${a.month}</div>` : ''}
          ${a.active_months?.length ? `<div class="leak-meta">📍 Active: ${a.active_months.join(', ')}</div>` : ''}
        </div>`;
      }).join('')}
    </div>

    <!-- Spending Chart -->
    ${catEntries.length ? `
    <div class="chart-wrap" style="margin-top:40px">
      <div class="chart-title">Spending Breakdown by Category</div>
      <div class="bar-chart">
        ${catEntries.map(([cat, amt], i) => `
          <div class="bar-row">
            <div class="bar-label">${cat}</div>
            <div class="bar-track">
              <div class="bar-fill" id="bar-${i}" style="width:0%;background:${BAR_COLORS[i % BAR_COLORS.length]}"></div>
            </div>
            <div class="bar-val" style="color:${BAR_COLORS[i % BAR_COLORS.length]}">₹${amt.toLocaleString('en-IN')}</div>
          </div>
        `).join('')}
      </div>
    </div>` : ''}

    <!-- AI Pipeline Summary -->
    <div class="ai-summary" style="margin-top:32px">
      <div class="ai-badge">⬡ Graph + CSP + A* Analysis</div>
      <div class="ai-text">
        Your total spend is <strong>₹${meta.total_spend.toLocaleString('en-IN')}</strong> across
        <strong>${meta.expense_count} transactions</strong>.
        The <strong>Graph engine</strong> mapped <strong>${graph_insights?.node_count || 0} nodes</strong> across
        <strong>${graph_insights?.dfs?.total_chains_found || 0} spending chains</strong>
        — top category: <strong>${topCat?.to?.replace('Category:','') || 'N/A'}</strong>
        (₹${(topCat?.total_amount || 0).toLocaleString('en-IN')}).
        <br/><br/>
        The <strong>CSP constraint engine</strong> checked
        <strong>${csp_violations?.total_vars_checked || 0} budget variables</strong>
        and found <strong>${cspViolCount} violations</strong>
        (compliance: <strong>${compliance}%</strong>).
        ${csp_violations?.worst_offender ? `Worst offender: <strong>${csp_violations.worst_offender.label}</strong> at ${csp_violations.worst_offender.overspent_pct}% overspent.` : ''}
        <br/><br/>
        The <strong>A* ranker</strong> prioritized <strong>${totalAnomalies} anomalies</strong>.
        ${topAnom ? `Top priority: <strong>${topAnom.anomaly_type}</strong> at <strong>${(topAnom.vendor || topAnom.category || '')}</strong>
        (f-score: ${topAnom.f_score?.toFixed(0)}, g=₹${topAnom.g_score?.toLocaleString('en-IN')}).` : ''}
        ${summary?.top_recommendation ? `<br/><br/>⚡ <strong>Priority action:</strong> ${summary.top_recommendation}` : ''}
      </div>
    </div>

    <!-- Action Plan -->
    <div class="section-tag" style="margin-top:48px">// Action Plan</div>
    <h3 class="section-title" style="font-size:28px;margin-bottom:24px">Your personalized <em>fix list</em></h3>
    <div class="rec-list">
      ${buildRecsFromAnalysis(analysis).map((rec, i) => `
        <div class="rec-item" style="animation-delay:${i * 0.1}s">
          <div class="rec-num">${String(i + 1).padStart(2, '0')}</div>
          <div class="rec-body">
            <div class="rec-title">${rec.title}</div>
            <div class="rec-desc">${rec.desc}</div>
            <div class="rec-save">${rec.saving}</div>
          </div>
        </div>
      `).join('')}
    </div>

    <!-- Reset button -->
    <div style="text-align:center;margin-top:48px;padding-bottom:24px">
      <button onclick="resetDatabase()" style="
        background:rgba(255,77,109,0.1);border:1px solid rgba(255,77,109,0.3);
        color:var(--accent2);padding:12px 28px;border-radius:10px;
        font-family:var(--font-head);font-weight:600;font-size:13px;
        cursor:none;transition:all .2s;
      ">🗑️ Reset Database & Start Fresh</button>
    </div>
  `;

  // Animate score ring
  setTimeout(() => {
    const ringEl = document.getElementById('scoreRing');
    if (ringEl) ringEl.style.strokeDashoffset = circum * (1 - score / 100);
    catEntries.forEach(([, amt], i) => {
      const bar = document.getElementById('bar-' + i);
      if (bar) setTimeout(() => { bar.style.width = (amt / maxCat * 100) + '%'; }, i * 80);
    });
  }, 120);
}

// ── Build action recommendations from backend analysis ──────────────────────
function buildRecsFromAnalysis(analysis) {
  const recs = [];
  const violations = analysis.csp_violations?.violations || [];
  const anomalies  = analysis.ranked_anomalies?.top_anomalies || [];

  // Top CSP violations → fix recommendations
  violations.filter(v => ['CRITICAL','HIGH'].includes(v.severity)).slice(0, 2).forEach(v => {
    recs.push({
      title: `Reduce ${v.label || v.variable} spending`,
      desc:  `${v.message}. Cut this category by ${(v.overspent_pct / 2).toFixed(0)}% to restore compliance.`,
      saving: `Recover ₹${Math.round(v.overspent / 2).toLocaleString('en-IN')}/mo`,
    });
  });

  // Recurring vendor anomalies
  anomalies.filter(a => a.anomaly_type === 'RECURRING_VENDOR').slice(0, 2).forEach(a => {
    recs.push({
      title: `Audit recurring vendor: ${a.vendor}`,
      desc:  `${a.vendor} has been active across ${a.month_count} months totalling ₹${(a.total_spent || 0).toLocaleString('en-IN')}. Review if fully essential.`,
      saving: `Potential ₹${Math.round((a.total_spent || 0) * 0.25).toLocaleString('en-IN')}/mo saving`,
    });
  });

  // High-spend single transactions
  anomalies.filter(a => a.anomaly_type === 'HIGH_SPEND').slice(0, 1).forEach(a => {
    recs.push({
      title: `Review large transaction at ${a.vendor}`,
      desc:  `₹${(a.amount || 0).toLocaleString('en-IN')} in ${a.category} on ${a.date} — ${((a.amount / analysis.meta.total_spend) * 100).toFixed(1)}% of total spend in one transaction.`,
      saving: `Negotiate or defer next time`,
    });
  });

  // Standard universal recommendations
  recs.push({
    title: 'Zero-Based Budget Review',
    desc:  'Assign every rupee a job at month-start. Studies show 15-20% reduction in first month.',
    saving: 'Ongoing financial discipline',
  });
  recs.push({
    title: 'Automate Savings First (20% Rule)',
    desc:  "Transfer 20% of income to savings the moment salary arrives. What you can't see, you won't spend.",
    saving: 'Builds long-term wealth',
  });

  return recs.slice(0, 6);
}

// ── Fallback: local-only analysis (when backend is offline) ────────────────
function renderLocalFallback(rows) {
  const total     = rows.reduce((s, e) => s + e.amt, 0);
  const catTotals = {};
  rows.forEach(e => { catTotals[e.cat] = (catTotals[e.cat] || 0) + e.amt; });

  const leaks = [];
  const subs  = rows.filter(e => ['Subscriptions','SaaS','Entertainment'].includes(e.cat));
  const subTotal = subs.reduce((s, e) => s + e.amt, 0);
  if (subs.length >= 2) leaks.push({ name:'Subscription/Entertainment Overload', severity:'HIGH', amount:subTotal, tip:`${subs.length} recurring services totalling ₹${subTotal.toLocaleString('en-IN')}.` });

  const food = rows.filter(e => e.cat === 'Food');
  const foodTotal = food.reduce((s, e) => s + e.amt, 0);
  if (foodTotal > total * 0.18) leaks.push({ name:'Food Delivery Overload', severity:'HIGH', amount:foodTotal, tip:`Food is ${Math.round(foodTotal/total*100)}% of total — above 18% threshold.` });

  const shop = rows.filter(e => e.cat === 'Shopping');
  const shopTotal = shop.reduce((s, e) => s + e.amt, 0);
  if (shopTotal > total * 0.15) leaks.push({ name:'Shopping Excess', severity:'MEDIUM', amount:shopTotal, tip:`Shopping is ${Math.round(shopTotal/total*100)}% of spend. Apply 48-hour rule before purchases.` });

  const score = Math.max(5, Math.min(100, Math.round(100 - (leaks.reduce((s,l)=>s+l.amount,0)/total)*110)));
  const grade = score>=85?'A':score>=70?'B':score>=55?'C':score>=40?'D':'F';
  const gradeColor = grade==='A'?'var(--accent)':grade==='B'?'#64c8ff':grade==='C'?'var(--warn)':'var(--accent2)';
  const circum = 2 * Math.PI * 54;
  const catEntries = Object.entries(catTotals).sort((a,b)=>b[1]-a[1]).slice(0,8);
  const maxCat = catEntries[0]?.[1]||1;
  const BAR_COLORS = ['var(--accent)','var(--accent3)','var(--warn)','var(--accent2)','#64c8ff','#f0a0ff','#80ffaa','#ffaa80'];

  const el  = document.getElementById('results');
  const con = document.getElementById('resultsContainer');
  el.style.display = 'block'; el.classList.add('visible');

  con.innerHTML = `
    <div class="section-tag">// Local Analysis (Backend Offline)</div>
    <h2 class="section-title" style="margin-bottom:32px">Your Financial <em>Health Report</em></h2>
    <div class="score-hero">
      <div class="score-ring-wrap">
        <svg class="score-svg" viewBox="0 0 120 120">
          <circle class="score-ring-bg" cx="60" cy="60" r="54"/>
          <circle class="score-ring-fg" id="scoreRing" cx="60" cy="60" r="54"
            stroke="${gradeColor}" stroke-dasharray="${circum}" stroke-dashoffset="${circum}"/>
          <text x="60" y="56" text-anchor="middle" fill="${gradeColor}" font-family="Syne,sans-serif" font-weight="800" font-size="28">${score}</text>
          <text x="60" y="70" text-anchor="middle" fill="#5a6070" font-family="DM Mono,monospace" font-size="9">/100</text>
        </svg>
      </div>
      <div class="score-info">
        <div class="score-grade" style="color:${gradeColor}">${grade}</div>
        <div class="score-verdict">${score>=70?'Good spending habits':'Leaks detected — action needed'}</div>
        <div class="score-meta">
          <div class="score-meta-item"><div class="label">Total Spend</div><div class="value">₹${total.toLocaleString('en-IN')}</div></div>
          <div class="score-meta-item"><div class="label">Leaks Found</div><div class="value" style="color:var(--accent2)">${leaks.length}</div></div>
        </div>
      </div>
    </div>
    <div class="leaks-grid" style="margin-top:28px">
      ${leaks.map((l, i) => `
        <div class="leak-card leak-${l.severity}" style="animation-delay:${i*0.08}s">
          <div class="leak-severity"><div class="sev-dot"></div>${l.severity}</div>
          <div class="leak-name">${l.name}</div>
          <div class="leak-amount">₹${l.amount.toLocaleString('en-IN')}</div>
          <div class="leak-tip">${l.tip}</div>
        </div>
      `).join('')}
    </div>
    <div class="chart-wrap" style="margin-top:28px">
      <div class="chart-title">Spending Breakdown by Category</div>
      <div class="bar-chart">
        ${catEntries.map(([cat,amt],i) => `
          <div class="bar-row">
            <div class="bar-label">${cat}</div>
            <div class="bar-track"><div class="bar-fill" id="bar-${i}" style="width:0%;background:${BAR_COLORS[i%BAR_COLORS.length]}"></div></div>
            <div class="bar-val" style="color:${BAR_COLORS[i%BAR_COLORS.length]}">₹${amt.toLocaleString('en-IN')}</div>
          </div>
        `).join('')}
      </div>
    </div>
    <p style="color:var(--muted);font-size:12px;margin-top:20px;text-align:center">
      ⚠️ Showing local analysis only — start the FastAPI backend (<code>python run.py</code>) for full Graph + CSP + A* results.
    </p>
  `;

  setTimeout(() => {
    const ringEl = document.getElementById('scoreRing');
    if (ringEl) ringEl.style.strokeDashoffset = circum * (1 - score / 100);
    catEntries.forEach(([,amt],i) => {
      const bar = document.getElementById('bar-'+i);
      if (bar) setTimeout(()=>{ bar.style.width=(amt/maxCat*100)+'%'; }, i*80);
    });
  }, 100);
}

// ── Init: seed 3 demo rows ─────────────────────────────────────────────────
addRow('Lunch order',    '250',   'Food',          '2026-03-01', 'Zomato');
addRow('Electricity',    '2500',  'Utilities',     '2026-03-13', 'Electricity');
addRow('Monthly Rent',   '15000', 'Rent',          '2026-03-04', 'Landlord');
