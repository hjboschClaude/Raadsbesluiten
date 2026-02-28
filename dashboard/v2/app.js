'use strict';

// ── State ──────────────────────────────────────────────────────────────────
let allData      = [];
let filteredData = [];
let currentPage  = 1;
let pageSize     = 25;
let sortCol      = 'datum_ingediend';
let sortDir      = 'desc';
let selectedPartij = '';  // combobox state
let selectedStatus = ''; // segmented control state
let chartYear, chartDonut, chartParty, chartQuarter;
let lastFocusBeforeDrawer = null;

// ── Boot ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initAlert();
  initTabs();
  showTableSkeleton();
  loadData();
});

async function loadData() {
  try {
    const res = await fetch('../data/vragen.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    allData = await res.json();

    hideSkeleton();
    populateBeleidsveldFilter();
    initCombobox();
    bindEvents();
    applyFilters();
    renderPartijTable();

    document.getElementById('headerCount').textContent =
      `${allData.length.toLocaleString('nl-NL')} vragen geladen`;
  } catch (err) {
    hideSkeleton();
    document.getElementById('tableBody').innerHTML =
      `<tr><td colspan="8" style="padding:2rem;text-align:center;color:var(--rood)">
       Fout bij laden: ${esc(err.message)}</td></tr>`;
  }
}

// ── Skeleton ───────────────────────────────────────────────────────────────
function showTableSkeleton() {
  const rows = Array.from({ length: 8 }, () =>
    `<tr class="skeleton-row"><td colspan="8"><div class="skeleton-line"></div></td></tr>`
  ).join('');
  const tb = document.getElementById('tableBody');
  if (tb) tb.innerHTML = rows;
}

function hideSkeleton() {
  ['skYear','skDonut','skParty','skQuarter'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.add('loaded');
  });
}

// ── Alert banner ───────────────────────────────────────────────────────────
function initAlert() {
  const banner = document.getElementById('alertBanner');
  if (!banner) return;
  if (localStorage.getItem('alertDismissed') === '1') {
    banner.hidden = true;
    return;
  }
  document.getElementById('alertClose').addEventListener('click', () => {
    banner.hidden = true;
    localStorage.setItem('alertDismissed', '1');
  });
}

// ── Tabs ───────────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    btn.addEventListener('keydown', e => {
      const tabs = [...document.querySelectorAll('.tab-btn')];
      const idx  = tabs.indexOf(btn);
      if (e.key === 'ArrowRight') { tabs[(idx + 1) % tabs.length].focus(); e.preventDefault(); }
      if (e.key === 'ArrowLeft')  { tabs[(idx - 1 + tabs.length) % tabs.length].focus(); e.preventDefault(); }
    });
  });
  // Restore tab from URL hash
  const hash = location.hash.replace('#', '');
  if (['overzicht','vragen','partijen'].includes(hash)) switchTab(hash);
}

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => {
    const active = b.dataset.tab === tabId;
    b.classList.toggle('tab-btn--active', active);
    b.setAttribute('aria-selected', active);
    b.tabIndex = active ? 0 : -1;
  });
  ['overzicht','vragen','partijen'].forEach(id => {
    const panel = document.getElementById(`panel-${id}`);
    if (panel) panel.hidden = id !== tabId;
  });
  location.hash = tabId;
  // Render charts when overzicht tab becomes visible
  if (tabId === 'overzicht' && allData.length) renderCharts();
}

// ── Combobox (partij) ──────────────────────────────────────────────────────
let partijOptions = [];

function initCombobox() {
  const counts = {};
  allData.forEach(r => {
    const p = primairPartij(r.partij);
    if (p) counts[p] = (counts[p] || 0) + 1;
  });
  partijOptions = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([p, n]) => ({ label: `${p} (${n})`, value: p }));

  const input   = document.getElementById('partijInput');
  const list    = document.getElementById('partijListbox');
  const clearBtn = document.getElementById('partijClear');
  if (!input) return;

  function renderOptions(query) {
    const q = query.toLowerCase();
    const filtered = q
      ? partijOptions.filter(o => o.value.toLowerCase().includes(q))
      : partijOptions;
    list.innerHTML = filtered.slice(0, 60).map((o, i) =>
      `<li role="option" id="combo-opt-${i}" aria-selected="${o.value === selectedPartij}"
           data-value="${esc(o.value)}">${esc(o.label)}</li>`
    ).join('') || '<li style="padding:.5rem .75rem;color:var(--sublabel)">Geen resultaten</li>';
  }

  function openList() {
    renderOptions(input.value);
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  }
  function closeList() {
    list.hidden = true;
    input.setAttribute('aria-expanded', 'false');
  }
  function selectPartij(value, label) {
    selectedPartij = value;
    input.value = value ? label.replace(/ \(\d+\)$/, '') : '';
    clearBtn.hidden = !value;
    closeList();
    currentPage = 1;
    applyFilters();
    renderFilterChips();
  }

  input.addEventListener('input', () => { openList(); });
  input.addEventListener('focus', () => { openList(); });
  input.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeList(); return; }
    if (e.key === 'Enter') {
      const active = list.querySelector('.combobox-active');
      if (active) selectPartij(active.dataset.value, active.textContent);
      return;
    }
    if (e.key === 'ArrowDown') {
      const items = list.querySelectorAll('li[data-value]');
      if (!items.length) return;
      const cur = list.querySelector('.combobox-active');
      const next = cur ? cur.nextElementSibling : items[0];
      if (cur) cur.classList.remove('combobox-active');
      if (next) { next.classList.add('combobox-active'); next.scrollIntoView({ block: 'nearest' }); }
      e.preventDefault();
    }
    if (e.key === 'ArrowUp') {
      const items = list.querySelectorAll('li[data-value]');
      const cur = list.querySelector('.combobox-active');
      if (cur) {
        cur.classList.remove('combobox-active');
        const prev = cur.previousElementSibling;
        if (prev && prev.dataset.value !== undefined) prev.classList.add('combobox-active');
      }
      e.preventDefault();
    }
  });
  list.addEventListener('click', e => {
    const li = e.target.closest('li[data-value]');
    if (li) selectPartij(li.dataset.value, li.textContent);
  });
  document.addEventListener('click', e => {
    if (!document.getElementById('partijComboWrap').contains(e.target)) closeList();
  });
  clearBtn.addEventListener('click', () => selectPartij('', ''));
}

// ── Filters vullen ─────────────────────────────────────────────────────────
function populateBeleidsveldFilter() {
  const counts = {};
  allData.forEach(r => {
    const b = (r.beleidsveld || '').trim();
    if (b) counts[b] = (counts[b] || 0) + 1;
  });
  const sel = document.getElementById('beleidsveldFilter');
  if (!sel) return;
  Object.entries(counts).sort((a, b) => b[1] - a[1]).forEach(([b, n]) => {
    const opt = document.createElement('option');
    opt.value = b; opt.textContent = `${b} (${n})`;
    sel.appendChild(opt);
  });
}

// ── Events ─────────────────────────────────────────────────────────────────
function bindEvents() {
  ['searchInput','jaarFilter','beleidsveldFilter'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => { currentPage = 1; applyFilters(); renderFilterChips(); });
  });

  // Segmented control
  document.querySelectorAll('.seg-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      selectedStatus = btn.dataset.status;
      document.querySelectorAll('.seg-btn').forEach(b => {
        const active = b.dataset.status === selectedStatus;
        b.classList.toggle('seg-btn--active', active);
        b.setAttribute('aria-pressed', active);
      });
      currentPage = 1;
      applyFilters();
      renderFilterChips();
    });
  });

  document.getElementById('resetBtn')?.addEventListener('click', resetFilters);
  document.getElementById('emptyStateReset')?.addEventListener('click', resetFilters);

  // Sort
  document.querySelectorAll('thead th.sortable').forEach(th => {
    th.addEventListener('click', () => sortBy(th.dataset.sort));
    th.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); sortBy(th.dataset.sort); }
    });
  });

  // Page size
  document.getElementById('pageSizeSelect')?.addEventListener('change', e => {
    pageSize = Number(e.target.value);
    currentPage = 1;
    renderTable();
  });

  // Drawer
  document.getElementById('drawerClose')?.addEventListener('click', closeDrawer);
  document.getElementById('drawerOverlay')?.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDrawer();
  });
}

function resetFilters() {
  const s = document.getElementById('searchInput');
  if (s) s.value = '';
  document.getElementById('jaarFilter').value = '';
  document.getElementById('beleidsveldFilter').value = '';
  selectedStatus = '';
  selectedPartij = '';
  const pi = document.getElementById('partijInput');
  if (pi) { pi.value = ''; document.getElementById('partijClear').hidden = true; }
  document.querySelectorAll('.seg-btn').forEach(b => {
    const active = b.dataset.status === '';
    b.classList.toggle('seg-btn--active', active);
    b.setAttribute('aria-pressed', active);
  });
  currentPage = 1;
  applyFilters();
  renderFilterChips();
  showToast(`Filters gewist — alle ${allData.length.toLocaleString('nl-NL')} vragen zichtbaar`);
}

// ── Filter pipeline ────────────────────────────────────────────────────────
function applyFilters() {
  const q    = (document.getElementById('searchInput')?.value || '').trim().toLowerCase();
  const jaar = document.getElementById('jaarFilter')?.value || '';
  const bveld = document.getElementById('beleidsveldFilter')?.value || '';

  filteredData = allData.filter(r => {
    if (q && !r.titel.toLowerCase().includes(q) &&
             !r.id.toLowerCase().includes(q) &&
             !(r.raadslid || '').toLowerCase().includes(q)) return false;
    if (selectedPartij && primairPartij(r.partij) !== selectedPartij) return false;
    if (jaar  && String(r.jaar) !== jaar) return false;
    if (selectedStatus === 'beantwoord' && !r.beantwoord) return false;
    if (selectedStatus === 'open'       &&  r.beantwoord) return false;
    if (bveld && (r.beleidsveld || '').trim() !== bveld) return false;
    return true;
  });

  sortData();
  renderKPIs();
  renderCharts();
  renderTable();
}

// ── Filter chips ───────────────────────────────────────────────────────────
function renderFilterChips() {
  const container = document.getElementById('filterChips');
  if (!container) return;
  const chips = [];

  const q = document.getElementById('searchInput')?.value.trim();
  if (q) chips.push({ label: `Zoek: "${q}"`, clear: () => { document.getElementById('searchInput').value = ''; applyFilters(); renderFilterChips(); } });
  if (selectedPartij) chips.push({ label: selectedPartij, clear: () => { selectedPartij = ''; document.getElementById('partijInput').value = ''; document.getElementById('partijClear').hidden = true; applyFilters(); renderFilterChips(); } });
  const jaar = document.getElementById('jaarFilter')?.value;
  if (jaar) chips.push({ label: jaar, clear: () => { document.getElementById('jaarFilter').value = ''; applyFilters(); renderFilterChips(); } });
  if (selectedStatus) chips.push({ label: selectedStatus === 'beantwoord' ? '✓ Beantwoord' : '⏳ Nog open', clear: () => { selectedStatus = ''; document.querySelectorAll('.seg-btn').forEach(b => { b.classList.toggle('seg-btn--active', b.dataset.status === ''); b.setAttribute('aria-pressed', b.dataset.status === ''); }); applyFilters(); renderFilterChips(); } });
  const bveld = document.getElementById('beleidsveldFilter')?.value;
  if (bveld) chips.push({ label: bveld, clear: () => { document.getElementById('beleidsveldFilter').value = ''; applyFilters(); renderFilterChips(); } });

  if (!chips.length) { container.innerHTML = ''; return; }
  container.innerHTML = chips.map((c, i) =>
    `<span class="filter-chip" role="listitem">
       ${esc(c.label)}
       <button class="chip-remove" data-chip="${i}" aria-label="Verwijder filter: ${esc(c.label)}" type="button">×</button>
     </span>`
  ).join('');
  container.querySelectorAll('.chip-remove').forEach(btn => {
    btn.addEventListener('click', () => chips[Number(btn.dataset.chip)].clear());
  });
}

// ── Sortering ──────────────────────────────────────────────────────────────
function sortBy(col) {
  sortDir = sortCol === col ? (sortDir === 'asc' ? 'desc' : 'asc') : 'desc';
  sortCol = col;
  currentPage = 1;
  sortData();
  updateSortIndicators();
  renderTable();
}
function sortData() {
  filteredData.sort((a, b) => {
    let va = a[sortCol] ?? '', vb = b[sortCol] ?? '';
    if (sortCol === 'doorlooptijd_dagen') {
      va = va === '' ? (sortDir === 'asc' ? Infinity : -Infinity) : Number(va);
      vb = vb === '' ? (sortDir === 'asc' ? Infinity : -Infinity) : Number(vb);
      return sortDir === 'asc' ? va - vb : vb - va;
    }
    const c = String(va).localeCompare(String(vb), 'nl', { sensitivity: 'base' });
    return sortDir === 'asc' ? c : -c;
  });
}
function updateSortIndicators() {
  document.querySelectorAll('thead th.sortable').forEach(th => {
    th.classList.remove('sort-asc','sort-desc');
    th.removeAttribute('aria-sort');
    if (th.dataset.sort === sortCol) {
      th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      th.setAttribute('aria-sort', sortDir === 'asc' ? 'ascending' : 'descending');
    }
  });
}

// ── KPI's ──────────────────────────────────────────────────────────────────
function renderKPIs() {
  const total = filteredData.length;
  const beant = filteredData.filter(r => r.beantwoord).length;
  const open  = total - beant;
  const pct   = total ? Math.round(beant / total * 100) : 0;
  const partijT = {};
  filteredData.forEach(r => { const p = primairPartij(r.partij); if (p) partijT[p] = (partijT[p]||0)+1; });
  const topP = Object.entries(partijT).sort((a,b) => b[1]-a[1])[0];
  const dlVals = filteredData.filter(r => r.beantwoord && r.doorlooptijd_dagen != null).map(r => r.doorlooptijd_dagen);
  const gemDl  = dlVals.length ? Math.round(dlVals.reduce((s,v) => s+v, 0) / dlVals.length) : null;

  document.getElementById('kpiTotaal').textContent        = total.toLocaleString('nl-NL');
  document.getElementById('kpiPctBeantwoord').textContent  = `${pct}%`;
  document.getElementById('kpiOpen').textContent           = open.toLocaleString('nl-NL');
  document.getElementById('kpiPartij').textContent         = topP ? topP[0] : '—';
  document.getElementById('kpiDoorlooptijd').textContent   = gemDl != null ? `${gemDl} d` : '—';
  document.getElementById('headerCount').textContent =
    `${filteredData.length.toLocaleString('nl-NL')} / ${allData.length.toLocaleString('nl-NL')} vragen`;
}

// ── Grafieken ──────────────────────────────────────────────────────────────
const GROEN = '#00811F', ROZE = '#C93675', GROEN_LICHT = 'rgba(0,129,31,.2)';

function renderCharts() {
  renderChartYear(); renderChartDonut(); renderChartParty(); renderChartQuarter();
}
function renderChartYear() {
  const jaren = ['2022','2023','2024','2025','2026'];
  const ctx = document.getElementById('chartYear')?.getContext('2d');
  if (!ctx) return;
  if (chartYear) chartYear.destroy();
  chartYear = new Chart(ctx, {
    type: 'bar',
    data: { labels: jaren, datasets: [
      { label: 'Beantwoord', data: jaren.map(j => filteredData.filter(r => String(r.jaar)===j && r.beantwoord).length), backgroundColor: GROEN, stack: 'a' },
      { label: 'Nog open',   data: jaren.map(j => filteredData.filter(r => String(r.jaar)===j && !r.beantwoord).length), backgroundColor: ROZE, stack: 'a' },
    ]},
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } },
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } },
  });
}
function renderChartDonut() {
  const beant = filteredData.filter(r => r.beantwoord).length;
  const ctx = document.getElementById('chartDonut')?.getContext('2d');
  if (!ctx) return;
  if (chartDonut) chartDonut.destroy();
  chartDonut = new Chart(ctx, {
    type: 'doughnut',
    data: { labels: ['Beantwoord','Nog open'], datasets: [{ data: [beant, filteredData.length - beant], backgroundColor: [GROEN, ROZE], borderWidth: 2, borderColor: '#fff' }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '60%',
      plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => { const t = c.dataset.data.reduce((a,b)=>a+b,0); return ` ${c.label}: ${c.raw} (${t?Math.round(c.raw/t*100):0}%)`; } } } } },
  });
}
function renderChartParty() {
  const counts = {};
  filteredData.forEach(r => { const p = primairPartij(r.partij); if (p) counts[p] = (counts[p]||0)+1; });
  const top10 = Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,10).reverse();
  const ctx = document.getElementById('chartParty')?.getContext('2d');
  if (!ctx) return;
  if (chartParty) chartParty.destroy();
  chartParty = new Chart(ctx, {
    type: 'bar',
    data: { labels: top10.map(([p])=>p), datasets: [{ label: 'Vragen', data: top10.map(([,n])=>n), backgroundColor: GROEN }] },
    options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } }, y: { grid: { display: false } } } },
  });
}
function renderChartQuarter() {
  const kw = []; for (let y=2022;y<=2026;y++) for (let q=1;q<=4;q++) kw.push(`${y}-Q${q}`);
  const counts = {};
  filteredData.forEach(r => { if (r.kwartaal) counts[r.kwartaal]=(counts[r.kwartaal]||0)+1; });
  const ctx = document.getElementById('chartQuarter')?.getContext('2d');
  if (!ctx) return;
  if (chartQuarter) chartQuarter.destroy();
  chartQuarter = new Chart(ctx, {
    type: 'line',
    data: { labels: kw, datasets: [{ label: 'Vragen', data: kw.map(k=>counts[k]||0), borderColor: GROEN, backgroundColor: GROEN_LICHT, fill: true, tension: 0.3, pointRadius: 3 }] },
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { maxRotation: 45, font: { size: 11 } } }, y: { beginAtZero: true, ticks: { precision: 0 } } } },
  });
}

// ── Tabel ──────────────────────────────────────────────────────────────────
function renderTable() {
  const total  = filteredData.length;
  const start  = (currentPage - 1) * pageSize;
  const page   = filteredData.slice(start, start + pageSize);
  const empty  = document.getElementById('emptyState');
  const wrap   = document.getElementById('tableWrap');

  document.getElementById('tableCount').textContent = total.toLocaleString('nl-NL');

  if (total === 0) {
    if (empty)  empty.hidden = false;
    if (wrap)   wrap.hidden  = true;
    document.getElementById('pagination').innerHTML = '';
    document.getElementById('paginationInfo').textContent = '';
    return;
  }
  if (empty)  empty.hidden = true;
  if (wrap)   wrap.hidden  = false;

  document.getElementById('tableBody').innerHTML = page.map(renderRow).join('');

  document.querySelectorAll('tbody tr[data-id]').forEach(tr => {
    const record = filteredData.find(r => r.id === tr.dataset.id);
    tr.setAttribute('tabindex', '0');
    const open = e => { if (!e.target.closest('a')) { lastFocusBeforeDrawer = tr; openDrawer(record); } };
    tr.addEventListener('click', open);
    tr.addEventListener('keydown', e => { if (e.key === 'Enter') open(e); });
  });

  updateSortIndicators();
  renderPagination(total);
}

function renderRow(r) {
  const url = r.portaal_url || '';
  const bbLink = url
    ? `<a href="${esc(url)}" target="_blank" rel="noopener" aria-label="Open vraag ${esc(r.id)}">${esc(r.id)}</a>`
    : esc(r.id);
  const titelLink = url
    ? `<a class="titel-link" href="${esc(url)}" target="_blank" rel="noopener" title="${esc(r.titel)}">${esc(truncate(r.titel, 100))}</a>`
    : esc(truncate(r.titel, 100));

  const d = r.doorlooptijd_dagen;
  let dlCls = 'dl--lopend', barCls = 'dl-bar-fill--lopend', dlTxt = `${d} d (lopend)`;
  if (r.beantwoord && d != null) {
    dlCls  = d <= 42 ? 'dl--snel'  : d <= 84 ? 'dl--matig'  : 'dl--lang';
    barCls = d <= 42 ? 'dl-bar-fill--snel' : d <= 84 ? 'dl-bar-fill--matig' : 'dl-bar-fill--lang';
    dlTxt  = `${d} d`;
  }
  const barWidth = d != null ? Math.min(100, Math.round(d / 180 * 100)) : 0;
  const dlHtml = d != null ? `<div class="dl-cell">
    <span class="dl ${dlCls}" aria-label="${dlTxt}">${dlTxt}</span>
    <div class="dl-bar" role="progressbar" aria-valuenow="${d}" aria-valuemax="180" aria-label="${dlTxt}">
      <div class="dl-bar-fill ${barCls}" style="width:${barWidth}%"></div>
    </div>
  </div>` : '<span style="color:var(--sublabel)">—</span>';

  let badge;
  if (!r.beantwoord && d != null && d > 84) {
    badge = `<span class="badge badge--open-lang" aria-label="Nog open, ${d} dagen lopend">⚠ Nog open — ${d} d</span>`;
  } else if (r.beantwoord) {
    badge = `<span class="badge badge--beantwoord" aria-label="Beantwoord">✓ Beantwoord</span>`;
  } else {
    badge = `<span class="badge badge--open" aria-label="Nog open">⏳ Nog open</span>`;
  }

  const datumBeant = r.datum_beantwoord
    ? formatDatum(r.datum_beantwoord)
    : r.verwachte_datum_afdoening
      ? `${formatDatum(r.verwachte_datum_afdoening)} <small style="color:var(--sublabel)">(verwacht)</small>`
      : '—';

  return `<tr data-id="${esc(r.id)}" aria-label="Vraag ${esc(r.id)}">
    <td class="td-bb">${bbLink}</td>
    <td class="col-titel">${titelLink}</td>
    <td>${esc(primairPartij(r.partij))}</td>
    <td class="td-datum">${formatDatum(r.datum_ingediend)}</td>
    <td class="td-datum">${datumBeant}</td>
    <td>${dlHtml}</td>
    <td>${badge}</td>
    <td>${esc(r.beleidsveld)}</td>
  </tr>`;
}

// ── Paginering ─────────────────────────────────────────────────────────────
function renderPagination(total) {
  const pages = Math.ceil(total / pageSize);
  const start = (currentPage - 1) * pageSize + 1;
  const end   = Math.min(currentPage * pageSize, total);
  document.getElementById('paginationInfo').textContent =
    `${start}–${end} van ${total.toLocaleString('nl-NL')}`;

  if (pages <= 1) { document.getElementById('pagination').innerHTML = ''; return; }
  const shown = pagesRange(currentPage, pages);
  let html = `<button ${currentPage===1?'disabled':''} onclick="goToPage(${currentPage-1})" aria-label="Vorige pagina">‹</button>`;
  let prev = null;
  shown.forEach(p => {
    if (prev !== null && p - prev > 1) html += `<button disabled>…</button>`;
    html += `<button class="${p===currentPage?'active':''}" aria-label="Pagina ${p}" aria-current="${p===currentPage?'page':''}" onclick="goToPage(${p})">${p}</button>`;
    prev = p;
  });
  html += `<button ${currentPage===pages?'disabled':''} onclick="goToPage(${currentPage+1})" aria-label="Volgende pagina">›</button>`;
  document.getElementById('pagination').innerHTML = html;
}
function pagesRange(cur, total) {
  const s = new Set([1, total]);
  for (let i=Math.max(1,cur-2); i<=Math.min(total,cur+2); i++) s.add(i);
  return [...s].sort((a,b)=>a-b);
}
function goToPage(p) {
  currentPage = p;
  renderTable();
  document.querySelector('.table-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Per-partij tabel ───────────────────────────────────────────────────────
function renderPartijTable() {
  const stats = {};
  allData.forEach(r => {
    const p = primairPartij(r.partij) || '(onbekend)';
    if (!stats[p]) stats[p] = { totaal: 0, beant: 0, dlVals: [] };
    stats[p].totaal++;
    if (r.beantwoord) { stats[p].beant++; if (r.doorlooptijd_dagen != null) stats[p].dlVals.push(r.doorlooptijd_dagen); }
  });
  const rows = Object.entries(stats).sort((a,b) => b[1].totaal - a[1].totaal);
  const tb = document.getElementById('partijTableBody');
  if (!tb) return;
  tb.innerHTML = rows.map(([p, s]) => {
    const open = s.totaal - s.beant;
    const pct  = Math.round(s.beant / s.totaal * 100);
    const gemDl = s.dlVals.length ? Math.round(s.dlVals.reduce((a,b)=>a+b,0)/s.dlVals.length) : null;
    return `<tr>
      <td><strong>${esc(p)}</strong></td>
      <td>${s.totaal}</td>
      <td>${s.beant}</td>
      <td>${open}</td>
      <td>${pct}%</td>
      <td>${gemDl != null ? `${gemDl} d` : '—'}</td>
      <td>
        <div class="part-bar-wrap" role="progressbar" aria-valuenow="${pct}" aria-valuemax="100" aria-label="${pct}% beantwoord">
          <div class="part-bar-fill" style="width:${pct}%"></div>
        </div>
      </td>
    </tr>`;
  }).join('');
}

// ── Drawer ─────────────────────────────────────────────────────────────────
function openDrawer(r) {
  if (!r) return;
  const d = r.doorlooptijd_dagen;
  let dlCls = 'dl--lopend', dlTxt = d != null ? `${d} d (lopend)` : '—';
  if (r.beantwoord && d != null) {
    dlCls = d <= 42 ? 'dl--snel' : d <= 84 ? 'dl--matig' : 'dl--lang';
    dlTxt = `${d} dagen`;
  }

  document.getElementById('drawerTitle').textContent = r.id;
  document.getElementById('drawerBody').innerHTML = `
    <dl>
      <div class="drawer-field">
        <dt>Titel</dt>
        <dd>${esc(r.titel)}</dd>
      </div>
      <div class="drawer-field">
        <dt>Partij / Raadslid</dt>
        <dd>${esc(r.partij || '—')} ${r.raadslid ? `— ${esc(r.raadslid)}` : ''}</dd>
      </div>
      <div class="drawer-field">
        <dt>Datum ingediend</dt>
        <dd>${formatDatum(r.datum_ingediend)}</dd>
      </div>
      <div class="drawer-field">
        <dt>Datum beantwoord</dt>
        <dd>${r.datum_beantwoord ? formatDatum(r.datum_beantwoord) : r.verwachte_datum_afdoening ? `Verwacht: ${formatDatum(r.verwachte_datum_afdoening)}` : 'Nog niet beantwoord'}</dd>
      </div>
      <div class="drawer-field">
        <dt>Doorlooptijd</dt>
        <dd><span class="dl ${dlCls} drawer-dl-big">${dlTxt}</span></dd>
      </div>
      <div class="drawer-field">
        <dt>Status</dt>
        <dd>${r.beantwoord ? '✓ Beantwoord' : '⏳ Nog open'}</dd>
      </div>
      <div class="drawer-field">
        <dt>Beleidsveld</dt>
        <dd>${esc(r.beleidsveld || '—')}</dd>
      </div>
      ${r.stand_van_zaken ? `<div class="drawer-field"><dt>Stand van zaken</dt><dd>${esc(r.stand_van_zaken)}</dd></div>` : ''}
    </dl>
    <p style="font-size:.8rem;color:var(--sublabel);margin:.75rem 0 .5rem">
      Tussenberichten en antwoorden staan op de portaalpagina:
    </p>
    ${r.portaal_url ? `<a class="drawer-portaal" href="${esc(r.portaal_url)}" target="_blank" rel="noopener">Open portaalpagina →</a>` : ''}
  `;

  const drawer  = document.getElementById('detailDrawer');
  const overlay = document.getElementById('drawerOverlay');
  drawer.hidden  = false;
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
  overlay.classList.add('open');
  overlay.setAttribute('aria-hidden', 'false');
  document.getElementById('drawerClose').focus();
  document.body.style.overflow = 'hidden';
}

function closeDrawer() {
  const drawer  = document.getElementById('detailDrawer');
  const overlay = document.getElementById('drawerOverlay');
  drawer.classList.remove('open');
  overlay.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
  overlay.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
  setTimeout(() => { drawer.hidden = true; }, 260);
  if (lastFocusBeforeDrawer) { lastFocusBeforeDrawer.focus(); lastFocusBeforeDrawer = null; }
}

// ── Toast ──────────────────────────────────────────────────────────────────
function showToast(msg, duration = 4000) {
  const c = document.getElementById('toastContainer');
  if (!c) return;
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  el.setAttribute('role', 'status');
  c.appendChild(el);
  requestAnimationFrame(() => { requestAnimationFrame(() => el.classList.add('show')); });
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 250);
  }, duration);
}

// ── Hulpfuncties ───────────────────────────────────────────────────────────
function primairPartij(p) { return p ? p.split('\n')[0].trim() : ''; }
function formatDatum(d) {
  if (!d) return '—';
  const [y, m, dag] = d.split('-');
  return `${dag}-${m}-${y}`;
}
function esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function truncate(s, max) { return s && s.length > max ? s.slice(0, max) + '…' : (s || ''); }
