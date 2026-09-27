"use strict";

/* Table & Vine — front-end for the Restaurant Reservations API.
   Vanilla JS; talks only to the JSON API served from the same origin. */

const $ = (sel) => document.querySelector(sel);

const state = {
  guests: 2,
  slot: null,       // "YYYY-MM-DDTHH:MM"
  table: null,      // {id, name, capacity}
  reservation: null, // created reservation object
};

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

/* ---------- helpers ---------- */

const pad = (n) => String(n).padStart(2, "0");

function localDateStr(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function tomorrow() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return localDateStr(d);
}

function prettyDate(dateStr) {
  return new Date(`${dateStr}T12:00:00`).toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

function hhmm(iso) {
  return iso.slice(11, 16);
}

function slotRange(slot) {
  const end = new Date(slot);
  end.setHours(end.getHours() + 2);
  return `${hhmm(slot)} – ${pad(end.getHours())}:${pad(end.getMinutes())}`;
}

let toastTimer = null;
function toast(message, kind = "error") {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast show ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = "toast"), 3200);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let body = null;
  try {
    body = await res.json();
  } catch (_) {
    /* empty body */
  }
  if (!res.ok) {
    const err = new Error((body && body.detail) || `Request failed (${res.status})`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

/* ---------- tab switching ---------- */

const TAB_LOADERS = {
  book: () => searchSlots(),
  reservations: () => loadReservations(),
  admin: () => {
    loadAdminTables();
    loadHours();
  },
};

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === name)
  );
  document.querySelectorAll(".panel").forEach((p) =>
    p.classList.toggle("active", p.id === `panel-${name}`)
  );
  (TAB_LOADERS[name] || (() => {}))();
}

/* ---------- booking flow ---------- */

function slotGridFor(dateStr, windows) {
  const jsDay = new Date(`${dateStr}T12:00:00`).getDay(); // 0 = Sunday in JS
  const weekday = (jsDay + 6) % 7; // the API numbers 0 = Monday
  const starts = [];
  for (const w of windows.filter((x) => x.weekday === weekday)) {
    const [oh, om] = w.opens.split(":").map(Number);
    const [ch, cm] = w.closes.split(":").map(Number);
    for (let m = oh * 60 + om; m + 120 <= ch * 60 + cm; m += 120) {
      starts.push(`${dateStr}T${pad(Math.floor(m / 60))}:${pad(m % 60)}`);
    }
  }
  return starts;
}

function hideCards() {
  ["#card-tables", "#card-form", "#card-done"].forEach((id) => $(id).classList.add("hidden"));
}

async function searchSlots() {
  hideCards();
  state.slot = null;
  state.table = null;
  const grid = $("#slot-grid");
  const date = $("#book-date").value;
  if (!date) {
    grid.innerHTML = `<p class="hint">Pick a date to see seatings.</p>`;
    return;
  }
  grid.innerHTML = `<p class="hint">Checking the book…</p>`;

  let windows;
  try {
    windows = await api("/api/admin/hours");
  } catch (err) {
    grid.innerHTML = `<p class="hint">Could not load operating hours — is the API running?</p>`;
    return;
  }

  const starts = slotGridFor(date, windows);
  if (!starts.length) {
    grid.innerHTML = `<p class="hint">We're closed on ${prettyDate(date)} — try another day.</p>`;
    return;
  }

  const now = new Date();
  const results = await Promise.all(
    starts.map(async (slot) => {
      if (new Date(slot) <= now) return { slot, tables: [], past: true };
      try {
        const r = await api(
          `/api/availability?start=${encodeURIComponent(slot)}&guests=${state.guests}`
        );
        return { slot, tables: r.available_tables, past: false };
      } catch (_) {
        return { slot, tables: [], past: false };
      }
    })
  );
  renderSlots(results);
}

function renderSlots(results) {
  const grid = $("#slot-grid");
  grid.innerHTML = "";
  if (results.every((r) => r.past)) {
    grid.innerHTML = `<p class="hint">No seatings left on this day — pick a later date.</p>`;
    return;
  }
  for (const r of results) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "slot";
    btn.disabled = r.past || r.tables.length === 0;
    btn.innerHTML =
      `<span class="when">${slotRange(r.slot)}</span>` +
      (r.past
        ? `<span class="free none">past</span>`
        : r.tables.length
          ? `<span class="free">${r.tables.length} table${r.tables.length > 1 ? "s" : ""} free</span>`
          : `<span class="free none">full</span>`);
    btn.addEventListener("click", () => showTables(r));
    grid.appendChild(btn);
  }
}

function showTables(r) {
  state.slot = r.slot;
  state.table = null;
  $("#tables-title").textContent = `Seatings at ${slotRange(r.slot)}`;
  $("#tables-hint").textContent =
    `${prettyDate(r.slot.slice(0, 10))} · ${state.guests} guest${state.guests > 1 ? "s" : ""} — pick a table:`;
  const list = $("#table-list");
  list.innerHTML = "";
  for (const t of r.tables) {
    const card = document.createElement("div");
    card.className = "table-card";
    card.innerHTML =
      `<div><div class="name">${t.name}</div><div class="seats">seats ${t.capacity}</div></div>` +
      `<button type="button" class="primary small">Select</button>`;
    card.querySelector("button").addEventListener("click", () => showForm(t));
    list.appendChild(card);
  }
  $("#card-tables").classList.remove("hidden");
  $("#card-tables").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function showForm(table) {
  state.table = table;
  $("#form-summary").textContent =
    `${table.name} · ${prettyDate(state.slot.slice(0, 10))} · ${slotRange(state.slot)} · ${state.guests} guests`;
  $("#card-form").classList.remove("hidden");
  $("#card-tables").classList.add("hidden");
}

async function submitBooking(event) {
  event.preventDefault();
  try {
    const r = await api("/api/reservations", {
      method: "POST",
      body: JSON.stringify({
        table_id: state.table.id,
        start: state.slot,
        guest_count: state.guests,
        customer_name: $("#cust-name").value.trim(),
        customer_phone: $("#cust-phone").value.trim(),
      }),
    });
    showDone(r);
  } catch (err) {
    toast(err.message);
    searchSlots(); // availability changed — refresh the grid
  }
}

function showDone(r) {
  state.reservation = r;
  $("#done-summary").textContent =
    `${r.table.name} · ${prettyDate(r.start.slice(0, 10))} · ${hhmm(r.start)} – ${hhmm(r.end)} · ` +
    `${r.guest_count} guests · under ${r.customer_name} · reference #${r.id}`;
  $("#card-done").classList.remove("hidden");
  $("#card-form").classList.add("hidden");
  $("#card-tables").classList.add("hidden");
}

async function cancelReservation(id, after) {
  try {
    await api(`/api/reservations/${id}/cancel`, { method: "POST" });
    toast("Reservation cancelled.", "ok");
  } catch (err) {
    toast(err.message);
  }
  if (after) after();
}

/* ---------- reservations tab ---------- */

async function loadReservations() {
  const box = $("#reservation-list");
  const date = $("#list-date").value;
  if (!date) {
    box.innerHTML = `<p class="hint">Pick a date to see that day's reservations.</p>`;
    return;
  }
  box.innerHTML = `<p class="hint">Loading…</p>`;
  let items;
  try {
    items = await api(`/api/reservations?date=${encodeURIComponent(date)}`);
  } catch (err) {
    box.innerHTML = `<p class="hint">${err.message}</p>`;
    return;
  }
  if (!items.length) {
    box.innerHTML = `<p class="hint">No reservations for ${prettyDate(date)}.</p>`;
    return;
  }
  box.innerHTML = "";
  for (const r of items) {
    const row = document.createElement("div");
    row.className = "res-row";
    row.innerHTML =
      `<div><div class="meta">${r.table.name} · ${hhmm(r.start)} – ${hhmm(r.end)} · ${r.guest_count} guests</div>` +
      `<div class="who">under ${r.customer_name} · ${r.customer_phone}</div></div>` +
      `<div class="right"><span class="chip ${r.status}">${r.status}</span>` +
      (r.status === "booked" ? ` <button type="button" class="linkish">Cancel</button>` : "") +
      `</div>`;
    const btn = row.querySelector("button");
    if (btn) btn.addEventListener("click", () => cancelReservation(r.id, loadReservations));
    box.appendChild(row);
  }
}

/* ---------- admin tab ---------- */

async function loadAdminTables() {
  const box = $("#admin-tables");
  let tables;
  try {
    tables = await api("/api/admin/tables");
  } catch (err) {
    box.innerHTML = `<p class="hint">${err.message}</p>`;
    return;
  }
  box.innerHTML = "";
  if (!tables.length) {
    box.innerHTML = `<p class="hint">No tables yet — add the first one below.</p>`;
  }
  for (const t of tables) {
    const row = document.createElement("div");
    row.className = "admin-row";
    row.innerHTML =
      `<div><strong>${t.name}</strong> <span class="seats">· seats ${t.capacity}</span></div>` +
      `<button type="button" class="linkish">Delete</button>`;
    row.querySelector("button").addEventListener("click", async () => {
      if (!confirm(`Delete table ${t.name}?`)) return;
      try {
        await api(`/api/admin/tables/${t.id}`, { method: "DELETE" });
        loadAdminTables();
      } catch (err) {
        toast(err.message);
      }
    });
    box.appendChild(row);
  }
}

async function loadHours() {
  let windows;
  try {
    windows = await api("/api/admin/hours");
  } catch (err) {
    $("#hours-editor").innerHTML = `<p class="hint">${err.message}</p>`;
    return;
  }
  const editor = $("#hours-editor");
  editor.innerHTML = "";
  WEEKDAYS.forEach((name, weekday) => {
    const w = windows.find((x) => x.weekday === weekday);
    const row = document.createElement("div");
    row.className = "admin-row";
    row.innerHTML =
      `<label class="check"><input type="checkbox" id="open-${weekday}" ${w ? "checked" : ""} /> <span>${name}</span></label>` +
      `<span class="times"><input type="time" id="from-${weekday}" value="${w ? w.opens.slice(0, 5) : "11:00"}" />` +
      `<span class="dash">–</span>` +
      `<input type="time" id="to-${weekday}" value="${w ? w.closes.slice(0, 5) : "23:00"}" /></span>`;
    editor.appendChild(row);
  });
}

async function saveHours() {
  const windows = [];
  for (let weekday = 0; weekday < 7; weekday++) {
    if (!$("#open-" + weekday).checked) continue;
    const opens = $("#from-" + weekday).value;
    const closes = $("#to-" + weekday).value;
    if (!opens || !closes || opens >= closes) {
      toast(`${WEEKDAYS[weekday]}: set both times, opening before closing.`);
      return;
    }
    windows.push({ weekday, opens, closes });
  }
  if (!windows.length) {
    toast("At least one day must be open.");
    return;
  }
  try {
    await api("/api/admin/hours", { method: "PUT", body: JSON.stringify({ windows }) });
    $("#hours-status").textContent = "Saved ✓";
    setTimeout(() => ($("#hours-status").textContent = ""), 2500);
    toast("Weekly schedule saved.", "ok");
  } catch (err) {
    toast(err.message);
  }
}

/* ---------- wire-up ---------- */

function setGuests(n) {
  state.guests = Math.min(20, Math.max(1, n));
  $("#guests-value").textContent = state.guests;
  searchSlots();
}

document.addEventListener("DOMContentLoaded", () => {
  $("#book-date").value = tomorrow();
  $("#list-date").value = tomorrow();

  document.querySelectorAll(".tab").forEach((t) =>
    t.addEventListener("click", () => switchTab(t.dataset.tab))
  );
  $("#book-date").addEventListener("change", searchSlots);
  $("#guests-minus").addEventListener("click", () => setGuests(state.guests - 1));
  $("#guests-plus").addEventListener("click", () => setGuests(state.guests + 1));
  $("#back-to-slots").addEventListener("click", hideCards);
  $("#back-to-tables").addEventListener("click", () => {
    $("#card-form").classList.add("hidden");
    $("#card-tables").classList.remove("hidden");
  });
  $("#booking-form").addEventListener("submit", submitBooking);
  $("#book-again").addEventListener("click", () => {
    hideCards();
    searchSlots();
  });
  $("#cancel-booking").addEventListener("click", () => {
    if (state.reservation) {
      cancelReservation(state.reservation.id, () => {
        hideCards();
        searchSlots();
      });
    }
  });
  $("#list-date").addEventListener("change", loadReservations);
  $("#add-table-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/admin/tables", {
        method: "POST",
        body: JSON.stringify({
          name: $("#new-table-name").value.trim(),
          capacity: Number($("#new-table-capacity").value),
        }),
      });
      $("#new-table-name").value = "";
      loadAdminTables();
    } catch (err) {
      toast(err.message);
    }
  });
  $("#save-hours").addEventListener("click", saveHours);

  searchSlots();
});
