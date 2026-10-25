"""Original gold/dark three-pane Tk shell built around existing Python services."""
from __future__ import annotations

import json
import math
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
from datetime import datetime, timedelta, timezone

BG, PANEL, GOLD, FG, DIM, BORDER = "#100e0a", "#19150e", "#edb94e", "#f4e9cf", "#b9aa88", "#584728"

ADVANCED = {"Brain settings": "/api/memory/owner", "Employees": "/api/employees",
    "Positions": "/api/positions", "Projects": "/api/projects", "Tasks": "/api/tasks",
    "Workflows": "/api/local/workflows", "Providers": "/api/providers", "Agents": "/api/agents",
    "Software inventory": "/api/local/software", "Backup": "/api/local/backup/preview",
    "Privacy and capabilities": "/api/capabilities/grants/policy", "Emergency stop": "/api/local/emergency-stop"}


class NativeShell:
    def __init__(self, root, session):
        self.root, self.session = root, session
        self.events = queue.Queue(); self.tabs = {}; self.next_id = 0
        self.stop_flag = threading.Event(); self.busy = False; self.sidebar_visible = True
        self.model_catalog = []; self.graph = []; self.advanced = {}; self.pending_confirm = None
        root.title("ERSELMETZ AI"); root.geometry("1360x820"); root.minsize(800, 580); root.configure(bg=BG)
        style = ttk.Style(root); style.theme_use("clam")
        style.configure("TNotebook", background=PANEL, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=FG, padding=(12, 7))
        style.map("TNotebook.Tab", background=[("selected", BORDER)])
        style.configure("TCombobox", fieldbackground=PANEL, foreground=FG, background=BORDER)
        style.map("TCombobox", fieldbackground=[("readonly",PANEL)],foreground=[("readonly",FG)])
        top = tk.Frame(root, bg=PANEL); top.pack(fill="x")
        self.button(top, "☰", self.toggle_sidebar).pack(side="left", padx=6, pady=5)
        tk.Label(top, text="ERSELMETZ AI", bg=PANEL, fg=GOLD, font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(top, text="Ctrl+B sidebar · Ctrl+N new chat", bg=PANEL, fg=DIM).pack(side="right", padx=12)
        self.status = tk.StringVar(value="Starting local workspace…")
        tk.Label(root, textvariable=self.status, bg=BORDER, fg=FG, anchor="w").pack(side="bottom", fill="x")
        self.panes = tk.PanedWindow(root, orient="horizontal", bg=BORDER, sashwidth=6, bd=0, opaqueresize=True)
        self.panes.pack(fill="both", expand=True)
        self.left, self.center, self.right = [tk.Frame(self.panes, bg=PANEL) for _ in range(3)]
        self.panes.add(self.left, minsize=180, width=230, stretch="never")
        self.panes.add(self.center, minsize=200, stretch="always")
        self.panes.add(self.right, minsize=300, width=510, stretch="always")
        self.build_sidebar(); self.build_center(); self.build_chat()
        root.bind("<Control-b>", lambda _e: self.toggle_sidebar())
        root.bind("<Control-n>", lambda _e: self.new_chat())
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.new_chat(); self.root.after(40, self.pump)
        self.background(self.load_models); self.background(self.load_brain)

    @staticmethod
    def button(parent, text, command):
        return tk.Button(parent, text=text, command=command, bg=PANEL, fg=FG,
            activebackground=BORDER, activeforeground=GOLD, relief="flat", padx=10, pady=6, cursor="hand2")

    def label(self, parent, text):
        tk.Label(parent, text=text, bg=PANEL, fg=GOLD, anchor="w", font=("Segoe UI", 10, "bold")).pack(fill="x", padx=12, pady=(12, 4))

    def build_sidebar(self):
        self.label(self.left, "MY BRAIN")
        for text, command in [("Feed file", self.feed_file), ("Feed folder", self.feed_folder), ("Add note", self.add_note)]:
            self.button(self.left, text, command).pack(fill="x", padx=8)
        self.label(self.left, "MODEL · LOCAL OLLAMA")
        self.model = tk.StringVar(); self.model_picker = ttk.Combobox(self.left, textvariable=self.model, state="readonly", width=18)
        self.model_picker.pack(fill="x", padx=12); self.model_picker.bind("<<ComboboxSelected>>", self.choose_model)
        self.button(self.left, "Refresh installed models", lambda: self.background(self.load_models)).pack(fill="x", padx=8)
        self.label(self.left, "AGENT SETTINGS")
        self.steps = tk.IntVar(value=8)
        tk.Scale(self.left, from_=1, to=20, variable=self.steps, orient="horizontal", label="Max steps",
            bg=PANEL, fg=FG, highlightthickness=0, troughcolor=BORDER).pack(fill="x", padx=10)
        self.ask_first = tk.BooleanVar(value=True); self.thinking = tk.BooleanVar(value=False)
        for text, variable in [("Ask before every tool", self.ask_first), ("Show model thinking", self.thinking)]:
            tk.Checkbutton(self.left, text=text, variable=variable, bg=PANEL, fg=FG, selectcolor=BG,
                           activebackground=PANEL, activeforeground=FG).pack(anchor="w", padx=8)
        self.label(self.left, "ADVANCED")
        menu = tk.Menubutton(self.left, text="Open Advanced window ▾", bg=PANEL, fg=FG, relief="flat")
        choices = tk.Menu(menu, tearoff=False, bg=PANEL, fg=FG)
        for title in ADVANCED: choices.add_command(label=title, command=lambda t=title: self.open_advanced(t))
        menu.configure(menu=choices); menu.pack(fill="x", padx=8)
        self.label(self.left, "COMING LATER")
        tk.Label(self.left, text="Optional local voice and vision\nShown only when available", justify="left", bg=PANEL, fg=DIM).pack(padx=12, anchor="w")

    def build_center(self):
        split = tk.PanedWindow(self.center, orient="vertical", bg=BORDER, sashwidth=5, bd=0)
        split.pack(fill="both", expand=True)
        visual = tk.Frame(split, bg=BG); log = tk.Frame(split, bg=BG)
        split.add(visual, minsize=160, stretch="always"); split.add(log, minsize=120, height=240, stretch="never")
        self.canvas = tk.Canvas(visual, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True); self.canvas.bind("<Configure>", lambda _e: self.draw_brain())
        self.canvas.bind("<Button-1>", self.inspect_node)
        tk.Label(log, text="THINKING / OBSERVED STEPS", bg=BG, fg=GOLD, anchor="w").pack(fill="x", padx=10, pady=5)
        self.log = tk.Text(log, bg=BG, fg=DIM, wrap="word", relief="flat", font=("Consolas", 10), state="disabled")
        self.log.pack(fill="both", expand=True)

    def build_chat(self):
        bar = tk.Frame(self.right, bg=PANEL); bar.pack(fill="x")
        self.button(bar, "+ New chat", self.new_chat).pack(side="right")
        self.notebook = ttk.Notebook(self.right); self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.tab_changed)
        self.confirm_frame = tk.Frame(self.right, bg=BORDER)
        self.composer = tk.Frame(self.right, bg=PANEL); self.composer.pack(fill="x", padx=8, pady=8)
        self.input = tk.Text(self.composer, width=20, height=3, bg=BG, fg=FG, insertbackground=GOLD, wrap="word", relief="flat")
        self.input.pack(side="left", fill="x", expand=True)
        self.input.bind("<Return>", self.enter)
        self.send_button = self.button(self.composer, "Send", self.send); self.send_button.pack(side="left")
        self.stop_button = self.button(self.composer, "Stop", self.stop); self.stop_button.pack(side="left")

    def current(self):
        return self.tabs.get(self.notebook.select())

    def new_chat(self):
        if self.busy: return
        self.next_id += 1
        frame = tk.Frame(self.notebook, bg=BG)
        box = tk.Text(frame, bg=BG, fg=FG, wrap="word", relief="flat", padx=14, pady=14,
                      font=("Segoe UI", 11), state="disabled")
        box.pack(fill="both", expand=True)
        self.notebook.add(frame, text=f"Chat {self.next_id}")
        self.tabs[str(frame)] = {"text": box, "model": self.model.get(), "workspace": None, "conversation": None}
        self.notebook.select(frame)

    def tab_changed(self, _event=None):
        tab = self.current()
        if tab: self.model.set(tab["model"])

    def choose_model(self, _event=None):
        if self.busy: return
        tab = self.current()
        if tab and tab["model"] != self.model.get():
            # Preserve immutable assignments: start a new tab on model changes after a turn.
            if tab["conversation"]: self.new_chat()
            else: tab["model"] = self.model.get()

    @staticmethod
    def append(box, text):
        box.configure(state="normal"); box.insert("end", text); box.see("end"); box.configure(state="disabled")

    def enter(self, event):
        if event.state & 1: return None
        self.send(); return "break"

    def send(self):
        if self.busy: return
        text = self.input.get("1.0", "end-1c").strip(); tab = self.current()
        if not text or not tab: return
        if not tab["model"]:
            self.append(tab["text"], "Install a local chat model in Ollama, then click Refresh installed models.\n"); return
        self.input.delete("1.0", "end"); self.append(tab["text"], f"You\n{text}\n\nERSELMETZ AI\n")
        self.busy = True; self.stop_flag.clear(); self.status.set(f"Local · {tab['model']} · working")
        def work():
            try:
                if not tab["conversation"]:
                    tab["workspace"], tab["conversation"] = self.session.new_chat(tab["model"])
                self.session.send(tab["workspace"], tab["conversation"], text, self.stop_flag,
                                  lambda event: self.events.put(("chat", (tab, event))))
            except Exception as error: self.events.put(("error", str(error)))
            finally: self.events.put(("done", tab))
        threading.Thread(target=work, daemon=True).start()

    def stop(self):
        self.stop_flag.set()
        if self.pending_confirm: self.pending_confirm(False)
        self.status.set("Stop requested; no action will be replayed.")

    def toggle_sidebar(self):
        if self.sidebar_visible: self.panes.forget(self.left)
        else: self.panes.add(self.left, before=self.center, minsize=180, width=230, stretch="never")
        self.sidebar_visible = not self.sidebar_visible
        self.root.after_idle(lambda: self.panes.sash_place(0 if not self.sidebar_visible else 1,
            (self.panes.winfo_width() // 2) if not self.sidebar_visible else (230 + (self.panes.winfo_width()-230)//2), 0))

    def background(self, fn):
        def work():
            try: fn()
            except Exception as error: self.events.put(("error", str(error)))
        threading.Thread(target=work, daemon=True).start()

    def load_models(self):
        self.events.put(("models", self.session.models()))

    def load_brain(self):
        self.events.put(("brain", self.session.request("GET", "/api/memory/brain/graph")))

    def draw_brain(self):
        self.canvas.delete("all"); self.positions = {}
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height(); x, y = w/2, h/2
        radius = max(20, min(w,h)*.36)
        # Original rings are a static frame, never fake knowledge or fake model activity.
        for scale in [1, .92, .38]:
            r=radius*scale; self.canvas.create_oval(x-r,y-r,x+r,y+r,outline=BORDER, width=1)
        self.canvas.create_text(x,y-radius-20,text="BRAIN",fill=GOLD,font=("Segoe UI",12,"bold"))
        nodes=[n for n in self.graph if n.get("kind")=="chunk"][:300]
        for i,node in enumerate(nodes):
            angle=i*2.399963; r=radius*math.sqrt((i+.5)/max(1,len(nodes)))
            px,py=x+r*math.cos(angle),y+r*math.sin(angle)
            item=self.canvas.create_oval(px-3,py-3,px+3,py+3,fill=GOLD,outline="")
            self.positions[item]=node
        self.canvas.create_text(x,y+radius+24,text=f"{len(nodes)} visible real chunks",fill=DIM)

    def inspect_node(self, event):
        item=self.canvas.find_closest(event.x,event.y); node=self.positions.get(item[0]) if item else None
        if node:
            self.background(lambda: self.events.put(("inspect", self.session.request("GET", "/api/memory/brain/node?node_id="+node["id"]))))

    def feed_file(self):
        paths=filedialog.askopenfilenames(parent=self.root, title="Feed local files")
        if paths: self.feed_paths(paths)

    def feed_folder(self):
        folder=filedialog.askdirectory(parent=self.root, title="Feed local folder")
        if folder: self.feed_paths([folder])

    def feed_paths(self, paths):
        from pathlib import Path
        chosen=[]
        for raw in paths:
            path=Path(raw)
            if path.is_dir():
                for item in path.rglob("*"):
                    if any(part in {".git","node_modules",".venv","__pycache__","build","dist"} for part in item.relative_to(path).parts): continue
                    if item.is_file() and not item.is_symlink(): chosen.append(item)
                    if len(chosen)>=25: break
            elif path.is_file(): chosen.append(path)
        if not chosen: return
        self.confirm(f"Feed {len(chosen)} selected local files into your private Brain for 30 days?",lambda approved:
                     self.background(lambda:self.ingest_files(chosen)) if approved else None)

    def ingest_files(self, paths):
        from app.knowledge.intake import extract_upload, MAX_UPLOAD_BYTES
        for path in paths:
            if self.stop_flag.is_set(): break
            try:
                if path.stat().st_size>MAX_UPLOAD_BYTES: raise ValueError("Existing intake limit: 1 MiB")
                content,_=extract_upload(path.name,path.read_bytes())
                self.session.request("POST","/api/memory/owner",{"content":content,"source_name":path.name,
                    "expires_at":(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(),"retention_opt_in":True})
                self.events.put(("log",f"Brain write: {path.name} saved locally."))
            except Exception as error: self.events.put(("log",f"{path.name}: {error}"))
        self.load_brain()

    def add_note(self):
        content=simpledialog.askstring("Add note", "Text to retain locally (30 days):", parent=self.root)
        if not content: return
        self.confirm("Save this note locally for 30 days?", lambda approved: self.background(lambda: self.save_note(content)) if approved else None)

    def save_note(self, content):
        self.session.request("POST", "/api/memory/owner", {"content": content,"source_name":"Owner note",
            "expires_at":(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(),"retention_opt_in":True})
        self.events.put(("log", "Brain write: saved owner note with explicit retention consent.")); self.load_brain()

    def confirm(self, text, callback):
        for child in self.confirm_frame.winfo_children(): child.destroy()
        self.confirm_frame.pack(before=self.composer,fill="x",padx=8,pady=6)
        tk.Label(self.confirm_frame,text=text,bg=BORDER,fg=FG,wraplength=420,justify="left").pack(fill="x",padx=10,pady=8)
        def finish(approved):
            self.pending_confirm=None; self.confirm_frame.pack_forget(); callback(approved)
        self.pending_confirm=finish
        self.button(self.confirm_frame,"Allow once",lambda:finish(True)).pack(side="left")
        self.button(self.confirm_frame,"Deny",lambda:finish(False)).pack(side="left")

    def open_advanced(self, title):
        existing=self.advanced.get(title)
        if existing and existing.winfo_exists(): existing.lift(); return
        win=tk.Toplevel(self.root); win.title("Advanced · "+title); win.geometry("780x550"); win.configure(bg=BG)
        self.advanced[title]=win
        tk.Label(win,text=title,bg=BG,fg=GOLD,font=("Segoe UI",16)).pack(anchor="w",padx=12,pady=12)
        box=tk.Text(win,bg=PANEL,fg=FG,wrap="word"); box.pack(fill="both",expand=True,padx=12,pady=8)
        editor=tk.Frame(win,bg=BG); editor.pack(fill="x",padx=12)
        tk.Label(editor,text="Existing API operation · authorization and approvals still apply",bg=BG,fg=DIM).pack(anchor="w")
        operation=tk.StringVar(value="GET "+ADVANCED[title])
        selector=ttk.Combobox(editor,textvariable=operation,state="readonly"); selector.pack(fill="x")
        path=tk.Entry(editor,bg=PANEL,fg=FG,insertbackground=GOLD); path.insert(0,ADVANCED[title]); path.pack(fill="x",pady=4)
        payload=tk.Text(editor,height=3,bg=PANEL,fg=FG,insertbackground=GOLD); payload.insert("1.0","{}"); payload.pack(fill="x")
        def pick(_event=None): path.delete(0,"end"); path.insert(0,operation.get().split(" ",1)[1])
        selector.bind("<<ComboboxSelected>>",pick)
        def execute():
            method=operation.get().split(" ",1)[0]; target=path.get()
            try: data=json.loads(payload.get("1.0","end-1c")) if method!="GET" else None
            except ValueError: self.status.set("Enter a valid JSON body."); return
            def run(approved=True):
                if not approved: return
                def work():
                    try: result=self.session.request(method,target,data); text=json.dumps(result,indent=2,default=str)
                    except Exception as error: text=str(error)
                    self.events.put(("advanced",(box,text)))
                self.background(work)
            if method=="GET": run()
            else: self.confirm(f"Run {method} {target}?\n{json.dumps(data,ensure_ascii=False)[:1800]}",run)
        self.button(editor,"Run selected operation",execute).pack(anchor="w")
        try:
            schema=self.session.request("GET","/openapi.json"); word=ADVANCED[title].split("/")[2]
            operations=[f"{method.upper()} {route}" for route,methods in schema.get("paths",{}).items()
                        if route.startswith("/api/") and (word in route or title=="Privacy and capabilities")
                        for method in methods if method in {"get","post","put","patch","delete"}]
            selector.configure(values=operations or [operation.get()])
        except Exception: pass
        def refresh():
            def work():
                try: result=self.session.request("GET",ADVANCED[title]); text=json.dumps(result,indent=2,default=str)
                except Exception as error: text=str(error)
                self.events.put(("advanced",(box,text)))
            self.background(work)
        self.button(win,"Refresh",refresh).pack(anchor="w",padx=12); refresh()

    def pump(self):
        try:
            for _ in range(100):
                kind,value=self.events.get_nowait()
                if kind=="models":
                    self.model_catalog=value; names=[item["name"] for item in value]
                    self.model_picker.configure(values=names)
                    if not self.model.get() and names:
                        self.model.set(names[0]); self.current()["model"]=names[0]
                    self.status.set("Local Ollama ready" if names else "No installed local chat model. Open Ollama and refresh.")
                elif kind=="brain": self.graph=value.get("nodes",[]); self.draw_brain()
                elif kind=="chat":
                    tab,event=value
                    if event.get("type")=="chunk": self.append(tab["text"],event.get("text",event.get("content","")))
                    elif event.get("type")=="complete": self.append(self.log,"Reply completed.\n")
                    elif event.get("type")=="error": self.append(tab["text"],"\n"+str(event.get("message","Reply failed")))
                elif kind=="done": self.busy=False; self.append(value["text"],"\n\n"); self.status.set("Stopped" if self.stop_flag.is_set() else "Ready · local only")
                elif kind=="advanced":
                    box,text=value
                    if box.winfo_exists(): box.delete("1.0","end"); box.insert("end",text)
                elif kind=="inspect": self.append(self.log,json.dumps(value,default=str)+"\n")
                else: self.status.set(str(value)[:200]); self.append(self.log,str(value)+"\n")
        except queue.Empty: pass
        self.root.after(40,self.pump)

    def close(self):
        self.stop(); self.root.destroy()
