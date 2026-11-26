#!/usr/bin/env python3
"""
Losowanie prezentów (Secret Santa) z wysyłką wyników przez WhatsApp Desktop (macOS).

- Każdy losuje dokładnie jedną osobę, każda osoba jest wylosowana dokładnie raz,
  nikt nie losuje siebie. Opcjonalnie jeden łańcuch A→B→C→…→A.
- Wyniki NIGDY nie są pokazywane w przeglądarce, w terminalu ani w logach.
  Są tylko w pamięci programu i znikają po „Zakończ” albo po zamknięciu programu.
- Przed wysyłką program ostrzega nadawcę, odlicza czas i podaje godzinę powrotu.
  Koniec wysyłki sygnalizuje dźwiękiem.

Uruchomienie:  python3 losowanie_whatsapp.py
Tryb próbny (nic nie wysyła, do testów):  python3 losowanie_whatsapp.py --dry-run
Wymaga: macOS, WhatsApp Desktop (zalogowany), uprawnienie Dostępności dla Terminala.
Tylko biblioteka standardowa Pythona.
"""
import json
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8765
DRY_RUN = "--dry-run" in sys.argv
NO_BROWSER = "--no-browser" in sys.argv
PAD_LINES = 40          # puste linie przed wynikiem: chowają go pod „Czytaj więcej”
AFTER_SEND_PAUSE = 2.0  # pauza po wysłaniu jednej wiadomości (s)

rng = secrets.SystemRandom()
LOCK = threading.Lock()
STATE = {
    "participants": None,   # [{"name":..., "phone":...}]
    "assignment": None,     # {indeks_dającego: indeks_obdarowanego}  — tylko w pamięci
    "event": "",
    "own_phone": "",
    "job": {"state": "idle", "sent": 0, "total": 0, "errors": [], "message": ""},
}


# ---------------------------------------------------------------- logika ----
def normalize_phone(raw: str) -> str:
    d = re.sub(r"\D", "", raw or "")
    if d.startswith("00"):
        d = d[2:]
    if len(d) == 9:            # polski numer bez kierunkowego
        d = "48" + d
    if not 10 <= len(d) <= 15:
        raise ValueError(f"Nieprawidłowy numer: {raw!r}")
    return d


def parse_participants(text: str):
    people, seen_names, seen_phones = [], set(), set()
    for no, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"[;,\t]", line, maxsplit=1)
        if len(parts) != 2 or not parts[0].strip():
            raise ValueError(f"Linia {no}: oczekiwano „Imię, numer”")
        name, phone = parts[0].strip(), normalize_phone(parts[1])
        if name.lower() in seen_names:
            raise ValueError(f"Linia {no}: powtórzone imię „{name}” (dodaj np. inicjał nazwiska)")
        if phone in seen_phones:
            raise ValueError(f"Linia {no}: powtórzony numer {phone}")
        seen_names.add(name.lower())
        seen_phones.add(phone)
        people.append({"name": name, "phone": phone})
    if len(people) < 3:
        raise ValueError("Potrzeba co najmniej 3 osób (przy 2 każdy zna wynik).")
    return people


def draw(n: int, chain: bool) -> dict:
    """Zwraca {dający: obdarowany}. Bijekcja bez punktów stałych."""
    idx = list(range(n))
    if chain:  # jeden cykl: losowa kolejność, każdy daje następnemu
        rng.shuffle(idx)
        return {idx[i]: idx[(i + 1) % n] for i in range(n)}
    while True:  # losowe nieporządki metodą odrzucania (rozkład jednostajny)
        perm = idx[:]
        rng.shuffle(perm)
        if all(perm[i] != i for i in range(n)):
            return {i: perm[i] for i in range(n)}


def build_message(event: str, giver: str, receiver: str) -> str:
    head = (
        f"🎁 {event or 'Losowanie prezentów'}\n"
        f"Cześć {giver}! Ta wiadomość jest tylko dla Ciebie.\n"
        "Kliknij „Czytaj więcej” i przewiń na sam dół ⬇️"
    )
    pad = "\n".join(["·"] * PAD_LINES)
    return f"{head}\n{pad}\nWylosowana osoba: *{receiver}* 🎉\n\nNikomu nie mów 🤫"


# -------------------------------------------------------- wysyłka (macOS) ----
class SendError(Exception):
    pass


def _osa(script: str):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        err = r.stderr.strip()
        if "1002" in err or "not allowed" in err.lower() or "nie ma uprawnień" in err.lower():
            raise SendError("Brak uprawnienia Dostępności dla Terminala (Ustawienia → Prywatność i ochrona → Dostępność).")
        raise SendError("Błąd AppleScript: " + err[:200])


def open_chat(phone, text):
    q = {"phone": phone}
    if text is not None:
        q["text"] = text
    url = "whatsapp://send?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)
    # Celowo nie używamy check=True: wyjątek zawierałby URL z treścią wiadomości.
    r = subprocess.run(["open", url], capture_output=True, timeout=15)
    if r.returncode != 0:
        raise SendError("Nie udało się otworzyć WhatsApp (czy aplikacja jest zainstalowana?).")


def send_one(phone: str, text: str, load_delay: float):
    if DRY_RUN:
        print(f"[dry-run] wysyłka do {phone}")
        time.sleep(0.3)
        return
    open_chat(phone, text)
    time.sleep(load_delay)
    _osa('tell application "WhatsApp" to activate')
    time.sleep(0.5)
    _osa('tell application "System Events" to key code 36')  # Enter = wyślij
    time.sleep(AFTER_SEND_PAUSE)


def finish_screen(own_phone: str, load_delay: float):
    """Po wysyłce: przejdź do neutralnego czatu (własnego), schowaj WhatsApp, zagraj dźwięk."""
    if DRY_RUN:
        print("[dry-run] koniec wysyłki")
        return
    try:
        if own_phone:
            open_chat(own_phone, None)
            time.sleep(load_delay)
        _osa('tell application "System Events" to set visible of application process "WhatsApp" to false')
    except SendError:
        pass
    for _ in range(2):
        subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], capture_output=True)


def per_message_seconds(load_delay: float) -> float:
    return load_delay + 0.5 + AFTER_SEND_PAUSE + 0.5


def run_job(targets, start_delay, load_delay):
    job = STATE["job"]
    try:
        time.sleep(start_delay)
        with LOCK:
            job["state"] = "sending"
        for giver in targets:
            people, a = STATE["participants"], STATE["assignment"]
            if a is None:
                break
            text = build_message(STATE["event"], people[giver]["name"], people[a[giver]]["name"])
            try:
                send_one(people[giver]["phone"], text, load_delay)
                with LOCK:
                    job["sent"] += 1
            except SendError as e:
                with LOCK:
                    job["errors"].append({"index": giver, "name": people[giver]["name"], "error": str(e)})
                if "Dostępności" in str(e):
                    break
            finally:
                text = None
    finally:
        finish_screen(STATE["own_phone"], load_delay)
        with LOCK:
            job["state"] = "done"


# ------------------------------------------------------------- serwer HTTP --
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # żadnych logów
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/status":
            with LOCK:
                p = STATE["participants"]
                self._json(200, {
                    "drawn": STATE["assignment"] is not None,
                    "names": [x["name"] for x in p] if p else [],
                    "event": STATE["event"],
                    "dryRun": DRY_RUN,
                    "job": STATE["job"],
                })
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        # prosta ochrona przed żądaniami z innych stron
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"):
            return self._json(403, {"error": "forbidden"})
        try:
            data = self._body()
            route = {
                "/api/draw": self.api_draw,
                "/api/send": self.api_send,
                "/api/test": self.api_test,
                "/api/reset": self.api_reset,
            }.get(self.path)
            if not route:
                return self._json(404, {"error": "not found"})
            route(data)
        except ValueError as e:
            self._json(400, {"error": str(e)})

    def _busy(self):
        return STATE["job"]["state"] in ("countdown", "sending")

    def api_draw(self, d):
        with LOCK:
            if STATE["assignment"] is not None:
                raise ValueError("Losowanie już się odbyło. Kliknij „Zakończ”, aby zacząć od nowa.")
            people = parse_participants(d.get("participants", ""))
            STATE["participants"] = people
            STATE["event"] = (d.get("event") or "").strip()[:80]
            STATE["own_phone"] = normalize_phone(d["ownPhone"]) if (d.get("ownPhone") or "").strip() else ""
            STATE["assignment"] = draw(len(people), bool(d.get("chain", True)))
            STATE["job"] = {"state": "idle", "sent": 0, "total": 0, "errors": [], "message": ""}
        self._json(200, {"ok": True, "count": len(people)})

    def api_send(self, d):
        with LOCK:
            if STATE["assignment"] is None:
                raise ValueError("Najpierw wykonaj losowanie.")
            if self._busy():
                raise ValueError("Wysyłka już trwa.")
            n = len(STATE["participants"])
            only = d.get("only")
            targets = [int(only)] if only is not None else list(range(n))
            if any(not 0 <= t < n for t in targets):
                raise ValueError("Nieprawidłowy uczestnik.")
            start_delay = max(10.0, min(60.0, float(d.get("startDelay", 15))))
            load_delay = max(2.0, min(15.0, float(d.get("loadDelay", 4))))
            est = start_delay + len(targets) * per_message_seconds(load_delay) + \
                (load_delay if STATE["own_phone"] else 0) + 5
            STATE["job"] = {"state": "countdown", "sent": 0, "total": len(targets),
                            "errors": [], "startedAt": time.time(),
                            "startsIn": start_delay, "estimate": round(est)}
        threading.Thread(target=run_job, args=(targets, start_delay, load_delay), daemon=True).start()
        self._json(200, {"ok": True, "startsIn": start_delay, "estimate": round(est)})

    def api_test(self, d):
        if self._busy():
            raise ValueError("Trwa wysyłka.")
        phone = normalize_phone(d.get("phone", ""))
        load_delay = max(2.0, min(15.0, float(d.get("loadDelay", 4))))
        try:
            send_one(phone, "✅ Test automatu losowania – działa.\n" + "\n".join(["·"] * PAD_LINES)
                     + "\nTu będzie wynik (sprawdź, czy był schowany pod „Czytaj więcej”).", load_delay)
        except SendError as e:
            raise ValueError(str(e))
        self._json(200, {"ok": True})

    def api_reset(self, d):
        with LOCK:
            if self._busy():
                raise ValueError("Trwa wysyłka.")
            STATE.update(participants=None, assignment=None, event="", own_phone="")
            STATE["job"] = {"state": "idle", "sent": 0, "total": 0, "errors": [], "message": ""}
        self._json(200, {"ok": True})


# ------------------------------------------------------------------ strona --
PAGE = r"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8">
<title>Losowanie prezentów → WhatsApp</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1f;--mut:#6e6e73;--acc:#1f8f5f;--warn:#b3261e;--line:#e3e1dc}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#222120;--ink:#f2f1ee;--mut:#a3a19c;--line:#3a3936;--acc:#3cc48a;--warn:#ff8a80}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
main{max-width:720px;margin:32px auto;padding:0 20px}
h1{font-size:24px;margin:0 0 4px}p.sub{color:var(--mut);margin:0 0 24px}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;margin-bottom:16px}
h2{font-size:16px;margin:0 0 12px}
label{display:block;font-weight:600;margin:12px 0 4px}
input,textarea{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:9px;background:transparent;color:inherit;font:inherit}
textarea{min-height:170px;font-family:ui-monospace,Menlo,monospace;font-size:13px}
.row{display:flex;gap:12px;flex-wrap:wrap}.row>div{flex:1;min-width:160px}
.chk{display:flex;gap:8px;align-items:center;font-weight:400;margin-top:14px}.chk input{width:auto}
button{font:inherit;font-weight:600;padding:10px 16px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:inherit;cursor:pointer}
button.pri{background:var(--acc);border-color:var(--acc);color:#fff}button.danger{color:var(--warn)}
button:disabled{opacity:.45;cursor:default}
.hint{color:var(--mut);font-size:13px}.err{color:var(--warn);font-weight:600;margin-top:8px}
.ok{color:var(--acc);font-weight:600}
ul.people{list-style:none;padding:0;margin:8px 0}ul.people li{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--line)}
ul.people button{padding:4px 10px;font-size:13px}
.badge{font-size:12px;padding:2px 8px;border-radius:99px;background:#fff3cd;color:#7a5b00}
#overlay{position:fixed;inset:0;background:rgba(0,0,0,.88);color:#fff;display:none;align-items:center;justify-content:center;text-align:center;z-index:9;padding:24px}
#overlay .box{max-width:560px}#overlay h2{font-size:28px;margin-bottom:12px}
#overlay .big{font-size:96px;font-weight:700;line-height:1;margin:16px 0}
#overlay .ret{font-size:22px}#overlay button{margin:8px}
</style></head><body><main>
<h1>🎁 Losowanie prezentów</h1>
<p class="sub">Wyniki nie pojawiają się nigdzie na ekranie. Każdy dostaje przez WhatsApp tylko swój wynik.</p>
<div id="dry" class="badge" style="display:none;margin-bottom:12px">TRYB PRÓBNY: nic nie jest wysyłane</div>

<section id="setup">
  <h2>1. Uczestnicy</h2>
  <label for="event">Nazwa wydarzenia (opcjonalnie)</label>
  <input id="event" placeholder="np. Wigilia 2026 u Kowalskich">
  <label for="list">Lista: jedna osoba w linii, „Imię, numer”</label>
  <textarea id="list" placeholder="Anna, 600 100 200&#10;Bartek, +48 601 200 300&#10;Celina, 0049 151 2345678"></textarea>
  <div class="hint">Numer bez kierunkowego = Polska (+48). Imiona muszą być różne.</div>
  <div class="row">
    <div><label for="own">Twój numer (do testu i neutralnego czatu na koniec)</label><input id="own" placeholder="opcjonalnie"></div>
  </div>
  <label class="chk"><input type="checkbox" id="chain" checked> Jeden łańcuch (A→B→C→…→A, bez zamkniętych par)</label>
  <div class="err" id="e1"></div>
  <p><button class="pri" id="btnDraw">Losuj</button></p>
</section>

<section id="drawn" style="display:none">
  <h2>2. Wysyłka</h2>
  <p class="ok" id="drawnInfo"></p>
  <div class="row">
    <div><label for="startDelay">Opóźnienie startu (s)</label><input id="startDelay" type="number" min="10" max="60" value="15"></div>
    <div><label for="loadDelay">Czas na otwarcie czatu (s)</label><input id="loadDelay" type="number" min="2" max="15" value="4"></div>
  </div>
  <div class="hint">Zanim wyślesz do wszystkich, kliknij „Test”: zobaczysz na swoim numerze, czy automat działa i jak wygląda schowany wynik.</div>
  <div class="err" id="e2"></div>
  <p>
    <button id="btnTest">Test na mój numer</button>
    <button class="pri" id="btnSend">Wyślij wszystkim</button>
  </p>
  <div id="result"></div>
  <ul class="people" id="people"></ul>
  <p><button class="danger" id="btnReset">Zakończ i usuń wyniki z pamięci</button></p>
</section>
</main>

<div id="overlay"><div class="box" id="ovBox"></div></div>

<script>
const $ = id => document.getElementById(id);
const LS = "losowanie.form";
try { const s = JSON.parse(localStorage.getItem(LS) || "{}");
  ["event","list","own"].forEach(k => { if (s[k]) $(k).value = s[k]; }); } catch(e) {}
function saveForm(){ try{ localStorage.setItem(LS, JSON.stringify({event:$("event").value,list:$("list").value,own:$("own").value})); }catch(e){} }

async function api(path, body){
  const r = await fetch(path, body===undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const j = await r.json(); if (!r.ok) throw new Error(j.error || "Błąd"); return j;
}
const hhmmss = d => d.toLocaleTimeString("pl-PL",{hour:"2-digit",minute:"2-digit",second:"2-digit"});
let names = [], polling = null;

async function refresh(){
  const s = await api("/api/status");
  $("dry").style.display = s.dryRun ? "inline-block" : "none";
  names = s.names;
  $("setup").style.display = s.drawn ? "none" : "block";
  $("drawn").style.display = s.drawn ? "block" : "none";
  if (s.drawn) {
    $("drawnInfo").textContent = `✔ Losowanie wykonane dla ${names.length} osób. Wynik jest tylko w pamięci programu.`;
    renderPeople(s.job);
  }
  return s;
}
function renderPeople(job){
  const failed = new Set((job.errors||[]).map(e => e.index));
  const done = job.state === "done";
  $("people").innerHTML = names.map((n,i) =>
    `<li><span>${esc(n)} ${failed.has(i) ? '<span class="badge">nie wysłano</span>' : ''}</span>
     <button data-i="${i}" ${done || job.state==="idle" ? "" : "disabled"}>Wyślij ponownie</button></li>`).join("");
  $("people").querySelectorAll("button").forEach(b => b.onclick = () => confirmSend(+b.dataset.i));
  if (done) {
    const e = job.errors || [];
    $("result").innerHTML = e.length
      ? `<p class="err">Wysłano ${job.sent}/${job.total}. Problemy: ${e.map(x=>esc(x.name)+" ("+esc(x.error)+")").join("; ")}</p>`
      : `<p class="ok">Wysłano ${job.sent}/${job.total}.</p>`;
  }
}
const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

$("btnDraw").onclick = async () => {
  $("e1").textContent = ""; saveForm();
  try { await api("/api/draw", {participants:$("list").value, event:$("event").value, ownPhone:$("own").value, chain:$("chain").checked}); await refresh(); }
  catch(e){ $("e1").textContent = e.message; }
};
$("btnTest").onclick = async () => {
  $("e2").textContent = "";
  if (!$("own").value.trim()) { $("e2").textContent = "Wpisz swój numer w sekcji 1 (Zakończ → popraw) albo pomiń test."; return; }
  try { $("btnTest").disabled = true; await api("/api/test", {phone:$("own").value, loadDelay:+$("loadDelay").value}); $("e2").innerHTML = '<span class="ok">Test wysłany, sprawdź swój czat w WhatsApp.</span>'; }
  catch(e){ $("e2").textContent = e.message; } finally { $("btnTest").disabled = false; }
};
$("btnSend").onclick = () => confirmSend(null);
$("btnReset").onclick = () => {
  showOverlay(`<h2>Zakończyć?</h2><p>Wyniki zostaną trwale usunięte z pamięci. Nie da się już nikomu wysłać ponownie.</p>
    <button id="ovNo">Anuluj</button><button class="pri" id="ovYes">Zakończ</button>`);
  $("ovNo").onclick = hideOverlay;
  $("ovYes").onclick = async () => { try{ await api("/api/reset", {}); }catch(e){} hideOverlay(); $("result").innerHTML=""; refresh(); };
};

function estimate(count){
  const sd = Math.max(10, +$("startDelay").value||15), ld = Math.max(2, +$("loadDelay").value||4);
  return Math.round(sd + count*(ld+3) + ($("own").value.trim()?ld:0) + 5);
}
function confirmSend(only){
  const count = only===null ? names.length : 1;
  const est = estimate(count), back = new Date(Date.now() + est*1000);
  const who = only===null ? `do ${count} osób` : `do: ${esc(names[only])}`;
  showOverlay(`<h2>⚠️ Za chwilę wysyłka ${who}</h2>
    <p>Gdy klikniesz „Start”, <b>odwróć się od ekranu</b>. Przez ${Math.max(10,+$("startDelay").value||15)} s nic się nie dzieje,
    potem WhatsApp sam otworzy czaty i wyśle wiadomości. Wyniki będą wtedy widoczne na ekranie.</p>
    <p class="ret">Wróć ok. <b>${hhmmss(back)}</b> (za ~${est} s)<br>albo gdy usłyszysz <b>dwa dźwięki</b>.</p>
    <p><button id="ovNo">Anuluj</button><button class="pri" id="ovYes">Rozumiem, start</button></p>`);
  $("ovNo").onclick = hideOverlay;
  $("ovYes").onclick = async () => {
    try {
      const r = await api("/api/send", {only, startDelay:+$("startDelay").value, loadDelay:+$("loadDelay").value});
      runCountdown(r.startsIn, r.estimate);
    } catch(e){ hideOverlay(); $("e2").textContent = e.message; }
  };
}
function runCountdown(startsIn, est){
  const t0 = Date.now(), back = new Date(t0 + est*1000);
  clearInterval(polling);
  const tick = async () => {
    const left = Math.ceil(startsIn - (Date.now()-t0)/1000);
    let s; try { s = await api("/api/status"); } catch(e) { return; }
    if (s.job.state === "done") {
      clearInterval(polling);
      showOverlay(`<h2>✅ Gotowe, możesz wrócić</h2><p>Wysłano ${s.job.sent}/${s.job.total}.
        ${s.job.errors.length ? "Część wiadomości nie wyszła, szczegóły poniżej." : ""}</p>
        <p class="hint" style="color:#ccc">Nie otwieraj czatów z uczestnikami: wynik jest w wysłanych wiadomościach (schowany pod „Czytaj więcej”).</p>
        <button class="pri" id="ovOk">OK</button>`);
      $("ovOk").onclick = hideOverlay; refresh(); return;
    }
    const phase = s.job.state === "countdown" ? `Start za<div class="big">${Math.max(0,left)}</div>` : `Wysyłanie… ${s.job.sent}/${s.job.total}<div class="big">📤</div>`;
    showOverlay(`<h2>🙈 Nie patrz na ekran</h2>${phase}<p class="ret">Wróć ok. <b>${hhmmss(back)}</b> albo po dwóch dźwiękach.</p>`);
  };
  tick(); polling = setInterval(tick, 1000);
}
function showOverlay(html){ $("ovBox").innerHTML = html; $("overlay").style.display = "flex"; }
function hideOverlay(){ $("overlay").style.display = "none"; }
refresh().then(s => { if (["countdown","sending"].includes(s.job.state)) runCountdown(0, 30); });
</script></body></html>
"""


def main():
    if sys.platform != "darwin" and not DRY_RUN:
        sys.exit("Ten program wysyła przez WhatsApp Desktop na macOS. Na innym systemie uruchom z --dry-run.")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Losowanie działa: {url}  (Ctrl+C kończy i usuwa wyniki z pamięci)")
    if DRY_RUN:
        print("TRYB PRÓBNY: nic nie zostanie wysłane.")
    if not NO_BROWSER:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nZamknięto. Wyniki usunięte z pamięci.")


if __name__ == "__main__":
    main()
