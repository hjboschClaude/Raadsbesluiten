/**
 * Dashboard Schriftelijke Vragen — Gemeenteraad Rotterdam
 *
 * Functionaliteiten:
 *  - Laden van JSON data (data/vragen.json)
 *  - Real-time filters: zoeken, partij, jaar, status, beleidsveld
 *  - KPI-kaarten: totaal, % beantwoord, nog open, meest actieve partij, gem. doorlooptijd
 *  - Grafieken (Chart.js): per jaar, open/beantwoord, top-10 partijen, per kwartaal
 *  - Sorteerbare datatable met paginering (25 rijen/pagina)
 *  - Aanklikbare rijen en BB-nummers → portaalpagina (bevat tussenberichten + antwoorden)
 *  - Doorlooptijd per vraag: berekend en kleur-gecodeerd
 */

'use strict';

// ─── State ───────────────────────────────────────────────────────────────────
let allData      = [];
let filteredData = [];
let currentPage  = 1;
const PAGE_SIZE  = 25;

let sortCol = 'datum_ingediend';
let sortDir = 'desc';

let chartYear, chartDonut, chartParty, chartQuarter;

// ─── Boot ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadData();
});

async function loadData() {
  try {
    const res = await fetch('data/vragen.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    allData = await res.json();

    populatePartijFilter();
    populateBeleidsveldFilter();
    bindEvents();
    applyFilters();

    document.getElementById('headerCount').textContent =
      `${allData.length.toLocaleString('nl-NL')} vragen geladen`;
  } catch (err) {
    document.getElementById('tableBody').innerHTML =
      `<tr class="loading-row"><td colspan="8">Fout bij laden: ${err.message}</td></tr>`;
    console.error(err);
  }
}

// ─── Filters vullen ───────────────────────────────────────────────────────────
function populatePartijFilter() {
  // Gebruik eerste partij (voor meerdere-partij vragen)
  const counts = {};
  allData.forEach(r => {
    const p = primairPartij(r.partij);
    if (p) counts[p] = (counts[p] || 0) + 1;
  });

  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const sel = document.getElementById('partijFilter');
  sorted.forEach(([p, n]) => {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = `${p} (${n})`;
    sel.appendChild(opt);
  });
}

function populateBeleidsveldFilter() {
  const counts = {};
  allData.forEach(r => {
    const b = (r.beleidsveld || '').trim();
    if (b) counts[b] = (counts[b] || 0) + 1;
  });

  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const sel = document.getElementById('beleidsveldFilter');
  sorted.forEach(([b, n]) => {
    const opt = document.createElement('option');
    opt.value = b;
    opt.textContent = `${b} (${n})`;
    sel.appendChild(opt);
  });
}

// ─── Event handlers ───────────────────────────────────────────────────────────
function bindEvents() {
  ['searchInput', 'partijFilter', 'jaarFilter', 'statusFilter', 'beleidsveldFilter']
    .forEach(id => {
      document.getElementById(id).addEventListener('input', () => {
        currentPage = 1;
        applyFilters();
      });
    });

  document.getElementById('resetBtn').addEventListener('click', resetFilters);

  // Kolom-sortering
  document.querySelectorAll('thead th.sortable').forEach(th => {
    th.addEventListener('click', () => sortBy(th.dataset.sort));
    th.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        sortBy(th.dataset.sort);
      }
    });
  });
}

function resetFilters() {
  document.getElementById('searchInput').value     = '';
  document.getElementById('partijFilter').value    = '';
  document.getElementById('jaarFilter').value      = '';
  document.getElementById('statusFilter').value    = '';
  document.getElementById('beleidsveldFilter').value = '';
  currentPage = 1;
  applyFilters();
}

// ─── Filter & render pipeline ──────────────────────────────────────────────────
function applyFilters() {
  const q      = document.getElementById('searchInput').value.trim().toLowerCase();
  const partij = document.getElementById('partijFilter').value;
  const jaar   = document.getElementById('jaarFilter').value;
  const status = document.getElementById('statusFilter').value;
  const bveld  = document.getElementById('beleidsveldFilter').value;

  filteredData = allData.filter(r => {
    if (q && !r.titel.toLowerCase().includes(q) &&
             !r.id.toLowerCase().includes(q) &&
             !r.raadslid.toLowerCase().includes(q)) return false;
    if (partij && primairPartij(r.partij) !== partij) return false;
    if (jaar   && String(r.jaar) !== jaar) return false;
    if (status === 'beantwoord' && !r.beantwoord) return false;
    if (status === 'open'       &&  r.beantwoord) return false;
    if (bveld  && (r.beleidsveld || '').trim() !== bveld) return false;
    return true;
  });

  sortData();
  renderKPIs();
  renderCharts();
  renderTable();
}

// ─── Sortering ────────────────────────────────────────────────────────────────
function sortBy(col) {
  if (sortCol === col) {
    sortDir = sortDir === 'asc' ? 'desc' : 'asc';
  } else {
    sortCol = col;
    sortDir = 'desc';
  }
  currentPage = 1;
  sortData();
  updateSortIndicators();
  renderTable();
}

function sortData() {
  filteredData.sort((a, b) => {
    let va = a[sortCol] ?? '';
    let vb = b[sortCol] ?? '';
    // Numeriek voor doorlooptijd
    if (sortCol === 'doorlooptijd_dagen') {
      va = va === '' ? (sortDir === 'asc' ? Infinity : -Infinity) : Number(va);
      vb = vb === '' ? (sortDir === 'asc' ? Infinity : -Infinity) : Number(vb);
      return sortDir === 'asc' ? va - vb : vb - va;
    }
    // String vergelijking
    const cmp = String(va).localeCompare(String(vb), 'nl', { sensitivity: 'base' });
    return sortDir === 'asc' ? cmp : -cmp;
  });
}

function updateSortIndicators() {
  document.querySelectorAll('thead th.sortable').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    th.removeAttribute('aria-sort');
    if (th.dataset.sort === sortCol) {
      th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      th.setAttribute('aria-sort', sortDir === 'asc' ? 'ascending' : 'descending');
    }
  });
}

// ─── KPI Kaarten ──────────────────────────────────────────────────────────────
function renderKPIs() {
  const total      = filteredData.length;
  const beantwoord = filteredData.filter(r => r.beantwoord).length;
  const open       = total - beantwoord;
  const pct        = total ? Math.round(beantwoord / total * 100) : 0;

  // Meest actieve partij
  const partijTeller = {};
  filteredData.forEach(r => {
    const p = primairPartij(r.partij);
    if (p) partijTeller[p] = (partijTeller[p] || 0) + 1;
  });
  const topPartij = Object.entries(partijTeller).sort((a,b) => b[1]-a[1])[0];

  // Gemiddelde doorlooptijd (alleen beantwoorde)
  const dlWaarden = filteredData
    .filter(r => r.beantwoord && r.doorlooptijd_dagen != null)
    .map(r => r.doorlooptijd_dagen);
  const gemDl = dlWaarden.length
    ? Math.round(dlWaarden.reduce((s, v) => s + v, 0) / dlWaarden.length)
    : null;

  document.getElementById('kpiTotaal').textContent        = total.toLocaleString('nl-NL');
  document.getElementById('kpiPctBeantwoord').textContent  = `${pct}%`;
  document.getElementById('kpiOpen').textContent           = open.toLocaleString('nl-NL');
  document.getElementById('kpiPartij').textContent         = topPartij ? topPartij[0] : '—';
  document.getElementById('kpiDoorlooptijd').textContent   = gemDl != null ? `${gemDl} d` : '—';
  document.getElementById('headerCount').textContent =
    `${filteredData.length.toLocaleString('nl-NL')} van ${allData.length.toLocaleString('nl-NL')} vragen`;
}

// ─── Grafieken ─────────────────────────────────────────────────────────────────
const GROEN = '#00811F';
const ROZE  = '#C93675';
const GROEN_LICHT = 'rgba(0,129,31,.25)';

function renderCharts() {
  renderChartYear();
  renderChartDonut();
  renderChartParty();
  renderChartQuarter();
}

/* Grafiek A: Vragen per jaar (gestapeld: beantwoord + open) */
function renderChartYear() {
  const jaren = ['2022','2023','2024','2025','2026'];
  const dataBeantwoord = jaren.map(j =>
    filteredData.filter(r => String(r.jaar) === j && r.beantwoord).length);
  const dataOpen = jaren.map(j =>
    filteredData.filter(r => String(r.jaar) === j && !r.beantwoord).length);

  const ctx = document.getElementById('chartYear').getContext('2d');
  if (chartYear) chartYear.destroy();
  chartYear = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: jaren,
      datasets: [
        { label: 'Beantwoord', data: dataBeantwoord, backgroundColor: GROEN, stack: 'a' },
        { label: 'Nog open',   data: dataOpen,       backgroundColor: ROZE,  stack: 'a' },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } },
      scales: {
        x: { stacked: true, grid: { display: false } },
        y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
      },
    },
  });
}

/* Grafiek B: Donut open vs beantwoord */
function renderChartDonut() {
  const beantwoord = filteredData.filter(r => r.beantwoord).length;
  const open       = filteredData.length - beantwoord;

  const ctx = document.getElementById('chartDonut').getContext('2d');
  if (chartDonut) chartDonut.destroy();
  chartDonut = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Beantwoord', 'Nog open'],
      datasets: [{
        data: [beantwoord, open],
        backgroundColor: [GROEN, ROZE],
        borderWidth: 2,
        borderColor: '#fff',
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom' },
        tooltip: {
          callbacks: {
            label: ctx => {
              const tot = ctx.dataset.data.reduce((a,b) => a+b, 0);
              const pct = tot ? Math.round(ctx.raw / tot * 100) : 0;
              return ` ${ctx.label}: ${ctx.raw} (${pct}%)`;
            },
          },
        },
      },
      cutout: '60%',
    },
  });
}

/* Grafiek C: Top 10 partijen (horizontale balk) */
function renderChartParty() {
  const counts = {};
  filteredData.forEach(r => {
    const p = primairPartij(r.partij);
    if (p) counts[p] = (counts[p] || 0) + 1;
  });
  const top10 = Object.entries(counts).sort((a,b) => b[1]-a[1]).slice(0, 10).reverse();

  const ctx = document.getElementById('chartParty').getContext('2d');
  if (chartParty) chartParty.destroy();
  chartParty = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: top10.map(([p]) => p),
      datasets: [{
        label: 'Vragen',
        data: top10.map(([,n]) => n),
        backgroundColor: GROEN,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { precision: 0 } },
        y: { grid: { display: false } },
      },
    },
  });
}

/* Grafiek D: Lijndiagram per kwartaal */
function renderChartQuarter() {
  // Genereer alle kwartalen 2022-Q1 → 2026-Q4
  const alleKwartalen = [];
  for (let y = 2022; y <= 2026; y++) {
    for (let q = 1; q <= 4; q++) alleKwartalen.push(`${y}-Q${q}`);
  }

  const counts = {};
  filteredData.forEach(r => { if (r.kwartaal) counts[r.kwartaal] = (counts[r.kwartaal] || 0) + 1; });
  const data = alleKwartalen.map(k => counts[k] || 0);

  const ctx = document.getElementById('chartQuarter').getContext('2d');
  if (chartQuarter) chartQuarter.destroy();
  chartQuarter = new Chart(ctx, {
    type: 'line',
    data: {
      labels: alleKwartalen,
      datasets: [{
        label: 'Vragen ingediend',
        data,
        borderColor: GROEN,
        backgroundColor: GROEN_LICHT,
        fill: true,
        tension: 0.3,
        pointRadius: 3,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { maxRotation: 45, font: { size: 11 } } },
        y: { beginAtZero: true, ticks: { precision: 0 } },
      },
    },
  });
}

// ─── Datatable ─────────────────────────────────────────────────────────────────
function renderTable() {
  const start = (currentPage - 1) * PAGE_SIZE;
  const page  = filteredData.slice(start, start + PAGE_SIZE);

  document.getElementById('tableCount').textContent =
    filteredData.length.toLocaleString('nl-NL');

  const tbody = document.getElementById('tableBody');
  if (filteredData.length === 0) {
    tbody.innerHTML = '<tr class="loading-row"><td colspan="8">Geen vragen gevonden met deze filters.</td></tr>';
    document.getElementById('pagination').innerHTML = '';
    return;
  }

  tbody.innerHTML = page.map(renderRow).join('');

  // Klikbare rijen
  tbody.querySelectorAll('tr[data-url]').forEach(tr => {
    tr.addEventListener('click', e => {
      // Niet triggeren als gebruiker op een <a> klikt
      if (e.target.closest('a')) return;
      const url = tr.dataset.url;
      if (url) window.open(url, '_blank', 'noopener');
    });
    tr.setAttribute('tabindex', '0');
    tr.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.target.closest('a')) {
        window.open(tr.dataset.url, '_blank', 'noopener');
      }
    });
  });

  renderPagination();
  updateSortIndicators();
}

function renderRow(r) {
  const portaalUrl = r.portaal_url || '';
  const bbLink = portaalUrl
    ? `<a href="${esc(portaalUrl)}" target="_blank" rel="noopener"
          aria-label="Open vraag ${esc(r.id)} op portaal">${esc(r.id)}</a>`
    : esc(r.id);

  const titelContent = portaalUrl
    ? `<a class="titel-link" href="${esc(portaalUrl)}" target="_blank" rel="noopener"
          title="${esc(r.titel)}">${esc(truncate(r.titel, 120))}</a>`
    : esc(truncate(r.titel, 120));

  const badge = r.beantwoord
    ? '<span class="badge badge--beantwoord">Beantwoord</span>'
    : '<span class="badge badge--open">Nog open</span>';

  const dlHtml = formatDoorlooptijdHtml(r);

  const datumBeantwoord = r.datum_beantwoord
    ? `<span class="td-datum">${formatDatum(r.datum_beantwoord)}</span>`
    : r.verwachte_datum_afdoening
      ? `<span class="td-datum" title="Verwacht">${formatDatum(r.verwachte_datum_afdoening)} <small>(verwacht)</small></span>`
      : '<span style="color:var(--sublabel)">—</span>';

  return `<tr data-url="${esc(portaalUrl)}" aria-label="Schriftelijke vraag ${esc(r.id)}">
    <td class="td-bb">${bbLink}</td>
    <td class="td-titel">${titelContent}</td>
    <td>${esc(primairPartij(r.partij))}</td>
    <td class="td-datum">${formatDatum(r.datum_ingediend)}</td>
    <td>${datumBeantwoord}</td>
    <td>${dlHtml}</td>
    <td>${badge}</td>
    <td>${esc(r.beleidsveld)}</td>
  </tr>`;
}

// ─── Paginering ────────────────────────────────────────────────────────────────
function renderPagination() {
  const total = Math.ceil(filteredData.length / PAGE_SIZE);
  if (total <= 1) { document.getElementById('pagination').innerHTML = ''; return; }

  let html = '';

  html += `<button ${currentPage === 1 ? 'disabled' : ''}
    aria-label="Vorige pagina" onclick="goToPage(${currentPage - 1})">‹</button>`;

  const pages = pagesToShow(currentPage, total);
  let prev = null;
  pages.forEach(p => {
    if (prev !== null && p - prev > 1) html += '<button disabled>…</button>';
    html += `<button class="${p === currentPage ? 'active' : ''}"
      aria-label="Pagina ${p}" aria-current="${p === currentPage ? 'page' : ''}"
      onclick="goToPage(${p})">${p}</button>`;
    prev = p;
  });

  html += `<button ${currentPage === total ? 'disabled' : ''}
    aria-label="Volgende pagina" onclick="goToPage(${currentPage + 1})">›</button>`;

  document.getElementById('pagination').innerHTML = html;
}

function pagesToShow(current, total) {
  const delta = 2;
  const pages = new Set();
  pages.add(1);
  pages.add(total);
  for (let i = Math.max(1, current - delta); i <= Math.min(total, current + delta); i++) {
    pages.add(i);
  }
  return [...pages].sort((a,b) => a-b);
}

function goToPage(p) {
  currentPage = p;
  renderTable();
  document.querySelector('.table-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ─── Hulpfuncties ──────────────────────────────────────────────────────────────

/** Geef eerste partij als de waarde meerdere partijen bevat (gescheiden door \n). */
function primairPartij(partij) {
  if (!partij) return '';
  return partij.split('\n')[0].trim();
}

/** Formatteer datum YYYY-MM-DD → DD-MM-YYYY. */
function formatDatum(d) {
  if (!d) return '—';
  const [y, m, dag] = d.split('-');
  return `${dag}-${m}-${y}`;
}

/** Doorlooptijd HTML met kleurcodering. */
function formatDoorlooptijdHtml(r) {
  if (r.doorlooptijd_dagen == null) return '<span style="color:var(--sublabel)">—</span>';

  const d = r.doorlooptijd_dagen;

  if (!r.beantwoord) {
    // Lopende vraag: doorlooptijd tot vandaag
    return `<span class="dl dl--lopend" title="Vraag is nog niet beantwoord">
      ${d} d <small class="dl--hint">(lopend)</small>
    </span>`;
  }

  // Beantwoorde vraag: kleurcodering
  let cls = 'dl--snel';      // < 6 weken (42 d)
  let label = '≤ 6 w';
  if (d > 84) {
    cls = 'dl--lang';        // > 12 weken
    label = '> 12 w';
  } else if (d > 42) {
    cls = 'dl--matig';       // 6–12 weken
    label = '6–12 w';
  }

  return `<span class="dl ${cls}" title="${d} kalenderdagen — ${label}">
    ${d} d
  </span>`;
}

/** Escape HTML special chars. */
function esc(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Tekst inkorten. */
function truncate(s, max) {
  if (!s) return '';
  return s.length > max ? s.slice(0, max) + '…' : s;
}
