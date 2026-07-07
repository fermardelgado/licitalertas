// ── CONFIG ──────────────────────────────────────────────
const SUPABASE_URL = "https://hjbmcdxbiajmbczgyhxk.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhqYm1jZHhiaWFqbWJjemd5aHhrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI5MzA0MTksImV4cCI6MjA5ODUwNjQxOX0.8xWlQbDrYCTMvqZLXz9aIwCACrMcAsrVWYUo8_gegmI";
const POR_PAGINA = 50;

// ── SESION ───────────────────────────────────────────────
const { createClient } = supabase;
const sb = createClient(SUPABASE_URL, SUPABASE_KEY);

async function verificarSesion() {
  const { data } = await sb.auth.getSession();
  if (!data.session) { window.location.href = "login.html"; return null; }
  return data.session;
}

async function salir() {
  await sb.auth.signOut();
  window.location.href = "login.html";
}

// ── ESTADO ──────────────────────────────────────────────
let todas     = [];
let filtradas = [];
let pagina    = 1;
let vista     = "tabla";
let charts    = {};
let vistaEstado = "abiertas";

// ── UTILS ───────────────────────────────────────────────
const hoy = () => { const d = new Date(); d.setHours(0,0,0,0); return d; };

function diasRestantes(f) {
  if (!f) return 999;
  return Math.round((new Date(f) - hoy()) / 86400000);
}

function urgencia(dias) {
  if (dias < 0)   return "vencido";
  if (dias <= 3)  return "urgente";
  if (dias <= 10) return "proximo";
  return "normal";
}

function fmtFecha(f) {
  if (!f) return "—";
  const [y, m, d] = f.slice(0,10).split("-");
  return `${d}/${m}/${y}`;
}

function fmtMonto(n) {
  if (!n || n === 0) return "—";
  return "S/ " + Number(n).toLocaleString("es-PE", { minimumFractionDigits: 0 });
}

function fmtMontoCorto(n) {
  if (!n) return "—";
  if (n >= 1e9)  return "S/ " + (n/1e9).toFixed(1) + "B";
  if (n >= 1e6)  return "S/ " + (n/1e6).toFixed(1) + "M";
  if (n >= 1000) return "S/ " + (n/1000).toFixed(0) + "K";
  return "S/ " + n;
}

function tagObj(tipo) {
  const map = { BIEN: ["tag-bien","Bien"], SERVICIO: ["tag-servicio","Servicio"], OBRA: ["tag-obra","Obra"] };
  const [cls, lbl] = map[tipo] || ["tag-bien", tipo || "—"];
  return `<span class="tag-obj ${cls}">${lbl}</span>`;
}

function badgeUrg(urg, dias) {
  const lbl = urg === "vencido" ? "Vencido" : dias === 0 ? "Hoy" : `${dias}d`;
  return `<span class="badge-urg ${urg}">${lbl}</span>`;
}

// ── BARRA DE PROGRESO TEMPORAL ───────────────────────────
function barraProgreso(c) {
  const pub  = c.fecha_publicacion ? new Date(c.fecha_publicacion) : null;
  const ven  = c.fecha_vencimiento ? new Date(c.fecha_vencimiento) : null;
  if (!pub || !ven) return "";

  const total     = Math.max(1, Math.round((ven - pub) / 86400000));
  const transcurridos = Math.round((hoy() - pub) / 86400000);
  const pct       = Math.min(100, Math.max(0, Math.round((transcurridos / total) * 100)));
  const restantes = Math.max(0, total - transcurridos);
  const colorCls  = c.urg === "urgente" ? "urgente" : c.urg === "proximo" ? "proximo" : c.urg === "vencido" ? "concluida" : "activa";

  return `
    <div class="ficha-progreso">
      <div class="ficha-progreso-label">
        <span>Publicado</span>
        <span>Cierre</span>
      </div>
      <div class="ficha-progreso-barra">
        <div class="ficha-progreso-fill ${colorCls}" style="width:${pct}%"></div>
      </div>
      <div class="ficha-progreso-fechas">
        <span>${fmtFecha(c.fecha_publicacion)}</span>
        <span>${fmtFecha(c.fecha_vencimiento)}</span>
      </div>
      <div class="ficha-progreso-dias">
        ${c.urg === "vencido"
          ? "Proceso concluido"
          : `${transcurridos} días transcurridos &nbsp;·&nbsp; <strong>${restantes} días restantes</strong>`}
      </div>
    </div>`;
}

// ── CARGA SUPABASE ───────────────────────────────────────
async function cargar() {
  const sesion = await verificarSesion();
  if (!sesion) return;

  document.getElementById("header-user").textContent = sesion.user.email || "";

  try {
    let acum = [], offset = 0;
    while (true) {
      const r = await fetch(
        `${SUPABASE_URL}/rest/v1/convocatorias?select=*&order=fecha_publicacion.desc&limit=1000&offset=${offset}`,
        { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } }
      );
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      acum = acum.concat(d);
      if (d.length < 1000) break;
      offset += 1000;
    }

    todas = acum.map(c => {
      const dias = diasRestantes(c.fecha_vencimiento);
      return { ...c, dias, urg: urgencia(dias) };
    });

    const abiertas   = todas.filter(c => c.dias >= 0).length;
    const concluidas = todas.filter(c => c.dias < 0).length;

    document.getElementById("tab-abiertas").textContent   = `🟢 Abiertas (${abiertas})`;
    document.getElementById("tab-concluidas").textContent = `📁 Concluidas (${concluidas})`;

    const ultima = todas[0]?.fecha_publicacion?.slice(0,10) || "";
    document.getElementById("header-meta").textContent =
      `${todas.length} convocatorias · actualizado ${ultima}`;

    aplicarFiltros();
  } catch(e) {
    document.getElementById("contenido-lista").innerHTML =
      `<div class="msg-center">Error cargando datos: ${e.message}</div>`;
  }
}

// ── VISTA ESTADO (Abiertas / Concluidas) ─────────────────
function setVistaEstado(v) {
  vistaEstado = v;
  document.getElementById("tab-abiertas").classList.toggle("activo",   v === "abiertas");
  document.getElementById("tab-concluidas").classList.toggle("activo", v === "concluidas");
  document.getElementById("tab-concluidas").classList.toggle("concluidas", true);
  pagina = 1;
  aplicarFiltros();
}

// ── FILTROS ──────────────────────────────────────────────
function aplicarFiltros() {
  const busq  = document.getElementById("f-busqueda").value.toLowerCase().trim();
  const objs  = [...document.querySelectorAll(".check-group input:checked")].map(i => i.value);
  const reg   = document.getElementById("f-region").value;
  const urg   = document.getElementById("f-urgencia").value;
  const monto = parseInt(document.getElementById("f-monto").value) || 0;

  const base = vistaEstado === "abiertas"
    ? todas.filter(c => c.dias >= 0)
    : todas.filter(c => c.dias < 0);

  filtradas = base.filter(c => {
    if (busq && !`${c.titulo||""} ${c.entidad||""}`.toLowerCase().includes(busq)) return false;
    if (objs.length && !objs.includes(c.tipo)) return false;
    if (reg  && c.region !== reg)  return false;
    if (urg  && c.urg   !== urg)   return false;
    if (monto && (c.monto || 0) < monto) return false;
    return true;
  });

  pagina = 1;
  actualizarStats();
  renderAlertas();
  renderLista();
  renderTimeline();
  renderGraficos();
}

function limpiarFiltros() {
  document.getElementById("f-busqueda").value = "";
  document.getElementById("f-region").value   = "";
  document.getElementById("f-urgencia").value = "";
  document.getElementById("f-monto").value    = "0";
  document.querySelectorAll(".check-group input").forEach(i => i.checked = false);
  aplicarFiltros();
}

// ── STATS ────────────────────────────────────────────────
function actualizarStats() {
  const urg  = filtradas.filter(c => c.urg === "urgente").length;
  const prox = filtradas.filter(c => c.urg === "proximo").length;
  const tot  = filtradas.reduce((s,c) => s + (c.monto||0), 0);
  document.getElementById("s-total").textContent   = filtradas.length;
  document.getElementById("s-urgente").textContent = urg;
  document.getElementById("s-proximo").textContent = prox;
  document.getElementById("s-monto").textContent   = fmtMontoCorto(tot);
}

// ── ALERTAS ──────────────────────────────────────────────
function renderAlertas() {
  if (vistaEstado !== "abiertas") {
    document.getElementById("alertas-wrap").innerHTML = "";
    return;
  }
  const urgentes = filtradas.filter(c => c.urg === "urgente").slice(0, 3);
  document.getElementById("alertas-wrap").innerHTML = urgentes.map(c =>
    `<div class="alerta-banner">&#128680; <strong>URGENTE${c.dias === 0 ? " — HOY" : ` — ${c.dias}d`}:</strong>
    &nbsp;${(c.titulo||"").slice(0,80)} — <em>${(c.entidad||"").slice(0,40)}</em></div>`
  ).join("");
}

// ── FICHA / DRAWER ───────────────────────────────────────
async function abrirFicha(id) {
  const c = todas.find(x => x.id === id);
  if (!c) return;

  const drawer  = document.getElementById("drawer");
  const overlay = document.getElementById("drawer-overlay");
  const body    = document.getElementById("drawer-body");

  drawer.classList.add("open");
  overlay.classList.add("open");

  const linkSeace = c.url_seace
    ? `<a class="link-seace" href="${c.url_seace}" target="_blank">Ver en SEACE &#8594;</a>`
    : "";

  body.innerHTML = `
    <div class="ficha-titulo">${c.titulo || c.descripcion || "Sin título"}</div>
    <div class="ficha-entidad">${c.entidad || "—"}</div>
    ${barraProgreso(c)}
    <div class="ficha-datos">
      <div><div class="ficha-dato-lbl">Nomenclatura</div><div class="ficha-dato-val">${c.nomenclatura || "—"}</div></div>
      <div><div class="ficha-dato-lbl">Objeto</div><div class="ficha-dato-val">${c.tipo || "—"}</div></div>
      <div><div class="ficha-dato-lbl">Región</div><div class="ficha-dato-val">${c.region || "—"}</div></div>
      <div><div class="ficha-dato-lbl">Monto</div><div class="ficha-dato-val">${fmtMonto(c.monto)}</div></div>
      <div><div class="ficha-dato-lbl">Estado</div><div class="ficha-dato-val">${badgeUrg(c.urg, c.dias)}</div></div>
      <div><div class="ficha-dato-lbl">SEACE</div><div class="ficha-dato-val">${linkSeace || "—"}</div></div>
    </div>
    <div class="ficha-seccion-titulo">Documentos</div>
    <div id="ficha-docs"><div class="msg-center"><div class="spinner"></div>Buscando documentos...</div></div>
  `;

  try {
    const nomEnc = encodeURIComponent(c.nomenclatura || "");
    const r = await fetch(
      `${SUPABASE_URL}/rest/v1/documentos?nomenclatura=eq.${nomEnc}&select=*&order=id.asc`,
      { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } }
    );
    if (!r.ok) throw new Error(r.status);
    const docs = await r.json();

    if (!docs.length) {
      document.getElementById("ficha-docs").innerHTML =
        `<div class="msg-center" style="padding:20px">Documentos aún no extraídos para esta convocatoria.</div>`;
      return;
    }

    const grupos = {};
    docs.forEach(d => {
      const et = d.etapa || "Sin etapa";
      if (!grupos[et]) grupos[et] = [];
      grupos[et].push(d);
    });

    document.getElementById("ficha-docs").innerHTML = Object.entries(grupos).map(([etapa, lista]) => `
      <div class="etapa-grupo">
        <div class="etapa-nombre">${etapa} (${lista.length})</div>
        ${lista.map(d => `
          <div class="doc-item">&#128196;
            ${d.url_descarga
              ? `<a href="${d.url_descarga}" target="_blank">${d.nombre_doc || "Documento"}</a>`
              : `<span class="doc-sin-enlace">${d.nombre_doc || "Documento"} (sin enlace)</span>`}
          </div>`).join("")}
      </div>`).join("");

  } catch(e) {
    document.getElementById("ficha-docs").innerHTML =
      `<div class="msg-center" style="padding:20px">Error cargando documentos: ${e.message}</div>`;
  }
}

function cerrarFicha() {
  document.getElementById("drawer").classList.remove("open");
  document.getElementById("drawer-overlay").classList.remove("open");
}

document.addEventListener("keydown", e => {
  if (e.key === "Escape") cerrarFicha();
});

// ── LISTA ────────────────────────────────────────────────
function setVista(v) {
  vista = v;
  document.getElementById("btn-tabla").classList.toggle("active", v === "tabla");
  document.getElementById("btn-cards").classList.toggle("active", v === "cards");
  renderLista();
}

function renderLista() {
  const inicio = (pagina - 1) * POR_PAGINA;
  const pag    = filtradas.slice(inicio, inicio + POR_PAGINA);
  const total  = filtradas.length;
  const totPag = Math.ceil(total / POR_PAGINA);

  document.getElementById("toolbar-info").textContent =
    total === 0 ? "Sin resultados" :
    `Mostrando ${inicio+1}–${Math.min(inicio+POR_PAGINA, total)} de ${total}`;
  document.getElementById("pag-info").textContent =
    total === 0 ? "" : `Página ${pagina} de ${totPag}`;
  document.getElementById("btn-prev").disabled = pagina <= 1;
  document.getElementById("btn-next").disabled = pagina >= totPag;

  if (!pag.length) {
    document.getElementById("contenido-lista").innerHTML =
      `<div class="msg-center">Sin convocatorias con esos filtros.</div>`;
    return;
  }

  if (vista === "tabla") {
    const filas = pag.map(c => `
      <tr>
        <td class="td-titulo">
          <div class="titulo-txt">${c.titulo || c.descripcion || "Sin título"}</div>
          <div class="entidad-txt">${c.entidad || "—"}</div>
        </td>
        <td>${tagObj(c.tipo)}</td>
        <td class="region-txt">${c.region || "—"}</td>
        <td class="monto-txt">${fmtMonto(c.monto)}</td>
        <td>${badgeUrg(c.urg, c.dias)}</td>
        <td><button class="btn-docs" onclick="abrirFicha(${c.id})">&#128196; Docs</button></td>
      </tr>`).join("");
    document.getElementById("contenido-lista").innerHTML = `
      <table>
        <thead><tr>
          <th>Título / Entidad</th><th>Objeto</th><th>Región</th>
          <th>Monto</th><th>Vence</th><th>Ficha</th>
        </tr></thead>
        <tbody>${filas}</tbody>
      </table>`;
  } else {
    const cards = pag.map(c => `
      <div class="card ${c.urg}">
        <div class="card-titulo">${(c.titulo || c.descripcion || "Sin título").slice(0,90)}</div>
        <div class="card-meta">
          <span>&#127963; ${(c.entidad||"—").slice(0,50)}</span>
          <span>&#128205; ${c.region||"—"} &nbsp;·&nbsp; ${tagObj(c.tipo)}</span>
          <span>&#128176; ${fmtMonto(c.monto)}</span>
        </div>
        <div class="card-footer">
          ${badgeUrg(c.urg, c.dias)}
          <button class="btn-docs" onclick="abrirFicha(${c.id})">&#128196; Docs</button>
        </div>
      </div>`).join("");
    document.getElementById("contenido-lista").innerHTML = `<div class="cards-grid">${cards}</div>`;
  }
}

function cambiarPagina(dir) {
  pagina = Math.max(1, Math.min(Math.ceil(filtradas.length/POR_PAGINA), pagina + dir));
  renderLista();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── TIMELINE ────────────────────────────────────────────
function renderTimeline() {
  const activas = filtradas.filter(c => c.urg !== "vencido").slice(0, 40);
  if (!activas.length) {
    document.getElementById("contenido-timeline").innerHTML =
      `<div class="msg-center">Sin convocatorias activas.</div>`;
    return;
  }
  const sorted  = [...activas].sort((a,b) => a.dias - b.dias);
  const maxDias = Math.max(...sorted.map(c => c.dias), 1);
  const cols    = { urgente:"#C53030", proximo:"#B7791F", normal:"#276749" };
  document.getElementById("contenido-timeline").innerHTML = sorted.map(c => {
    const pct = Math.max(5, Math.round((c.dias / maxDias) * 100));
    const col = cols[c.urg] || "#718096";
    const lbl = c.dias === 0 ? "HOY" : `${c.dias}d`;
    return `<div class="tl-item">
      <div class="tl-nombre">
        <div>${(c.titulo||"").slice(0,50)}…</div>
        <div class="tl-entidad">${(c.entidad||"").slice(0,40)}</div>
      </div>
      <div class="tl-bar-wrap">
        <div class="tl-bar" style="width:${pct}%;background:${col}">${lbl}</div>
      </div>
      <div class="tl-dias" style="color:${col}">${lbl}</div>
    </div>`;
  }).join("");
}

// ── GRAFICOS ────────────────────────────────────────────
function contarPor(arr, key) {
  return arr.reduce((acc, c) => {
    const v = c[key] || "Otro"; acc[v] = (acc[v]||0) + 1; return acc;
  }, {});
}

function sumarPor(arr, key, valKey) {
  return arr.reduce((acc, c) => {
    const v = c[key] || "Otro"; acc[v] = (acc[v]||0) + (c[valKey]||0); return acc;
  }, {});
}

function mkChart(id, type, labels, data, colors, opts={}) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(canvas, {
    type,
    data: { labels, datasets: [{ data, backgroundColor: colors, borderRadius: type==="bar"?6:0 }] },
    options: { responsive: true, plugins: { legend: { position: type==="doughnut"?"bottom":"top", labels:{font:{size:11}} } }, ...opts }
  });
}

function renderGraficos() {
  const COLORES = ["#2557A7","#276749","#C05621","#805AD5","#C53030","#B7791F","#319795","#D53F8C"];

  const obj = contarPor(filtradas, "tipo");
  mkChart("chart-objeto","doughnut", Object.keys(obj), Object.values(obj), COLORES);

  const urgMap = { urgente:0, proximo:0, normal:0, vencido:0 };
  filtradas.forEach(c => urgMap[c.urg]++);
  mkChart("chart-urgencia","bar",
    ["Urgente","Próxima","Normal","Vencida"],
    [urgMap.urgente, urgMap.proximo, urgMap.normal, urgMap.vencido],
    ["#C53030","#B7791F","#276749","#718096"],
    { scales: { y: { beginAtZero:true, grid:{color:"#F4F6FA"} } } }
  );

  const reg    = contarPor(filtradas, "region");
  const topReg = Object.entries(reg).sort((a,b)=>b[1]-a[1]).slice(0,10);
  mkChart("chart-region","bar",
    topReg.map(r=>r[0]), topReg.map(r=>r[1]),
    COLORES,
    { indexAxis:"y", scales: { x:{beginAtZero:true,grid:{color:"#F4F6FA"}} } }
  );

  const mon = sumarPor(filtradas, "tipo", "monto");
  mkChart("chart-monto","doughnut", Object.keys(mon), Object.values(mon), COLORES);
}

// ── TABS ────────────────────────────────────────────────
function showTab(id, btn) {
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.getElementById(`tab-${id}`).classList.add("active");
  btn.classList.add("active");
}

// ── INIT ────────────────────────────────────────────────
cargar();
