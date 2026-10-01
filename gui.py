#!/usr/bin/env python3
"""Involeap desktop app: drop WhatsApp export zips, press Run, review drafts."""
import json, os, queue, shutil, subprocess, sys, threading, tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import involeap as P
from PIL import Image, ImageTk

ENV = P.ROOT / ".env"
FIELDS = [("title", "Title"), ("organizer", "Organizer"), ("deadline", "Deadline (YYYY-MM-DD)"), ("start_at", "Start date"),
          ("location", "Location"), ("cost", "Cost"), ("eligibility", "Eligibility")]


def read_env():
    d = {}
    if ENV.exists():
        for l in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in l and not l.strip().startswith("#"):
                k, v = l.split("=", 1)
                d[k.strip()] = v.strip().strip('"')
    return d


def write_env(d):
    ENV.write_text("\n".join(f"{k}={v}" for k, v in d.items()) + "\n", encoding="utf-8")


def open_folder(path):
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Involeap – Daily Pipeline")
        self.geometry("1080x720")
        self.minsize(900, 600)
        self.q, self.worker, self.items, self.sel, self.photo = queue.Queue(), None, [], None, None
        P.log = lambda m: self.q.put(("log", m))
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.run_tab, self.rev_tab, self.set_tab = ttk.Frame(nb), ttk.Frame(nb), ttk.Frame(nb)
        nb.add(self.run_tab, text="  1. Run  ")
        nb.add(self.rev_tab, text="  2. Review  ")
        nb.add(self.set_tab, text="  3. Settings  ")
        nb.bind("<<NotebookTabChanged>>", lambda e: self.refresh_items() if nb.index("current") == 1 else None)
        self.build_run(); self.build_review(); self.build_settings()
        self.refresh_inbox()
        if not read_env().get("GEMINI_API_KEY"):
            nb.select(self.set_tab)
        self.after(150, self.pump)

    # ───────────── Run tab ─────────────
    def build_run(self):
        f = self.run_tab
        top = ttk.Frame(f); top.pack(fill="x", padx=10, pady=10)
        ttk.Label(top, text="Daily steps:  ① In WhatsApp export each group (with media)   ② Add the .zip files here   ③ Press Run",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        row = ttk.Frame(f); row.pack(fill="x", padx=10)
        ttk.Button(row, text="➕ Add export files…", command=self.add_zips).pack(side="left")
        ttk.Button(row, text="Open inbox folder", command=lambda: (P.INBOX.mkdir(exist_ok=True), open_folder(P.INBOX))).pack(side="left", padx=6)
        self.inbox_lbl = ttk.Label(row, text=""); self.inbox_lbl.pack(side="left", padx=10)
        opt = ttk.Frame(f); opt.pack(fill="x", padx=10, pady=8)
        self.mock, self.links, self.push = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar(value=True)
        ttk.Checkbutton(opt, text="Test mode (no AI, for trying the app)", variable=self.mock).pack(side="left")
        ttk.Checkbutton(opt, text="Check that links open", variable=self.links).pack(side="left", padx=12)
        ttk.Checkbutton(opt, text="Send to admin dashboard (Supabase)", variable=self.push).pack(side="left")
        ttk.Label(opt, text="Ignore messages older than").pack(side="left", padx=(16, 4))
        self.days = tk.IntVar(value=14)
        ttk.Spinbox(opt, from_=1, to=90, width=4, textvariable=self.days).pack(side="left")
        ttk.Label(opt, text="days").pack(side="left", padx=3)
        btn = ttk.Frame(f); btn.pack(fill="x", padx=10, pady=4)
        self.run_btn = ttk.Button(btn, text="▶  Run", command=self.start); self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(btn, text="■ Stop", command=lambda: P.STOP.update(flag=True), state="disabled"); self.stop_btn.pack(side="left", padx=6)
        self.bar = ttk.Progressbar(btn, mode="indeterminate", length=180); self.bar.pack(side="left", padx=10)
        self.summary = ttk.Label(f, text="", font=("TkDefaultFont", 10, "bold")); self.summary.pack(anchor="w", padx=10, pady=4)
        self.logbox = tk.Text(f, height=18, state="disabled", wrap="word", bg="#fafafa")
        self.logbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def refresh_inbox(self):
        n = len(list(P.INBOX.glob("*.zip"))) if P.INBOX.exists() else 0
        self.inbox_lbl.config(text=f"{n} file(s) waiting in inbox")

    def add_zips(self):
        files = filedialog.askopenfilenames(title="Select WhatsApp export .zip files", filetypes=[("WhatsApp export", "*.zip")])
        P.INBOX.mkdir(exist_ok=True)
        for f in files:
            shutil.copy(f, P.INBOX / Path(f).name)
        self.refresh_inbox()

    def log(self, m):
        self.logbox.config(state="normal"); self.logbox.insert("end", m + "\n"); self.logbox.see("end"); self.logbox.config(state="disabled")

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        if not self.mock.get() and not read_env().get("GEMINI_API_KEY"):
            return messagebox.showwarning("Missing key", "Add your free Gemini API key in the Settings tab (or tick Test mode).")
        self.refresh_inbox()
        self.run_btn.config(state="disabled"); self.stop_btn.config(state="normal"); self.bar.start(12); self.summary.config(text="Running…")

        opts = (self.mock.get(), self.days.get(), None, not self.push.get(), self.links.get())  # read Tk vars on the main thread

        def job():
            try:
                self.q.put(("done", P.run(*opts)))
            except Exception as e:
                self.q.put(("fail", str(e)))
        self.worker = threading.Thread(target=job, daemon=True); self.worker.start()

    def pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.log(val)
                else:
                    self.bar.stop(); self.run_btn.config(state="normal"); self.stop_btn.config(state="disabled"); self.refresh_inbox()
                    if kind == "fail":
                        self.summary.config(text="Failed"); self.log("ERROR: " + val); messagebox.showerror("Could not run", val)
                    else:
                        r = val
                        self.summary.config(text=f"Done: {r['new_items']} new, {r['merged']} merged into existing, {r['pending']} pending, "
                                                 f"{len(r['errors'])} error(s). Dashboard push: {r['push']}")
                        self.log(json.dumps(r, indent=2))
        except queue.Empty:
            pass
        self.after(150, self.pump)

    # ───────────── Review tab ─────────────
    def build_review(self):
        f = self.rev_tab
        bar = ttk.Frame(f); bar.pack(fill="x", padx=10, pady=8)
        ttk.Label(bar, text="Show:").pack(side="left")
        self.filter = tk.StringVar(value="needs_review")
        c = ttk.Combobox(bar, textvariable=self.filter, values=["all", "needs_review", "approved", "rejected"], width=14, state="readonly")
        c.pack(side="left", padx=6); c.bind("<<ComboboxSelected>>", lambda e: self.refresh_items())
        ttk.Button(bar, text="Refresh", command=self.refresh_items).pack(side="left")
        ttk.Button(bar, text="Export approved to JSON…", command=self.export).pack(side="right")
        pan = ttk.PanedWindow(f, orient="horizontal"); pan.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        left = ttk.Frame(pan); pan.add(left, weight=2)
        cols = ("type", "title", "deadline", "flags", "status")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for col, w in zip(cols, (80, 260, 90, 170, 90)):
            self.tree.heading(col, text=col.capitalize()); self.tree.column(col, width=w, anchor="w")
        self.tree.tag_configure("warn", background="#fff4d6")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        right = ttk.Frame(pan); pan.add(right, weight=3)
        self.ent = {}
        form = ttk.Frame(right); form.pack(fill="x")
        for i, (k, label) in enumerate(FIELDS):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=2)
            self.ent[k] = ttk.Entry(form, width=52); self.ent[k].grid(row=i, column=1, sticky="we", padx=6)
        form.columnconfigure(1, weight=1)
        ttk.Label(right, text="Links (one per line)").pack(anchor="w", pady=(6, 0))
        self.links_box = tk.Text(right, height=2); self.links_box.pack(fill="x")
        ttk.Label(right, text="Summary (article text)").pack(anchor="w", pady=(6, 0))
        self.sum_box = tk.Text(right, height=5, wrap="word"); self.sum_box.pack(fill="x")
        self.flag_lbl = ttk.Label(right, text="", foreground="#a15c00", wraplength=520, justify="left"); self.flag_lbl.pack(anchor="w", pady=4)
        ttk.Label(right, text="Original messages + poster").pack(anchor="w")
        act = ttk.Frame(right); act.pack(side="bottom", fill="x", pady=6)  # packed first so it is never pushed off-screen
        low = ttk.Frame(right); low.pack(fill="both", expand=True)
        self.img_lbl = ttk.Label(low, width=26); self.img_lbl.pack(side="right", padx=6, anchor="n")
        self.src_box = tk.Text(low, height=6, width=30, wrap="word", bg="#fafafa", state="disabled"); self.src_box.pack(side="left", fill="both", expand=True)
        ttk.Button(act, text="💾 Save edits", command=lambda: self.save(None)).pack(side="left")
        ttk.Button(act, text="✅ Approve", command=lambda: self.save("approved")).pack(side="left", padx=6)
        ttk.Button(act, text="❌ Reject", command=lambda: self.save("rejected")).pack(side="left")

    def refresh_items(self):
        flt = self.filter.get()
        self.items = [i for i in P.list_items() if flt == "all" or i["status"] == flt]
        self.tree.delete(*self.tree.get_children())
        for n, i in enumerate(self.items):
            d = i["data"]
            fl = ", ".join(i["flags"]) if i["flags"] else ""
            self.tree.insert("", "end", iid=str(n), values=(i["type"], d.get("title", "")[:70], d.get("deadline") or "—", fl[:40], i["status"]),
                             tags=("warn",) if [x for x in i["flags"] if x != "mock_extractor"] else ())
        self.sel = None

    def on_select(self, _):
        s = self.tree.selection()
        if not s:
            return
        self.sel = self.items[int(s[0])]
        d = self.sel["data"]
        for k, _l in FIELDS:
            self.ent[k].delete(0, "end"); self.ent[k].insert(0, d.get(k) or "")
        self.links_box.delete("1.0", "end"); self.links_box.insert("1.0", "\n".join(d.get("links") or []))
        self.sum_box.delete("1.0", "end"); self.sum_box.insert("1.0", d.get("summary") or "")
        extra = []
        if d.get("missing_fields"): extra.append("Missing: " + ", ".join(d["missing_fields"]))
        if d.get("conflicts"): extra.append("Conflicts: " + json.dumps(d["conflicts"], ensure_ascii=False))
        if self.sel["dup_of"]: extra.append("Possible duplicate of another item – check before approving.")
        self.flag_lbl.config(text="⚠ " + " | ".join(self.sel["flags"] + extra) if (self.sel["flags"] or extra) else "")
        rows = P.item_messages(self.sel["sources"])
        self.src_box.config(state="normal"); self.src_box.delete("1.0", "end")
        for grp, ts, text in rows:
            self.src_box.insert("end", f"[{grp} · {ts[:16]}]\n{text}\n\n")
        self.src_box.config(state="disabled")
        self.photo = None; self.img_lbl.config(image="")
        for p in self.sel["attachments"]:
            if p.endswith(".webp") and Path(p).exists():
                im = Image.open(p); im.thumbnail((200, 260)); self.photo = ImageTk.PhotoImage(im); self.img_lbl.config(image=self.photo); break

    def save(self, status):
        if not self.sel:
            return
        d = dict(self.sel["data"])
        for k, _l in FIELDS:
            d[k] = self.ent[k].get().strip() or None
        d["links"] = [l.strip() for l in self.links_box.get("1.0", "end").splitlines() if l.strip()]
        d["summary"] = self.sum_box.get("1.0", "end").strip()
        if status == "approved":
            miss = [n for k, n in (("title", "title"), ("summary", "summary")) if not d.get(k)]
            if not d["links"] and not self.sel["sources"]: miss.append("link or source")
            if d.get("type") == "opportunity" and not d.get("deadline") and not messagebox.askyesno("No deadline", "No deadline set. Approve as 'rolling / unknown deadline'?"):
                return
            if miss:
                return messagebox.showwarning("Can't approve", "Missing: " + ", ".join(miss))
        P.update_item(self.sel["id"], d, status)
        self.refresh_items()

    def export(self):
        ok = [dict(i["data"], id=i["id"], type=i["type"]) for i in P.list_items() if i["status"] == "approved"]
        if not ok:
            return messagebox.showinfo("Nothing to export", "No approved items yet.")
        f = filedialog.asksaveasfilename(defaultextension=".json", initialfile="approved_items.json", filetypes=[("JSON", "*.json")])
        if f:
            Path(f).write_text(json.dumps(ok, ensure_ascii=False, indent=2), encoding="utf-8")
            messagebox.showinfo("Exported", f"{len(ok)} item(s) saved.")

    # ───────────── Settings tab ─────────────
    def build_settings(self):
        f, env = self.set_tab, read_env()
        self.vars = {}
        rows = [("GEMINI_API_KEY", "Gemini API key (free at aistudio.google.com)", True),
                ("GEMINI_MODEL", "Gemini model name", False), ("MAX_LLM_CALLS", "Max AI calls per run", False),
                ("SUPABASE_URL", "Supabase URL (optional)", False), ("SUPABASE_SERVICE_KEY", "Supabase service key (optional, keep secret)", True),
                ("SUPABASE_BUCKET", "Supabase poster bucket", False)]
        defaults = {"GEMINI_MODEL": "gemini-2.5-flash", "MAX_LLM_CALLS": "40", "SUPABASE_BUCKET": "posters"}
        g = ttk.Frame(f); g.pack(fill="x", padx=14, pady=14)
        for i, (k, label, secret) in enumerate(rows):
            ttk.Label(g, text=label).grid(row=i, column=0, sticky="w", pady=5)
            v = tk.StringVar(value=env.get(k, defaults.get(k, ""))); self.vars[k] = v
            ttk.Entry(g, textvariable=v, width=60, show="•" if secret else "").grid(row=i, column=1, padx=10)
        g.columnconfigure(1, weight=1)
        b = ttk.Frame(f); b.pack(anchor="w", padx=14)
        ttk.Button(b, text="Save settings", command=self.save_settings).pack(side="left")
        ttk.Button(b, text="Test Gemini key", command=self.test_key).pack(side="left", padx=8)
        ttk.Label(f, wraplength=800, justify="left", foreground="#555", text=(
            "Privacy: phone numbers and personal Gmail/Yahoo-type emails are removed and sender names are replaced by codes BEFORE any text is sent to Gemini. "
            "The free Gemini tier may use submitted data to improve Google's models, so only announcements (not private chats) should be exported. "
            "Settings are stored in a .env file next to this app – don't share it.")).pack(anchor="w", padx=14, pady=16)

    def save_settings(self):
        write_env({k: v.get().strip() for k, v in self.vars.items()})
        messagebox.showinfo("Saved", "Settings saved.")

    def test_key(self):
        import requests
        key, model = self.vars["GEMINI_API_KEY"].get().strip(), self.vars["GEMINI_MODEL"].get().strip()
        if not key:
            return messagebox.showwarning("No key", "Paste your Gemini API key first.")
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", headers={"x-goog-api-key": key},
                              json={"contents": [{"parts": [{"text": "Reply with OK"}]}]}, timeout=30)
            if r.ok:
                messagebox.showinfo("Works", f"Key and model '{model}' work.")
            else:
                messagebox.showerror("Failed", f"{r.status_code}: {r.text[:300]}\n\nIf it's 404, the model name changed – check AI Studio.")
        except Exception as e:
            messagebox.showerror("Failed", str(e))


if __name__ == "__main__":
    App().mainloop()
