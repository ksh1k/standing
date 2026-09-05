const COORD = "", MEMBER = "/member", POLL_MS = 1000;
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const SLOTS_PER_DAY = 32, GRID_START_HOUR = 7, SLOT_MINUTES = 30;
const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function qs(id) { return document.getElementById(id); }
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}
async function jget(u) {
  const r = await fetch(u);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
async function jpost(u, b) {
  const r = await fetch(u, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: b ? JSON.stringify(b) : null,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

const LS_CODE = "standing_student_code";
const LS_NAME = "standing_display_name";

function saveIdentity(code, name) {
  if (code) {
    localStorage.setItem(LS_CODE, code);
    localStorage.setItem("student_id", code);
  }
  if (name) localStorage.setItem(LS_NAME, name);
}
function loadIdentity() {
  return {
    code: localStorage.getItem("student_id") || localStorage.getItem(LS_CODE) || "",
    name: localStorage.getItem(LS_NAME) || "",
  };
}
function fillIdentityFields() {
  const id = loadIdentity();
  const sid = qs("student_id");
  const name = qs("display_name");
  if (sid && id.code && !sid.value) sid.value = id.code;
  if (name && id.name && !name.value) name.value = id.name;
}

/** Mon–Sun, 07:00–23:00, 30-min slots, 32/day → e.g. "Wed 14:00". */
function slotLabel(index) {
  const i = Number(index);
  if (!Number.isFinite(i) || i < 0 || i >= 224) return "slot " + index;
  const day = Math.floor(i / SLOTS_PER_DAY);
  const sid = i % SLOTS_PER_DAY;
  const mins = GRID_START_HOUR * 60 + sid * SLOT_MINUTES;
  const hh = Math.floor(mins / 60), mm = mins % 60;
  return DAYS[day] + " " + String(hh).padStart(2, "0") + ":" + String(mm).padStart(2, "0");
}

/** ISO → "Wed Sep 9, 2:00 PM" (browser-local). */
function formatWhen(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return esc(iso);
  let h = d.getHours(), m = d.getMinutes(), ap = h >= 12 ? "PM" : "AM";
  h = h % 12; if (h === 0) h = 12;
  return esc(
    WEEKDAY[d.getDay()] + " " + MONTHS[d.getMonth()] + " " + d.getDate() +
    ", " + h + ":" + String(m).padStart(2, "0") + " " + ap
  );
}

function memberDownHint(err) {
  const msg = String(err && err.message || err || "");
  if (/Failed to fetch|NetworkError|load failed|Network request failed|ECONNREFUSED/i.test(msg) ||
      (err && err.name === "TypeError")) {
    return "Member API must be on :8001. Start the member server and try again.";
  }
  return msg;
}

function setRunButtonDisabled(disabled) {
  const btn = qs("run_demo_btn") ||
    document.querySelector("button.primary-cta, button[onclick*=\"runDemoNegotiate\"]");
  if (btn) btn.disabled = !!disabled;
}

function updatePollBtn() {
  const btn = qs("poll_btn");
  if (!btn) return;
  btn.textContent = "Resume polling";
  btn.hidden = !!pollTimer;
}

async function submitAuth(ev) {
  if (ev) ev.preventDefault();
  const code = qs("student_id").value.trim();
  const name = qs("display_name").value.trim();
  const st = qs("auth_status");
  try {
    const res = await jpost(COORD + "/api/auth/register", {
      student_id: code, student_code: code, display_name: name,
    });
    const sid = res.student_id || res.student_code || code;
    const dn = (res.profile && res.profile.display_name) || res.display_name || name;
    saveIdentity(sid, dn);
    st.className = "status-ok";
    st.textContent = (res.status === "exists" ? "Welcome back " : "Registered ") +
      sid + ". Continue with profile below.";
  } catch (e) {
    st.className = "status-err";
    st.textContent = String(e.message || e);
  }
}

async function submitLogin() {
  const code = qs("student_id").value.trim();
  const st = qs("auth_status");
  try {
    const res = await jpost(COORD + "/api/auth/login", {
      student_id: code, student_code: code,
    });
    const p = res.profile || res;
    const sid = p.student_id || p.student_code || code;
    saveIdentity(sid, p.display_name);
    if (qs("display_name")) qs("display_name").value = p.display_name || "";
    if (qs("year") && p.year) qs("year").value = p.year;
    if (qs("group_size") && p.preferred_group_size)
      qs("group_size").value = String(p.preferred_group_size);
    if (qs("study_style") && p.study_style) qs("study_style").value = p.study_style;
    if (qs("courses") && p.courses) qs("courses").value = (p.courses || []).join(", ");
    if (qs("pool_course") && p.courses && p.courses[0])
      qs("pool_course").value = p.courses[0];
    st.className = "status-ok";
    st.textContent = "Logged in as " + (p.display_name || sid) + " (" + sid + ").";
  } catch (e) {
    st.className = "status-err";
    st.textContent = String(e.message || e);
  }
}

async function submitIntake(ev) {
  ev.preventDefault();
  const zones = [...document.querySelectorAll("input[name=zone]:checked")].map(el => el.value);
  const code = (qs("student_id") && qs("student_id").value.trim()) || loadIdentity().code;
  const name = (qs("display_name") && qs("display_name").value.trim()) || loadIdentity().name || code;
  const body = {
    student_id: code,
    display_name: name,
    year: qs("year").value,
    courses: qs("courses").value.split(",").map(s => s.trim()).filter(Boolean),
    preferred_group_size: +qs("group_size").value,
    preferred_zones: zones,
    study_style: qs("study_style").value,
    time_of_day_preference: {
      morning: +qs("tod_m").value,
      afternoon: +qs("tod_a").value,
      evening: +qs("tod_e").value,
    },
  };
  const st = qs("intake_status");
  try {
    if (!code) throw new Error("Enter a student code first");
    await jpost(COORD + "/api/auth/register", {
      student_id: code, student_code: code, display_name: name,
    });
    const res = await jpost(MEMBER + "/api/intake", body);
    saveIdentity(res.student_id, name);
    if (qs("pool_course") && body.courses[0])
      qs("pool_course").value = body.courses[0];
    const joins = [];
    for (const c of body.courses) {
      joins.push(await joinCourse(res.student_id, c));
    }
    const last = joins[joins.length - 1];
    const waiting = last ? (last.waiting_count || last.pool_size || 0) : 0;
    st.className = "status-ok";
    st.innerHTML = "Saved <strong>" + esc(res.student_id) +
      "</strong> and joined pool(s). Waiting: " + esc(waiting) +
      ". <a class=\"btn\" href=\"/groups.html\">My groups →</a>";
    if (qs("pool_status") && last) {
      qs("pool_status").className = "status-ok";
      qs("pool_status").textContent = "Joined · waiting " + waiting +
        (last.ready_to_match ? " · ready to match" : "");
    }
    await refreshPool();
  } catch (e) {
    st.className = "status-err";
    st.textContent = memberDownHint(e);
  }
}

async function joinCourse(studentId, courseCode) {
  return jpost(COORD + "/api/pools/join", {
    student_id: studentId,
    student_code: studentId,
    course_code: courseCode,
  });
}

async function matchCourse(courseCode) {
  return jpost(COORD + "/api/pools/match", { course_code: courseCode });
}

async function loadPool(courseCode) {
  return jget(COORD + "/api/pools?course_code=" + encodeURIComponent(courseCode));
}

async function joinPool() {
  const st = qs("pool_status");
  const code = (qs("student_id") && qs("student_id").value.trim()) || loadIdentity().code;
  const course = (qs("pool_course") && qs("pool_course").value.trim()) ||
    ((qs("courses") && qs("courses").value.split(",")[0] || "").trim());
  try {
    if (!code || !course) throw new Error("Need student code and course");
    saveIdentity(code);
    const res = await joinCourse(code, course);
    st.className = "status-ok";
    st.textContent = res.status + " · pool size " + (res.pool_size || res.waiting_count) +
      (res.ready_to_match ? " · ready to match (≥4)" : " · waiting for more students");
    await refreshPool();
  } catch (e) {
    st.className = "status-err";
    st.textContent = String(e.message || e);
  }
}

async function matchPool() {
  const st = qs("pool_status");
  const course = (qs("pool_course") && qs("pool_course").value.trim()) ||
    ((qs("courses") && qs("courses").value.split(",")[0] || "").trim());
  try {
    if (!course) throw new Error("Need a course code");
    const res = await matchCourse(course);
    st.className = res.status === "ok" ? "status-ok" : "status-err";
    st.textContent = res.status + " · groups " + (res.groups || []).length +
      " · pool was " + res.pool_size;
    await refreshPool();
  } catch (e) {
    st.className = "status-err";
    st.textContent = String(e.message || e);
  }
}

async function refreshPool() {
  const box = qs("pool_list");
  const st = qs("pool_status");
  if (!box) return;
  const course = (qs("pool_course") && qs("pool_course").value.trim()) ||
    ((qs("courses") && qs("courses").value.split(",")[0] || "").trim());
  if (!course) {
    box.innerHTML = "";
    return;
  }
  try {
    const data = await loadPool(course);
    const codes = data.student_codes || (data.members || []).map(m => m.student_id || m);
    box.innerHTML = "<p class=\"muted\">" + esc(data.course_code) + " wait pool: " +
      (data.waiting_count != null ? data.waiting_count : data.pool_size) +
      " waiting</p><ul>" +
      codes.map(c => "<li><code>" + esc(c) + "</code></li>").join("") + "</ul>";
  } catch (e) {
    if (st) { st.className = "status-err"; st.textContent = String(e.message || e); }
  }
}

async function loadMyGroups() {
  const sidEl = qs("student_id"), box = qs("groups_list");
  if (!box) return;
  let sid = sidEl ? sidEl.value.trim() : "";
  if (!sid) sid = loadIdentity().code;
  if (sidEl && sid && !sidEl.value.trim()) sidEl.value = sid;
  if (!sid) {
    box.innerHTML = "<div class=\"empty\"><strong>Enter your student code</strong><p>Then load your sessions.</p></div>";
    return;
  }
  box.innerHTML = "<p class=\"muted\">Loading…</p>";
  try {
    const data = await jget(MEMBER + "/api/groups?student_id=" + encodeURIComponent(sid));
    box.innerHTML = data.groups.length
      ? data.groups.map(g =>
          "<div class=\"card group-card\"><strong>" + esc(g.group_id) + "</strong><ul>" +
          g.sessions.map(s =>
            "<li>" + formatWhen(s.scheduled_datetime) + " @ " + esc(s.location) + "</li>"
          ).join("") +
          "</ul></div>"
        ).join("")
      : "<div class=\"empty\"><strong>No sessions yet</strong>" +
        "<p>Join a course pool and run match, or use the demo on the Demo page.</p>" +
        "<a class=\"btn secondary\" href=\"/dashboard.html\">Go to dashboard</a></div>";
  } catch (e) {
    box.innerHTML = "<p class=\"status-err\">" + esc(memberDownHint(e)) + "</p>";
  }
}

async function loadCoordGroups() {
  const sidEl = qs("filter_student"), sid = sidEl ? sidEl.value.trim() : "", box = qs("coord_groups");
  if (!box) return;
  try {
    const data = await jget(sid
      ? COORD + "/api/groups?student_id=" + encodeURIComponent(sid)
      : COORD + "/api/groups");
    box.innerHTML = data.groups.length
      ? data.groups.map(g =>
          "<div class=\"card group-card\"><strong>" + esc(g.course_code) +
          "</strong> <span class=\"pill\">" + esc(g.status) + "</span>" +
          "<div class=\"group-meta\">" + esc(g.slot_label || "unscheduled") +
          " · " + esc(g.zone || "—") + " · " + esc(g.member_count) + " members</div>" +
          "<div><a class=\"btn\" href=\"" + COORD + "/api/ics/" + encodeURIComponent(g.group_id) +
          "\">Download .ics</a></div></div>"
        ).join("")
      : "<div class=\"empty\"><strong>No scheduled groups yet</strong>" +
        "<p>Run the demo above. Confirmed groups and .ics downloads will show up here.</p></div>";
  } catch (e) {
    box.innerHTML = "<p class=\"status-err\">" + esc(e.message) + "</p>";
  }
}

let lineOffset = 0, pollTimer = null;

function renderLine(line) {
  const t = line.type || "?";
  const label = slotLabel(line.start_slot);
  let d;
  if (t === "PROPOSE") {
    d = "Proposed " + esc(label) + " <span class=\"muted\">(slot " + esc(line.start_slot) + ")</span>";
  } else if (t === "CONFIRM") {
    d = "Confirmed " + esc(label) + " <span class=\"muted\">(slot " + esc(line.start_slot) + ")</span>";
  } else if (t === "RESPOND") {
    const v = line.verdict || {};
    const kind = v.kind || JSON.stringify(v);
    d = "Responded " + esc(label) + " → " + esc(kind) +
      (v.delta != null ? " (shift " + esc(v.delta) + ")" : "") +
      " <span class=\"muted\">(slot " + esc(line.start_slot) + ")</span>";
  } else {
    d = esc(JSON.stringify(line));
  }
  return "<div class=\"msg " + esc(t) + "\"><strong>" + esc(t) + "</strong> " + d + "</div>";
}

function ensureTranscriptPlaceholder() {
  const box = qs("transcript");
  if (!box) return;
  if (!box.dataset.ready) {
    box.dataset.ready = "1";
    if (!box.innerHTML.trim()) {
      box.innerHTML = "<div class=\"empty transcript-empty\"><strong>Negotiation will appear here…</strong>" +
        "<p>Click <em>Run 5-student demo</em> to watch PROPOSE / RESPOND / CONFIRM live.</p></div>";
    }
  }
}

async function pollTranscript() {
  const box = qs("transcript");
  if (!box) return;
  try {
    const data = await jget(COORD + "/api/transcript?after=" + lineOffset + "&limit=200");
    if (data.lines.length) {
      if (box.querySelector(".transcript-empty")) box.innerHTML = "";
      box.insertAdjacentHTML("beforeend", data.lines.map(renderLine).join(""));
      lineOffset = data.after + data.lines.length;
      box.scrollTop = box.scrollHeight;
    }
    const st = qs("demo_status");
    if (!st) return;
    const ds = await jget(COORD + "/api/demo/status");
    st.textContent = ds.running
      ? "Negotiation running…"
      : (ds.last
        ? ("Last: " + ds.last.status + " · " + slotLabel(ds.last.start_slot) + " · " + ds.last.rounds + " rounds")
        : "Idle");
    st.className = ds.running ? "pill warn" : (ds.last ? "pill ok" : "pill muted");
    setRunButtonDisabled(!!ds.running);
  } catch (e) { /* keep UI quiet while polling */ }
}

function startPolling() {
  ensureTranscriptPlaceholder();
  if (pollTimer) { updatePollBtn(); return; }
  pollTranscript();
  pollTimer = setInterval(pollTranscript, POLL_MS);
  updatePollBtn();
}

async function runDemoNegotiate() {
  lineOffset = 0;
  const box = qs("transcript");
  if (box) {
    box.innerHTML = "";
    box.dataset.ready = "1";
  }
  setRunButtonDisabled(true);
  try {
    await jpost(COORD + "/api/demo/negotiate?background=true");
  } catch (e) {
    setRunButtonDisabled(false);
    if (box) box.innerHTML = "<p class=\"status-err\">" + esc(e.message) + "</p>";
    return;
  }
  startPolling();
}

document.addEventListener("DOMContentLoaded", function () {
  fillIdentityFields();
  const sid = qs("student_id");
  if (qs("groups_list") && sid && (sid.value.trim() || loadIdentity().code)) loadMyGroups();
  if (qs("pool_list") && qs("pool_course") && qs("pool_course").value.trim()) refreshPool();
  if (qs("transcript")) {
    ensureTranscriptPlaceholder();
    updatePollBtn();
  }
});

window.StandingUI = {
  submitAuth, submitLogin, submitIntake, joinPool, matchPool, refreshPool,
  joinCourse, matchCourse, loadPool,
  loadMyGroups, loadCoordGroups, startPolling, runDemoNegotiate, POLL_MS,
};
