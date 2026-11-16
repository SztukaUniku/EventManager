/* EventManager – aplikacja na telefon.
   Dane: data/events.json (budowane co tydzień na GitHubie).
   Preferencje (ukryte wydarzenia, „nie mój klimat”) zostają tylko w tej przeglądarce. */
(function () {
  "use strict";

  const PREFS_KEY = "em-prefs-v1";
  const UI_KEY = "em-ui-v1";
  const DAY_NAMES = ["niedziela", "poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota"];
  const MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"];
  const CAT_ORDER = ["Teatr i performans", "Koncerty", "Imprezy i taniec", "Film", "Wystawy", "Spotkania i wykłady", "Warsztaty", "Inne", "Stand-up"];

  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fold = (s) => String(s || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/ł/g, "l").replace(/[^a-z0-9]+/g, " ").trim();

  // ---------------------------------------------------------------- pamięć
  function load(key, fallback) {
    try { const v = JSON.parse(localStorage.getItem(key)); return v && typeof v === "object" ? v : fallback; } catch (e) { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* tryb prywatny itp. */ }
  }

  const prefs = load(PREFS_KEY, { v: 1, rules: [] });
  if (!Array.isArray(prefs.rules)) prefs.rules = [];
  if (!Array.isArray(prefs.likes)) prefs.likes = [];          // ♥ Zapisane i „Dodaj do kalendarza” = sygnały „lubię”
  if (!Array.isArray(prefs.dismissed)) prefs.dismissed = [];  // odrzucone podpowiedzi „ukryć wszystkie?”
  const GENERIC = ["wykład / spotkanie", "oprowadzanie"];
  // Filtry: kilka kategorii naraz (lub), do tego „Za darmo” i „LGBT+” (zawężają), „Ukryte” to osobny widok.
  const ui = Object.assign({ range: "week", cats: [], free: false, lgbt: false, hidden: false, fav: false, p4u: false, ref: "a", maxkm: 0 }, load(UI_KEY, {}));
  if (!Array.isArray(ui.cats)) ui.cats = [];
  delete ui.filter;
  const state = { data: null, sources: null, excluded: null, open: new Set(), installEvent: null };

  // ---------------------------------------------------------------- daty
  function todayISO() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }
  function addDays(iso, n) {
    const [y, m, d] = iso.split("-").map(Number);
    const dt = new Date(y, m - 1, d + n);
    return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
  }
  function parts(iso) { const [y, m, d] = iso.split("-").map(Number); return { y, m, d, dow: new Date(y, m - 1, d).getDay() }; }
  function dayLabel(iso) {
    const p = parts(iso);
    const n = DAY_NAMES[p.dow];
    return { name: n.charAt(0).toUpperCase() + n.slice(1), date: `${p.d} ${MONTHS[p.m - 1]}` };
  }
  function shortDate(iso) { const p = parts(iso); return `${p.d}.${String(p.m).padStart(2, "0")}`; }

  // ---------------------------------------------------------------- reguły „nie dla mnie”
  function hiddenBy(ev) {
    for (const r of prefs.rules) {
      if (r.type === "event" && r.value === ev.id) return r;
      if (r.type === "tag" && (ev.tags || []).includes(r.value)) return r;
      if (r.type === "venue" && ev.venue && fold(ev.venue) === r.value) return r;
      if (r.type === "source" && ev.source === r.value) return r;
      if (r.type === "series" && fold(ev.title).startsWith(r.value)) return r;
    }
    return null;
  }

  // ---------------------------------------------------------------- ♥, „4U”, podpowiedzi
  const isFav = (id) => prefs.likes.some((l) => l.id === id && l.kind === "fav");
  function addLike(ev, kind) {
    if (prefs.likes.some((l) => l.id === ev.id)) { if (kind === "fav") prefs.likes.find((l) => l.id === ev.id).kind = "fav"; }
    else prefs.likes.push({ id: ev.id, kind, title: ev.title, tags: ev.tags || [], venue: fold(ev.venue || ""), venueName: ev.venue || "", at: new Date().toISOString() });
    save(PREFS_KEY, prefs);
  }
  function taste() {
    const tags = {}, venues = {};
    prefs.likes.forEach((l) => {
      (l.tags || []).filter((t) => !GENERIC.includes(t)).forEach((t) => { tags[t] = (tags[t] || 0) + 1; });
      if (l.venue) venues[l.venue] = { n: ((venues[l.venue] || {}).n || 0) + 1, name: l.venueName };
    });
    return { tags, venues };
  }
  let tasteCache = null;
  function why4u(ev) {   // powody podpowiedzi „4U” albo null; podpowiadamy dopiero po co najmniej 2 podobnych sygnałach
    if (!tasteCache) tasteCache = taste();
    if (isFav(ev.id)) return null;
    const r = (ev.tags || []).filter((t) => (tasteCache.tags[t] || 0) >= 2);
    const v = ev.venue && tasteCache.venues[fold(ev.venue)];
    if (v && v.n >= 2) r.push(ev.venue);
    return r.length ? r : null;
  }
  function suggestions() {   // „ukryłaś kilka wydarzeń z tym samym tagiem — ukrywać wszystkie?”
    const counts = {};
    prefs.rules.filter((r) => r.type === "event").forEach((r) => (r.tags || []).filter((t) => !GENERIC.includes(t)).forEach((t) => { counts[t] = (counts[t] || 0) + 1; }));
    return Object.keys(counts).filter((t) => counts[t] >= 3 && !prefs.dismissed.includes(t) && !prefs.rules.some((r) => r.type === "tag" && r.value === t))
      .map((t) => ({ tag: t, n: counts[t] }));
  }
  const distKey = () => (ui.ref === "b" ? "dist_b" : "dist_a");
  const refs = () => (state.data && state.data.refs) || {};
  const distOk = (e) => !ui.maxkm || !refs()[ui.ref] || e[distKey()] == null || e[distKey()] <= ui.maxkm;   // brak danych = nie ukrywamy

  // ---------------------------------------------------------------- dane
  async function fetchJSON(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(url + " " + r.status);
    return r.json();
  }

  async function init() {
    bindUI();
    try {
      if (window.EM_DATA) {  // podgląd: dane wbudowane w stronę
        state.data = window.EM_DATA.events;
        state.sources = window.EM_DATA.sources;
        state.excluded = window.EM_DATA.excluded;
      } else {
        const [data, sources] = await Promise.all([fetchJSON("data/events.json"), fetchJSON("data/sources.json").catch(() => null)]);
        state.data = data;
        state.sources = sources;
      }
    } catch (e) {
      $("#stamp").textContent = "Nie udało się wczytać danych";
      $("#list").innerHTML = `<div class="empty">Brak danych. Sprawdź połączenie z internetem i odśwież stronę.</div>`;
      return;
    }
    render();
  }

  function visibleEvents() {
    const t = todayISO();
    const end = ui.range === "week" ? addDays(t, 6) : addDays(t, 30);
    const inRange = (e) => (e.ongoing ? e.date <= end && e.date_to >= t : e.date >= t && e.date <= end);
    const all = (state.data.events || []).filter(inRange);
    const check = (state.data.check || []).filter(inRange);
    return { all, check, end };
  }

  // ---------------------------------------------------------------- widok
  function render() {
    const { all, check } = visibleEvents();
    const shown = all.filter((e) => !hiddenBy(e));
    const hidden = all.filter((e) => hiddenBy(e));

    // nagłówek
    const gen = state.data.generated_at ? new Date(state.data.generated_at) : null;
    const genTxt = gen ? `${gen.getDate()}.${String(gen.getMonth() + 1).padStart(2, "0")}, ${String(gen.getHours()).padStart(2, "0")}:${String(gen.getMinutes()).padStart(2, "0")}` : "?";
    $("#stamp").textContent = `Aktualizacja ${genTxt} · ${shown.length} propozycji`;
    const age = gen ? (Date.now() - gen.getTime()) / 86400000 : 99;
    const banner = $("#banner");
    if (age > 9) {
      banner.hidden = false;
      banner.textContent = `Dane mają ${Math.floor(age)} dni. Cotygodniowe odświeżenie mogło się nie udać — sprawdź „Źródła” w menu.`;
    } else banner.hidden = true;

    document.querySelectorAll(".seg button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.range === ui.range)));

    // chipy: liczby pokazują, ile zostanie po dodaniu danego filtra
    tasteCache = null;
    const base = (ui.hidden ? hidden : shown).filter(distOk);
    const flagsOk = (e) => (!ui.free || e.free) && (!ui.lgbt || (e.tags || []).includes("LGBT+")) && (!ui.fav || isFav(e.id)) && (!ui.p4u || why4u(e));
    const byFlags = base.filter(flagsOk);
    const counts = {};
    byFlags.forEach((e) => { counts[e.category] = (counts[e.category] || 0) + 1; });
    ui.cats = ui.cats.filter((c) => CAT_ORDER.includes(c));
    const inCats = (e) => !ui.cats.length || ui.cats.includes(e.category);
    const others = (skip) => (e) => inCats(e) && [["free", e.free], ["lgbt", (e.tags || []).includes("LGBT+")], ["fav", isFav(e.id)], ["p4u", !!why4u(e)]].every(([k, v]) => k === skip || !ui[k] || v);
    const free = base.filter((e) => e.free && others("free")(e)).length;
    const lgbt = base.filter((e) => (e.tags || []).includes("LGBT+") && others("lgbt")(e)).length;
    const favN = base.filter((e) => isFav(e.id) && others("fav")(e)).length;
    const p4uN = base.filter((e) => why4u(e) && others("p4u")(e)).length;
    let chips = `<button type="button" class="chip" data-cat="" aria-pressed="${!ui.cats.length}">Wszystko<span class="n">${byFlags.length}</span></button>`;
    CAT_ORDER.forEach((c) => {
      if (counts[c] || ui.cats.includes(c)) chips += `<button type="button" class="chip" data-cat="${esc(c)}" aria-pressed="${ui.cats.includes(c)}">${esc(c)}<span class="n">${counts[c] || 0}</span></button>`;
    });
    chips += `<span class="chip-sep" aria-hidden="true"></span>`;
    chips += `<button type="button" class="chip flag" data-flag="free" aria-pressed="${ui.free}">Za darmo<span class="n">${free}</span></button>`;
    chips += `<button type="button" class="chip flag" data-flag="lgbt" aria-pressed="${ui.lgbt}">LGBT+<span class="n">${lgbt}</span></button>`;
    chips += `<button type="button" class="chip flag" data-flag="fav" aria-pressed="${ui.fav}">♥ Zapisane<span class="n">${favN}</span></button>`;
    chips += `<button type="button" class="chip flag" data-flag="p4u" aria-pressed="${ui.p4u}">4U<span class="n">${p4uN}</span></button>`;
    if (hidden.length || ui.hidden) chips += `<button type="button" class="chip flag" data-flag="hidden" aria-pressed="${ui.hidden}">Ukryte<span class="n">${hidden.length}</span></button>`;
    $("#chips").innerHTML = chips;

    // odległość: punkt odniesienia + progi (tylko gdy w danych są odległości)
    const rf = refs(), dist = $("#dist");
    if (Object.keys(rf).length) {
      if (!rf[ui.ref]) ui.ref = Object.keys(rf)[0];
      dist.hidden = false;
      dist.innerHTML = `<span class="chip-lbl">Od:</span>` + Object.keys(rf).map((k) => `<button type="button" class="chip" data-ref="${k}" aria-pressed="${ui.ref === k}">${esc(rf[k])}</button>`).join("")
        + `<span class="chip-sep" aria-hidden="true"></span>` + [5, 10, 20].map((n) => `<button type="button" class="chip" data-km="${n}" aria-pressed="${ui.maxkm === n}">do ${n} km</button>`).join("")
        + `<span class="chip-lbl">km po drodze</span>`;
    } else dist.hidden = true;

    // lista
    const list = byFlags.filter(inCats);
    $("#stamp").textContent += ui.cats.length || ui.free || ui.lgbt || ui.hidden ? ` · widać ${list.length}` : "";

    const dated = list.filter((e) => !e.ongoing);
    const ongoing = list.filter((e) => e.ongoing).sort((a, b) => a.date_to.localeCompare(b.date_to));
    let html = suggestions().map((x) => `<div class="suggest"><span>Ukryłaś już ${x.n} wydarzeń z tagiem „${esc(x.tag)}”. Ukrywać wszystkie takie?</span><span class="sg-btns"><button type="button" class="btn primary" data-sug-yes="${esc(x.tag)}">Tak, ukryj</button><button type="button" class="btn" data-sug-no="${esc(x.tag)}">Nie</button></span></div>`).join("");
    let day = "";
    dated.forEach((e) => {
      if (e.date !== day) {
        if (day) html += "</section>";
        day = e.date;
        const l = dayLabel(e.date);
        const off = e.day_off && !["sobota", "niedziela"].includes(e.day_off) ? `<span class="off">${esc(e.day_off)}</span>` : "";
        html += `<section class="day${e.day_off || parts(e.date).dow === 5 ? " weekend" : ""}"><h2 class="day-h">${esc(l.name)} <span class="date">${esc(l.date)}</span>${off}</h2>`;
      }
      html += card(e, ui.hidden);
    });
    if (day) html += "</section>";
    if (ongoing.length) {
      html += `<section class="day"><h2 class="day-h">Wystawy trwające</h2><p class="section-p">Do obejrzenia w dowolny dzień otwarcia. W dni robocze część miejsc zamyka się przed 17:00.</p>`;
      ongoing.forEach((e) => { html += card(e, ui.hidden); });
      html += "</section>";
    }
    if (!html) html = `<div class="empty">${ui.hidden ? "Nic nie ukryłaś." : "Nic nie pasuje do tych filtrów. Spróbuj „30 dni” albo odznacz któryś filtr."}</div>`;
    $("#list").innerHTML = html;

    // do sprawdzenia
    const extra = $("#extra");
    extra.innerHTML = check.length ? `<details class="box"><summary>Do sprawdzenia (${check.length})</summary>
      <p class="section-p" style="margin-bottom:10px">Brakuje godziny w dzień roboczy albo danych nie udało się potwierdzić na stronie źródła. Nic nie zgadujemy — sprawdź sama.</p>
      <ul>${check.map((e) => `<li><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a><span class="why">${esc(shortDate(e.date))} · ${esc(e.venue || e.area || "")} · ${esc(e.check)}</span></li>`).join("")}</ul></details>` : "";
  }

  function card(e, isHidden) {
    const open = state.open.has(e.id);
    const time = e.ongoing ? `<div class="time none">do ${esc(shortDate(e.date_to))}</div>` : e.time ? `<div class="time">${esc(e.time)}</div>` : `<div class="time none">godz. ?</div>`;
    const where = [e.venue, e.area && e.area !== e.venue ? e.area : ""].filter(Boolean).join(" · ");
    const price = e.price ? `<span class="badge ${e.free ? "free" : "paid"}">${esc(e.price)}</span>` : `<span class="badge">cena: sprawdź na stronie</span>`;
    const lgbt = (e.tags || []).includes("LGBT+") ? `<span class="badge lgbt">LGBT+</span>` : "";
    const w4 = why4u(e);
    const fav = isFav(e.id);
    const rf = refs();
    const dk = distKey();
    const dist = rf[ui.ref] && e[dk] != null ? `<span class="badge dist" title="Odległość po drodze od: ${esc(rf[ui.ref])} (D – dom, P – praca)">${e.dist_approx ? "ok. " : ""}${e[dk]} km</span>` : "";
    const distAll = Object.keys(rf).filter((k) => e["dist_" + k] != null).map((k) => `${e["dist_" + k]} km od: ${esc(rf[k])}`).join(" · ");
    let more = "";
    const evUrl = e.url || sourceUrl(e.source);
    if (open) {
      const rule = isHidden ? hiddenBy(e) : null;
      more = `<div class="more">
        ${e.description ? `<p>${esc(e.description)}</p>` : ""}
        ${e.address ? `<p><span class="lbl">Adres:</span> ${esc(e.address)}</p>` : ""}
        ${distAll ? `<p><span class="lbl">Dojazd samochodem:</span> ${distAll} <span class="src">(D – dom, P – praca)</span>${e.dist_approx ? " (przybliżone — źródło nie podaje adresu)" : ""}</p>` : ""}
        ${w4 ? `<p><span class="lbl">4U:</span> podobne do tego, co zapisałaś lub dodałaś do kalendarza (${esc(w4.join(", "))}).</p>` : ""}
        <p><span class="lbl">Jak wziąć udział:</span> ${esc(e.how || "Szczegóły i bilety na stronie wydarzenia.")}</p>
        ${e.note ? `<p class="src">${esc(e.note)}</p>` : ""}
        <div class="actions">
          ${evUrl ? `<a class="btn primary" href="${esc(evUrl)}" target="_blank" rel="noopener">Strona wydarzenia</a>` : ""}
          ${e.ticket_url && e.ticket_url !== e.url ? `<a class="btn" href="${esc(e.ticket_url)}" target="_blank" rel="noopener">Bilety / zapisy</a>` : ""}
          <a class="btn" href="${esc(calendarLink(e))}" data-cal="${esc(e.id)}" target="_blank" rel="noopener">Dodaj do kalendarza</a>
          <a class="btn" href="${esc(routeLink(e))}" target="_blank" rel="noopener">Trasa</a>
          ${rule ? `<button type="button" class="btn" data-unhide="${esc(rule.id)}">Pokaż znowu</button>` : `<button type="button" class="btn nope" data-nope="${esc(e.id)}">Nie dla mnie</button>`}
        </div>
        ${rule ? `<p class="src">Ukryte: ${esc(rule.label)}</p>` : ""}
      </div>`;
    }
    return `<article class="card" id="e-${esc(e.id)}">
      <button type="button" class="fav${fav ? " on" : ""}" data-fav="${esc(e.id)}" aria-pressed="${fav}" aria-label="${fav ? "Usuń z zapisanych" : "Zapisz"}">${fav ? "♥" : "♡"}</button>
      <button type="button" class="card-main" data-toggle="${esc(e.id)}" aria-expanded="${open}">
        ${time}
        <div class="body">
          <span class="cat">${esc(e.category)}</span>
          <h3 class="title">${esc(e.title)}</h3>
          ${where ? `<div class="where">${esc(where)}</div>` : ""}
          <div class="badges">${price}${dist}${w4 ? `<span class="badge fu">4U</span>` : ""}${lgbt}</div>
        </div>
      </button>${more}</article>`;
  }

  function routeLink(e) {   // Mapy Google (domyślnie samochód; inne środki transportu są na górze widoku)
    const dest = [e.venue, e.address || (e.venue ? "" : e.area)].filter(Boolean).join(", ") || e.area || "";
    return "https://www.google.com/maps/dir/?api=1&travelmode=driving&destination=" + encodeURIComponent(dest + ", Polska");
  }

  function sourceUrl(id) {
    const s = ((state.sources && state.sources.sources) || []).find((x) => x.id === id);
    return s ? s.url : "";
  }

  function calendarLink(e) {
    const ymd = e.date.replace(/-/g, "");
    let dates;
    if (e.ongoing && e.date_to) {
      dates = `${ymd}/${addDays(e.date_to, 1).replace(/-/g, "")}`;   // wystawa: cały okres jako wydarzenie całodniowe
    } else if (e.time) {
      const [h, m] = e.time.split(":").map(Number);
      const start = `${ymd}T${String(h).padStart(2, "0")}${String(m).padStart(2, "0")}00`;
      const endH = h + 2;
      const endDate = endH >= 24 ? addDays(e.date, 1).replace(/-/g, "") : ymd;
      const end = `${endDate}T${String(endH % 24).padStart(2, "0")}${String(m).padStart(2, "0")}00`;
      dates = `${start}/${end}`;
    } else {
      dates = `${ymd}/${addDays(e.date, 1).replace(/-/g, "")}`;
    }
    const details = [`Kategoria: ${e.category}`, e.time ? `Start: ${e.time}` : "", e.price ? `Cena: ${e.price}` : "", e.description, e.how, e.url || sourceUrl(e.source)].filter(Boolean).join("\n\n");
    const loc = [e.venue, e.address || e.area].filter(Boolean).join(", ");
    const p = new URLSearchParams({ action: "TEMPLATE", text: e.title, dates, ctz: "Europe/Warsaw", details, location: loc });
    return "https://calendar.google.com/calendar/render?" + p.toString();
  }

  // ---------------------------------------------------------------- „nie dla mnie”
  function findEvent(id) { return (state.data.events || []).find((e) => e.id === id); }

  function openNope(id) {
    const e = findEvent(id);
    if (!e) return;
    const opts = [["event", e.id, "Tylko to wydarzenie", ""]];
    (e.tags || []).forEach((t) => opts.push(["tag", t, `Nie lubię tego klimatu: ${t}`, "ukryje wszystkie wydarzenia z tym tagiem"]));
    if (e.venue) opts.push(["venue", fold(e.venue), `To miejsce: ${e.venue}`, "ukryje wszystko z tego miejsca"]);
    const series = fold(e.title).split(" ").slice(0, 3).join(" ");
    if (series.length > 6) opts.push(["series", series, `Cykl „${e.title.split(/[|–:]/)[0].trim()}”`, "ukryje wydarzenia o tak samo zaczynającym się tytule"]);
    $("#nope-title").textContent = e.title;
    $("#nope-opts").innerHTML = opts.map(([type, value, label, hint], i) =>
      `<label class="opt"><input type="radio" name="nope" value="${i}" ${i === 0 ? "checked" : ""}><span>${esc(label)}${hint ? `<small>${esc(hint)}</small>` : ""}</span></label>`).join("");
    $("#nope-why").value = "";
    const dlg = $("#nope");
    dlg.returnValue = "";
    dlg.onclose = () => {
      if (dlg.returnValue !== "ok") return;
      const i = Number(($("#nope-opts input:checked") || {}).value || 0);
      const [type, value, label] = opts[i];
      const rule = { id: Math.random().toString(36).slice(2, 10), type, value, label, why: $("#nope-why").value.trim(), at: new Date().toISOString(), title: e.title, tags: e.tags || [] };
      prefs.rules.push(rule);
      save(PREFS_KEY, prefs);
      state.open.delete(e.id);
      render();
      toast(type === "event" ? "Ukryto wydarzenie" : `Ukryto: ${label}`, () => removeRule(rule.id));
    };
    dlg.showModal();
  }

  function removeRule(id) {
    prefs.rules = prefs.rules.filter((r) => r.id !== id);
    save(PREFS_KEY, prefs);
    render();
  }

  let toastTimer;
  function toast(msg, undo) {
    const t = $("#toast");
    t.innerHTML = `<span>${esc(msg)}</span>${undo ? `<button type="button">Cofnij</button>` : ""}`;
    t.hidden = false;
    if (undo) t.querySelector("button").onclick = () => { undo(); t.hidden = true; };
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 5000);
  }

  // ---------------------------------------------------------------- menu
  function openMenu(view) {
    const box = $("#menu-content");
    const h = $("#menu-h");
    if (!view) {
      h.textContent = "Menu";
      box.innerHTML = `<div class="menu-list">
        ${state.installEvent ? `<button class="btn primary" data-view="install">Zainstaluj aplikację</button>` : ""}
        <button class="btn" data-view="rules">Twoje reguły (${prefs.rules.length})</button>
        <button class="btn" data-view="sources">Źródła i ich stan</button>
        <button class="btn" data-view="excluded">Odrzucone automatycznie</button>
        <button class="btn" data-view="backup">Kopia zapasowa preferencji</button>
        <button class="btn" data-view="about">Jak to działa</button>
      </div>`;
    } else if (view === "rules") {
      h.textContent = "Twoje reguły";
      box.innerHTML = prefs.rules.length ? prefs.rules.slice().reverse().map((r) =>
        `<div class="rule"><span>${esc(r.label)}<small>${esc(r.type === "event" ? r.title : "")}${r.why ? ` · ${esc(r.why)}` : ""}</small></span><button class="btn ghost" data-unhide="${esc(r.id)}">Usuń</button></div>`).join("")
        : `<p class="section-p">Jeszcze nic nie ukryłaś. Otwórz wydarzenie i wybierz „Nie dla mnie”.</p>`;
    } else if (view === "sources") {
      h.textContent = "Źródła";
      const s = (state.sources && state.sources.sources) || [];
      const now = Date.now();
      box.innerHTML = `<p class="section-p">Zielone działają, żółte nie odpowiadają od ponad 7 dni, czerwone od ponad 14.</p>` + s.map((x) => {
        const last = x.last_ok_at ? new Date(x.last_ok_at) : null;
        const days = last ? (now - last.getTime()) / 86400000 : 999;
        const cls = days > 14 ? "bad" : days > 7 ? "warn" : "";
        return `<div class="src-row"><span class="dot ${cls}"></span><span><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a> · ${x.events} propozycji
          <small>${esc(x.area)} · ${last ? `ostatni udany odczyt ${last.getDate()}.${String(last.getMonth() + 1).padStart(2, "0")}` : "jeszcze nie odczytano"}${x.adapter === "snapshot" && !x.extracted_at && !x.events ? " · czeka na odczyt przez AI" : ""}</small></span></div>`;
      }).join("");
    } else if (view === "excluded") {
      h.textContent = "Odrzucone automatycznie";
      box.innerHTML = `<p class="section-p">Wczytywanie…</p>`;
      const show = (d) => {
        const t = todayISO();
        const ev = (d.events || []).filter((e) => (e.ongoing ? e.date_to >= t : e.date >= t));
        const groups = {};
        ev.forEach((e) => { const k = e.excluded.startsWith("dzień roboczy") ? "godzina w dzień roboczy" : e.excluded; (groups[k] = groups[k] || []).push(e); });
        box.innerHTML = `<p class="section-p">Tego nie widzisz na liście z powodu stałych reguł. Jeśli coś tu nie pasuje, napisz — poprawimy reguły.</p>` +
          Object.keys(groups).sort((a, b) => groups[b].length - groups[a].length).map((k) =>
            `<details class="box"><summary>${esc(k)} (${groups[k].length})</summary><ul>${groups[k].map((e) =>
              `<li><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a><span class="why">${esc(shortDate(e.date))}${e.time ? " " + esc(e.time) : ""} · ${esc(e.source_name)}${e.excluded.startsWith("dzień") ? " · " + esc(e.excluded) : ""}</span></li>`).join("")}</ul></details>`).join("");
      };
      if (state.excluded) show(state.excluded);
      else fetchJSON("data/excluded.json").then((d) => { state.excluded = d; show(d); }).catch(() => { box.innerHTML = `<p class="section-p">Nie udało się wczytać.</p>`; });
    } else if (view === "backup") {
      h.textContent = "Kopia zapasowa";
      box.innerHTML = `<p class="section-p">Twoje reguły są zapisane tylko w tej przeglądarce. Skopiuj ten tekst i zachowaj (np. w notatce), żeby przenieść je na inne urządzenie.</p>
        <textarea id="backup-text" readonly>${esc(JSON.stringify(prefs))}</textarea>
        <div class="actions"><button class="btn" data-copy>Kopiuj</button></div>
        <label class="field">Wklej kopię, aby przywrócić<textarea id="restore-text" placeholder='{"v":1,"rules":[...]}'></textarea></label>
        <div class="actions"><button class="btn primary" data-restore>Przywróć</button></div>`;
    } else if (view === "about") {
      h.textContent = "Jak to działa";
      box.innerHTML = `<p class="section-p">Co tydzień w poniedziałek nad ranem automat na GitHubie odczytuje wybrane strony domów kultury, muzeów i agregatorów. Wydarzenia dla dzieci, rodzin i seniorów, karaoke, disco polo, metal, kabaret, tańce towarzyskie, wydarzenia patriotyczne i komercyjne są odrzucane. W dni robocze zostają tylko wydarzenia zaczynające się między 17:00 a 23:00.</p>
        <p class="section-p">Każda pozycja ma link do źródła. Jeśli czegoś nie da się potwierdzić, trafia do „Do sprawdzenia”, a nie na listę.</p>
        <p class="section-p">Instalacja na Androidzie: w Chrome otwórz menu (⋮) i wybierz „Zainstaluj aplikację” albo „Dodaj do ekranu głównego”.</p>`;
    } else if (view === "install" && state.installEvent) {
      state.installEvent.prompt();
      state.installEvent = null;
      return openMenu();
    }
    if (view) box.insertAdjacentHTML("afterbegin", `<button class="btn ghost" data-view="" style="align-self:flex-start;margin-bottom:6px">← Wróć</button>`);
    const dlg = $("#menu");
    if (!dlg.open) dlg.showModal();
  }

  // ---------------------------------------------------------------- zdarzenia
  function bindUI() {
    document.addEventListener("click", (ev) => {
      const b = ev.target.closest("button, a");
      if (!b) return;
      if (b.dataset.range) { ui.range = b.dataset.range; save(UI_KEY, ui); render(); return; }
      if (b.dataset.cat !== undefined) {
        const c = b.dataset.cat;
        if (!c) ui.cats = [];
        else ui.cats = ui.cats.includes(c) ? ui.cats.filter((x) => x !== c) : ui.cats.concat(c);
        save(UI_KEY, ui); render(); return;
      }
      if (b.dataset.ref) { ui.ref = b.dataset.ref; save(UI_KEY, ui); render(); return; }
      if (b.dataset.km) { const n = Number(b.dataset.km); ui.maxkm = ui.maxkm === n ? 0 : n; save(UI_KEY, ui); render(); return; }
      if (b.dataset.fav) {
        const e = findEvent(b.dataset.fav);
        if (!e) return;
        if (isFav(e.id)) { prefs.likes = prefs.likes.filter((l) => l.id !== e.id); save(PREFS_KEY, prefs); toast("Usunięto z zapisanych"); }
        else { addLike(e, "fav"); toast("Zapisano ♥"); }
        render(); return;
      }
      if (b.dataset.cal) { const e = findEvent(b.dataset.cal); if (e) { addLike(e, "cal"); tasteCache = null; } return; }
      if (b.dataset.sugYes) {
        const t = b.dataset.sugYes;
        prefs.rules.push({ id: Math.random().toString(36).slice(2, 10), type: "tag", value: t, label: `Nie lubię tego klimatu: ${t}`, why: "podpowiedź aplikacji", at: new Date().toISOString(), title: "" });
        save(PREFS_KEY, prefs); render(); toast(`Ukryto tag „${t}”`); return;
      }
      if (b.dataset.sugNo) { prefs.dismissed.push(b.dataset.sugNo); save(PREFS_KEY, prefs); render(); return; }
      if (b.dataset.flag) { ui[b.dataset.flag] = !ui[b.dataset.flag]; save(UI_KEY, ui); render(); return; }
      if (b.dataset.toggle) {
        const id = b.dataset.toggle;
        state.open.has(id) ? state.open.delete(id) : state.open.add(id);
        render();
        return;
      }
      if (b.dataset.nope) { openNope(b.dataset.nope); return; }
      if (b.dataset.unhide) {
        removeRule(b.dataset.unhide);
        if ($("#menu").open) openMenu("rules");
        toast("Przywrócono");
        return;
      }
      if (b.id === "menu-btn") { openMenu(); return; }
      if (b.hasAttribute("data-close")) { $("#menu").close(); return; }
      if (b.dataset.view !== undefined) { openMenu(b.dataset.view || null); return; }
      if (b.hasAttribute("data-copy")) {
        const ta = $("#backup-text");
        const done = () => toast("Skopiowano");
        try { navigator.clipboard.writeText(ta.value).then(done, () => { ta.select(); }); } catch (e) { ta.select(); }
        return;
      }
      if (b.hasAttribute("data-restore")) {
        try {
          const p = JSON.parse($("#restore-text").value);
          if (!p || !Array.isArray(p.rules)) throw new Error();
          prefs.rules = p.rules;
          save(PREFS_KEY, prefs);
          render();
          toast(`Przywrócono ${p.rules.length} reguł`);
          openMenu();
        } catch (e) { toast("To nie wygląda na kopię z tej aplikacji"); }
      }
    });
    $("#menu").addEventListener("click", (e) => { if (e.target === $("#menu")) $("#menu").close(); });
    $("#nope").addEventListener("click", (e) => { if (e.target === $("#nope")) $("#nope").close("cancel"); });
    window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); state.installEvent = e; });
    if ("serviceWorker" in navigator && location.protocol === "https:" && !window.EM_DATA) {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    }
  }

  init();
})();
