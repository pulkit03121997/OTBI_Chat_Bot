"""
Orbrick SQL Automation
Oracle Fusion BIP SQL Generator & Personal SQL Library
orbrick.com — Oracle ERP & AI Cloud Consulting

Run: python app.py  (Python 3.8+, no pip installs)
"""
import json, re, threading, tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from pathlib import Path

from sql_engine  import answer, SA_DATA, TBL_DATA, detect_intent, wants_sql
from sql_validator import validate_sql, load_catalog
from sql_library import (save_entry, delete_entry, delete_multiple, get_all,
                          bulk_import, find_relevant, search as lib_search,
                          get_stats, increment_use, analyze_sql,
                          MODULE_COLORS, CATEGORY_GROUPS)

BASE_DIR = Path(__file__).parent

# ── Orbrick Dashboard Theme — white background, professional colours ────────
BRAND = {
    # Backgrounds
    "bg":        "#f1f5f9",   # light grey — main window
    "bg2":       "#ffffff",   # white — panels, cards
    "bg3":       "#f8fafc",   # near-white — sidebar, inputs
    "bg4":       "#e2e8f0",   # light grey — hover, borders
    "bg_white":  "#ffffff",
    "bg_light":  "#f8fafc",
    # Borders
    "border":    "#e2e8f0",
    "border2":   "#cbd5e1",
    # Text
    "text":      "#1e293b",   # dark — primary text
    "text2":     "#475569",   # medium — secondary text
    "text3":     "#64748b",   # lighter — labels, hints
    "text_dark": "#1e293b",
    # Orbrick orange accent
    "accent":    "#f97316",   # orange primary
    "accent2":   "#ea6c0a",   # orange darker (hover)
    "accent_lt": "#fff7ed",   # light orange background
    # Status colours
    "green":     "#16a34a",
    "yellow":    "#d97706",
    "cyan":      "#0284c7",
    "red":       "#dc2626",
    "purple":    "#7c3aed",
    # Selection
    "sel_bg":    "#f97316",
    "sel_fg":    "#ffffff",
    # SQL syntax — dark bg box (library viewer)
    "sql_kw":    "#1d4ed8",
    "sql_kw2":   "#7c3aed",
    "sql_tbl":   "#065f46",
    "sql_parm":  "#c2410c",
    "sql_str":   "#991b1b",
    "sql_cmt":   "#6b7280",
    "sql_def":   "#1e293b",
    # SQL syntax — light bg (generated SQL box)
    "lsql_kw":   "#1d4ed8",
    "lsql_kw2":  "#7c3aed",
    "lsql_tbl":  "#065f46",
    "lsql_parm": "#c2410c",
    "lsql_str":  "#991b1b",
    "lsql_cmt":  "#6b7280",
    "lsql_def":  "#1e293b",
}

# ── Safe SQL tokeniser (single capture group — never returns None) ─────────
_SPLIT = re.compile(
    r"(:[A-Z_P]\w+"           # :P_START_DATE
    r"|'[^']*'"               # 'string'
    r'|"[^"]*"'               # "alias"
    r"|\b[A-Z][A-Z0-9_]{3,}_(?:ALL|F|V|B|TL|M|VL|S|X|GT)\b"
    r")"
)
_TBL  = re.compile(r"^[A-Z][A-Z0-9_]{3,}_(?:ALL|F|V|B|TL|M|VL|S|X|GT)$")
_PARM = re.compile(r"^:[A-Z_P]\w+$")
_KW   = re.compile(r"^(SELECT|FROM|WHERE|ORDER\s+BY|GROUP\s+BY|HAVING|WITH|UNION|MINUS)\b", re.I)
_KW2  = re.compile(r"^(AND|OR)\s", re.I)


def _insert_sql(widget, line: str, light: bool = False):
    """Insert one SQL line with syntax highlighting. Safe — never crashes on None."""
    s = line.strip()
    if s.startswith("--"):
        widget.insert("end", line + "\n", "cmt")
        return
    base = "kw" if _KW.match(s) else ("kw2" if _KW2.match(s) else "def")
    for part in _SPLIT.split(line):
        if not part:
            continue
        if _TBL.match(part):
            widget.insert("end", part, "ltbl" if light else "tbl")
        elif _PARM.match(part):
            widget.insert("end", part, "lparm" if light else "parm")
        elif part[0] in ("'", '"'):
            widget.insert("end", part, "lstr" if light else "str")
        else:
            widget.insert("end", part, base)
    widget.insert("end", "\n")


def _setup_dark_tags(w):
    w.tag_configure("kw",   foreground=BRAND["sql_kw"],   font=("Consolas",10,"bold"))
    w.tag_configure("kw2",  foreground=BRAND["sql_kw2"],  font=("Consolas",10))
    w.tag_configure("tbl",  foreground=BRAND["sql_tbl"],  font=("Consolas",10,"bold"))
    w.tag_configure("parm", foreground=BRAND["sql_parm"], font=("Consolas",10,"bold"))
    w.tag_configure("str",  foreground=BRAND["sql_str"],  font=("Consolas",10))
    w.tag_configure("cmt",  foreground=BRAND["sql_cmt"],  font=("Consolas",10,"italic"))
    w.tag_configure("def",  foreground=BRAND["sql_def"],  font=("Consolas",10))


def _setup_light_tags(w):
    w.tag_configure("kw",    foreground=BRAND["lsql_kw"],   font=("Consolas",10,"bold"))
    w.tag_configure("kw2",   foreground=BRAND["lsql_kw2"],  font=("Consolas",10))
    w.tag_configure("ltbl",  foreground=BRAND["lsql_tbl"],  font=("Consolas",10,"bold"))
    w.tag_configure("lparm", foreground=BRAND["lsql_parm"], font=("Consolas",10,"bold"))
    w.tag_configure("lstr",  foreground=BRAND["lsql_str"],  font=("Consolas",10))
    w.tag_configure("cmt",   foreground=BRAND["lsql_cmt"],  font=("Consolas",10,"italic"))
    w.tag_configure("def",   foreground=BRAND["lsql_def"],  font=("Consolas",10))


def _format_sql(sql: str) -> str:
    """
    Format Oracle SQL:
    - Major keywords start at column 0
    - SELECT columns indented 4 spaces, comma at end
    - WHERE conditions: first line after WHERE, rest with AND
    - Preserves CTE (WITH ... AS) structure
    - No double AND prefixes
    """
    if not sql.strip(): return sql
    import re as _re
    KW     = _re.compile(r"^(SELECT|FROM|WHERE|ORDER\s+BY|GROUP\s+BY|HAVING|WITH|UNION\s*ALL|UNION|MINUS|INTERSECT|SET)\b", _re.I)
    ANDOR  = _re.compile(r"^(AND|OR)\s", _re.I)
    JOIN   = _re.compile(r"^(LEFT|RIGHT|INNER|OUTER|FULL|CROSS)?\s*(JOIN|OUTER\s+JOIN)\b", _re.I)
    CLAUSE = _re.compile(r"^(ON|CONNECT\s+BY|START\s+WITH|NOCYCLE|PRIOR)\b", _re.I)

    out    = []
    in_cte = False

    for raw in sql.splitlines():
        s = raw.strip()
        if not s:
            out.append("")
            continue
        # Comments preserved
        if s.startswith("--"):
            out.append(s)
            continue
        # CTE opening
        if _re.match(r"^WITH\b", s, _re.I):
            out.append(s)
            in_cte = True
            continue
        # Major SQL keyword
        if KW.match(s):
            kw   = KW.match(s).group(0).upper().replace("  ", " ")
            rest = s[KW.match(s).end():].strip()
            out.append(kw)
            if rest:
                out.append("    " + rest)
            continue
        # AND / OR
        if ANDOR.match(s):
            m2  = ANDOR.match(s)
            kw2 = m2.group(0).upper().rstrip()
            out.append("%-6s%s" % (kw2, s[m2.end():]))
            continue
        # JOIN
        if JOIN.match(s):
            out.append(s.upper() if len(s) < 20 else s)
            continue
        # ON / CONNECT BY etc.
        if CLAUSE.match(s):
            out.append("    " + s)
            continue
        # Default: indent 4 spaces
        out.append("    " + s)

    # Clean up: remove 3+ consecutive blank lines
    result = []
    blanks = 0
    for line in out:
        if line.strip() == "":
            blanks += 1
            if blanks <= 1: result.append("")
        else:
            blanks = 0
            result.append(line)
    return "\n".join(result)


# ══════════════════════════════════════════════════════════════════════════
class OrbrickApp:
# ══════════════════════════════════════════════════════════════════════════

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Orbrick SQL Automation  |  Oracle Fusion BIP SQL Generator")
        self.root.geometry("1480x920")
        self.root.configure(bg=BRAND["bg"])
        self.root.minsize(1100, 700)

        # State
        self._sa_items   = []
        self._filter_mod = tk.StringVar(value="ALL")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._refresh_sidebar())
        self._current_sa = None
        self._busy       = False

        self._lib_cat    = tk.StringVar(value="ALL")
        self._lib_mod    = tk.StringVar(value="ALL")
        self._lib_search = tk.StringVar()
        self._lib_items  = []
        self._sel_entry  = None
        self._lib_search.trace_add("write", lambda *_: self._refresh_library())
        self._lib_mod.trace_add("write",    lambda *_: self._refresh_library())
        self._lib_cat.trace_add("write",    lambda *_: self._refresh_library())

        self._build_ui()
        self._refresh_sidebar()
        self._welcome()
        self._refresh_library()

    # ══════════════════════════════════════════════════════════════════════
    # HEADER + NOTEBOOK
    # ══════════════════════════════════════════════════════════════════════
    def _build_ui(self):
        # ── Orbrick header bar ───────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=BRAND["bg2"], pady=0)
        hdr.pack(fill="x")

        # Logo area
        logo_frame = tk.Frame(hdr, bg=BRAND["accent"], padx=16, pady=10)
        logo_frame.pack(side="left")
        tk.Label(logo_frame, text="⬡", font=("Segoe UI",20,"bold"),
                 bg=BRAND["accent"], fg="white").pack(side="left")
        tk.Label(logo_frame, text=" Orbrick",
                 font=("Segoe UI",16,"bold"),
                 bg=BRAND["accent"], fg="white").pack(side="left")

        # App name
        title_frame = tk.Frame(hdr, bg=BRAND["bg2"], padx=16, pady=0)
        title_frame.pack(side="left", fill="y")
        tk.Frame(title_frame, bg=BRAND["bg2"], height=4).pack()
        tk.Label(title_frame, text="SQL Automation",
                 font=("Segoe UI",14,"bold"),
                 bg=BRAND["bg2"], fg=BRAND["text"]).pack(anchor="w")
        tk.Label(title_frame,
                 text=f"Oracle Fusion BIP Generator  ·  {len(SA_DATA)} Subject Areas  ·  {len(TBL_DATA)} Tables  ·  100% Offline",
                 font=("Segoe UI",8),
                 bg=BRAND["bg2"], fg=BRAND["text3"]).pack(anchor="w")

        # Right side stats/info
        right_hdr = tk.Frame(hdr, bg=BRAND["bg2"], padx=16)
        right_hdr.pack(side="right", fill="y", pady=8)
        tk.Label(right_hdr, text="orbrick.com",
                 font=("Segoe UI",8,"bold"), bg=BRAND["bg2"],
                 fg=BRAND["accent"]).pack(anchor="e")
        tk.Label(right_hdr, text="Oracle ERP & AI Cloud Consulting",
                 font=("Segoe UI",8), bg=BRAND["bg2"],
                 fg=BRAND["text3"]).pack(anchor="e")

        # Orange accent line
        tk.Frame(self.root, bg=BRAND["accent"], height=3).pack(fill="x")

        # ── Notebook ────────────────────────────────────────────────────
        sty = ttk.Style()
        sty.theme_use("clam")
        sty.configure("Orb.TNotebook",
                       background="#f1f5f9", borderwidth=0, tabmargins=[0,0,0,0])
        sty.configure("Orb.TNotebook.Tab",
                       background="#e2e8f0", foreground="#475569",
                       padding=[22,9], font=("Segoe UI",10), borderwidth=0)
        sty.map("Orb.TNotebook.Tab",
                background=[("selected", BRAND["accent"])],
                foreground=[("selected", "white")])

        nb = ttk.Notebook(self.root, style="Orb.TNotebook")
        nb.pack(fill="both", expand=True)

        t1 = tk.Frame(nb, bg=BRAND["bg"])
        t2 = tk.Frame(nb, bg=BRAND["bg"])
        t3 = tk.Frame(nb, bg=BRAND["bg"])
        nb.add(t1, text="  🔍  SQL Generator  ")
        nb.add(t2, text="  📚  My SQL Library  ")
        nb.add(t3, text="  🗄️  Table Catalog  ")
        self._build_generator(t1)
        self._build_library(t2)
        self._build_table_catalog(t3)

    # ══════════════════════════════════════════════════════════════════════
    # SQL GENERATOR TAB
    # ══════════════════════════════════════════════════════════════════════
    def _build_generator(self, p):
        # Filter toolbar
        tb = tk.Frame(p, bg=BRAND["bg2"], pady=7, padx=14)
        tb.pack(fill="x")
        tk.Label(tb, text="MODULE:", bg=BRAND["bg2"], fg=BRAND["text3"],
                 font=("Segoe UI",8,"bold")).pack(side="left")
        for m in ["ALL","ERP/SCM","HCM","CX"]:
            tk.Radiobutton(tb, text=m, variable=self._filter_mod, value=m,
                           bg=BRAND["bg2"], fg=BRAND["text2"],
                           selectcolor=BRAND["bg4"],
                           activebackground=BRAND["bg2"],
                           activeforeground=BRAND["text"],
                           font=("Segoe UI",9),
                           command=self._refresh_sidebar).pack(side="left", padx=5)
        tk.Label(tb, text="   SEARCH:", bg=BRAND["bg2"], fg=BRAND["text3"],
                 font=("Segoe UI",8,"bold")).pack(side="left", padx=(10,3))
        se = tk.Entry(tb, textvariable=self._search_var,
                      bg=BRAND["bg4"], fg=BRAND["text"],
                      insertbackground=BRAND["text"],
                      relief="flat", font=("Segoe UI",10), width=26)
        se.pack(side="left", ipady=4)
        tk.Button(tb, text="✕", bg=BRAND["bg4"], fg=BRAND["text3"],
                  relief="flat", cursor="hand2", font=("Segoe UI",9),
                  command=lambda: self._search_var.set("")).pack(side="left", padx=2)
        tk.Frame(p, bg=BRAND["border"], height=1).pack(fill="x")

        pw = tk.PanedWindow(p, orient="horizontal",
                            bg=BRAND["bg"], sashwidth=5, bd=0,
                            sashrelief="flat")
        pw.pack(fill="both", expand=True)

        # ── LEFT: Subject area list ──────────────────────────────────────
        lf = tk.Frame(pw, bg=BRAND["bg3"], width=262)
        pw.add(lf, minsize=190)

        sa_hdr = tk.Frame(lf, bg=BRAND["bg4"], pady=7, padx=10)
        sa_hdr.pack(fill="x")
        tk.Label(sa_hdr, text="SUBJECT AREAS", font=("Segoe UI",8,"bold"),
                 bg=BRAND["bg4"], fg=BRAND["accent"]).pack(side="left")
        self._sa_cnt = tk.Label(sa_hdr, text="", font=("Segoe UI",8),
                                 bg=BRAND["bg4"], fg=BRAND["text3"])
        self._sa_cnt.pack(side="right")

        sf = tk.Frame(lf, bg=BRAND["bg3"]); sf.pack(fill="both", expand=True)
        self._sa_lb = tk.Listbox(
            sf, bg=BRAND["bg3"], fg=BRAND["text2"],
            selectbackground=BRAND["accent"],
            selectforeground="white",
            relief="flat", activestyle="none",
            font=("Segoe UI",9), bd=0, highlightthickness=0)
        sb = tk.Scrollbar(sf, orient="vertical", command=self._sa_lb.yview,
                          bg=BRAND["bg3"], troughcolor=BRAND["bg3"], width=6)
        self._sa_lb.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._sa_lb.pack(fill="both", expand=True, padx=2)
        self._sa_lb.bind("<<ListboxSelect>>", self._on_sa_click)

        # ── MIDDLE: Chat area ────────────────────────────────────────────
        mid = tk.Frame(pw, bg=BRAND["bg"]); pw.add(mid, minsize=420)

        self._out = scrolledtext.ScrolledText(
            mid, bg="#ffffff", fg=BRAND["text"],
            insertbackground=BRAND["text"],
            relief="flat", font=("Consolas",10), wrap="word",
            state="disabled", bd=0, highlightthickness=0, padx=16, pady=12)
        self._out.pack(fill="both", expand=True, padx=6, pady=(6,2))
        self._setup_out_tags()

        # Quick chip buttons
        qf = tk.Frame(mid, bg=BRAND["bg"]); qf.pack(fill="x", padx=6, pady=(3,3))
        CHIPS = [
            ("AR Customer Invoice", "AR customer transaction SQL"),
            ("AP Invoice + Payment","Generate SQL for AP invoice and AP payment with supplier"),
            ("GL Journal + SLA",    "Generate SQL for GL journal with SLA subledger"),
            ("AR Adjustment",       "Generate SQL for AR adjustment"),
            ("PO with Lines",       "Generate SQL for purchase order with lines"),
            ("Employee Salary",     "Generate SQL for employee salary"),
            ("Bank Statement",      "Generate SQL for bank statement"),
        ]
        for lbl, q in CHIPS:
            b = tk.Button(qf, text=lbl,
                          bg=BRAND["bg3"], fg=BRAND["text2"],
                          activebackground=BRAND["bg4"],
                          activeforeground=BRAND["text"],
                          relief="flat", font=("Segoe UI",8), cursor="hand2",
                          padx=8, pady=3,
                          command=lambda q2=q: self._ask(q2))
            b.pack(side="left", padx=2)

        # Input area
        inp_outer = tk.Frame(mid, bg=BRAND["bg2"], pady=8)
        inp_outer.pack(fill="x", padx=6, pady=(2,4))
        self._inp = tk.Text(
            inp_outer, bg="#f8fafc", fg="#1e293b",
            insertbackground=BRAND["text"],
            relief="flat", font=("Segoe UI",10), height=2, wrap="word",
            bd=0, highlightthickness=2,
            highlightbackground=BRAND["border"],
            highlightcolor=BRAND["accent"],
            padx=10, pady=7)
        self._inp.pack(side="left", fill="x", expand=True, padx=(8,0))
        self._inp.bind("<Return>",       self._on_enter)
        self._inp.bind("<Shift-Return>", lambda e: None)
        ask_btn = tk.Button(
            inp_outer, text="Generate SQL",
            bg=BRAND["accent"], fg="white",
            activebackground=BRAND["accent2"], activeforeground="white",
            relief="flat", font=("Segoe UI",10,"bold"), cursor="hand2",
            padx=14, pady=6, command=self._ask)
        ask_btn.pack(side="right", padx=8, fill="y")
        tk.Label(mid, text="Enter = generate  ·  Shift+Enter = new line  ·  Automatically checks SQL Library",
                 bg=BRAND["bg"], fg=BRAND["text3"],
                 font=("Segoe UI",8)).pack()

        # ── RIGHT: Table info ────────────────────────────────────────────
        ri = tk.Frame(pw, bg=BRAND["bg3"], width=262); pw.add(ri, minsize=185)
        ri_hdr = tk.Frame(ri, bg=BRAND["bg4"], pady=7, padx=10); ri_hdr.pack(fill="x")
        tk.Label(ri_hdr, text="TABLE DETAILS", font=("Segoe UI",8,"bold"),
                 bg=BRAND["bg4"], fg=BRAND["accent"]).pack(side="left")
        self._info = scrolledtext.ScrolledText(
            ri, bg="#ffffff", fg="#475569",
            relief="flat", font=("Consolas",9), wrap="word",
            state="disabled", bd=0, highlightthickness=0, padx=10, pady=10)
        self._info.pack(fill="both", expand=True)
        self._setup_info_tags()
        self._info_hint()


    # ══════════════════════════════════════════════════════════════════════
    # TABLE CATALOG TAB
    # ══════════════════════════════════════════════════════════════════════
    def _build_table_catalog(self, p):
        self._tc_search = tk.StringVar()
        self._tc_mod    = tk.StringVar(value="ALL")
        self._tc_items  = []

        top = tk.Frame(p, bg=BRAND["bg2"], pady=8, padx=14); top.pack(fill="x")
        self._tc_stats = tk.Label(top, text="", font=("Segoe UI",9),
                                   bg=BRAND["bg2"], fg=BRAND["text3"])
        self._tc_stats.pack(side="left")
        tk.Button(top, text=" + Add Table ",
                  bg=BRAND["bg3"], fg=BRAND["green"],
                  activebackground=BRAND["bg4"], relief="flat",
                  font=("Segoe UI",9,"bold"), cursor="hand2", padx=8, pady=4,
                  command=self._tc_add_table).pack(side="right", padx=3)
        tk.Button(top, text=" 🌐 Import from Oracle Docs ",
                  bg=BRAND["bg3"], fg=BRAND["yellow"],
                  activebackground=BRAND["bg4"], relief="flat",
                  font=("Segoe UI",9,"bold"), cursor="hand2", padx=8, pady=4,
                  command=self._import_oracle_url).pack(side="right", padx=3)
        tk.Frame(p, bg=BRAND["accent"], height=2).pack(fill="x")

        # Module filter + Search
        fb = tk.Frame(p, bg=BRAND["bg2"], pady=6, padx=14); fb.pack(fill="x")
        tk.Label(fb, text="MODULE:", bg=BRAND["bg2"], fg=BRAND["text3"],
                 font=("Segoe UI",8,"bold")).pack(side="left")
        for m, c in [("ALL","#94a3b8"),("GL","#34d399"),("AP","#60a5fa"),("AR","#f472b6"),
                      ("HCM","#a78bfa"),("PO","#fb923c"),("FA","#fbbf24"),
                      ("CE","#06b6d4"),("SLA","#818cf8")]:
            tk.Radiobutton(fb, text=m, variable=self._tc_mod, value=m,
                           bg=BRAND["bg2"], fg=c, selectcolor=BRAND["bg4"],
                           activebackground=BRAND["bg2"], font=("Segoe UI",8),
                           command=self._tc_refresh).pack(side="left", padx=3)
        tk.Label(fb, text="  Search:", bg=BRAND["bg2"], fg=BRAND["text3"],
                 font=("Segoe UI",8,"bold")).pack(side="left", padx=(12,3))
        self._tc_search.trace_add("write", lambda *_: self._tc_refresh())
        tk.Entry(fb, textvariable=self._tc_search,
                 bg=BRAND["bg4"], fg=BRAND["text"], insertbackground=BRAND["text"],
                 relief="flat", font=("Segoe UI",10), width=22).pack(side="left", ipady=3)
        tk.Button(fb, text="✕", bg=BRAND["bg4"], fg=BRAND["text3"],
                  relief="flat", cursor="hand2", font=("Segoe UI",9),
                  command=lambda: self._tc_search.set("")).pack(side="left", padx=2)
        tk.Frame(p, bg=BRAND["border"], height=1).pack(fill="x")

        pw = tk.PanedWindow(p, orient="horizontal", bg=BRAND["bg"], sashwidth=5, bd=0)
        pw.pack(fill="both", expand=True)

        # Left list
        lp = tk.Frame(pw, bg=BRAND["bg3"], width=290); pw.add(lp, minsize=210)
        lhdr = tk.Frame(lp, bg=BRAND["bg4"], pady=6, padx=10); lhdr.pack(fill="x")
        tk.Label(lhdr, text="ORACLE FUSION TABLES", font=("Segoe UI",8,"bold"),
                 bg=BRAND["bg4"], fg=BRAND["accent"]).pack(side="left")
        self._tc_cnt = tk.Label(lhdr, text="", font=("Segoe UI",8),
                                 bg=BRAND["bg4"], fg=BRAND["text3"])
        self._tc_cnt.pack(side="right")
        lf = tk.Frame(lp, bg=BRAND["bg3"]); lf.pack(fill="both", expand=True)
        self._tc_lb = tk.Listbox(lf, bg="#ffffff", fg="#1e293b",
                                  selectbackground=BRAND["accent"],
                                  selectforeground="white",
                                  relief="flat", activestyle="none",
                                  font=("Consolas",9), bd=0, highlightthickness=0)
        sb = tk.Scrollbar(lf, orient="vertical", command=self._tc_lb.yview,
                          bg=BRAND["bg3"], troughcolor=BRAND["bg3"], width=6)
        self._tc_lb.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self._tc_lb.pack(fill="both", expand=True, padx=2)
        self._tc_lb.bind("<<ListboxSelect>>", self._tc_select)

        # Right detail
        dp = tk.Frame(pw, bg=BRAND["bg"]); pw.add(dp, minsize=500)
        dhdr = tk.Frame(dp, bg=BRAND["bg2"], pady=8, padx=14); dhdr.pack(fill="x")
        self._tc_title = tk.Label(dhdr, text="← Select a table",
                                   font=("Segoe UI",11,"bold"),
                                   bg=BRAND["bg2"], fg=BRAND["text"], anchor="w")
        self._tc_title.pack(side="left", fill="x", expand=True)
        tk.Frame(dp, bg=BRAND["accent"], height=2).pack(fill="x")
        self._tc_detail = scrolledtext.ScrolledText(
            dp, bg="#ffffff", fg="#475569",
            relief="flat", font=("Consolas",9), wrap="word",
            state="disabled", bd=0, highlightthickness=0, padx=14, pady=10)
        self._tc_detail.pack(fill="both", expand=True)
        # Tags for detail view
        self._tc_detail.tag_configure("tbl",  foreground="#f97316",  font=("Consolas",11,"bold"))
        self._tc_detail.tag_configure("sec",  foreground="#0284c7",  font=("Segoe UI",8,"bold"))
        self._tc_detail.tag_configure("desc", foreground="#475569",  font=("Segoe UI",9,"italic"))
        self._tc_detail.tag_configure("col",  foreground="#065f46",  font=("Consolas",9,"bold"))
        self._tc_detail.tag_configure("typ",  foreground="#64748b",  font=("Consolas",8))
        self._tc_detail.tag_configure("nn",   foreground="#d97706",  font=("Consolas",8,"bold"))
        self._tc_detail.tag_configure("pk",   foreground="#d97706",  font=("Consolas",8,"bold"))
        self._tc_detail.tag_configure("fk",   foreground="#0284c7",  font=("Consolas",8))
        self._tc_detail.tag_configure("dim",  foreground="#64748b",  font=("Segoe UI",8))
        self._tc_detail.tag_configure("sep",  foreground="#e2e8f0")
        self._tc_refresh()

    def _tc_refresh(self):
        from sql_validator import load_catalog
        cat = load_catalog()
        q   = self._tc_search.get().strip().lower()
        mod = self._tc_mod.get()
        items = []
        for tbl, info in cat.items():
            if mod != "ALL" and info.get("module","") != mod: continue
            if q and q not in tbl.lower() and q not in info.get("description","").lower():
                if not any(q in c.lower() for c in info.get("columns",{})): continue
            items.append((tbl, info))
        items.sort(key=lambda x: x[0])
        self._tc_items = items
        self._tc_lb.delete(0,"end")
        ICONS = {"GL":"📊","AP":"💰","AR":"📥","HCM":"👤","PO":"🛒","FA":"🏗","CE":"🏦","SLA":"🔗"}
        for tbl, info in items:
            icon = ICONS.get(info.get("module",""),"📄")
            ncols = len(info.get("columns",{}))
            self._tc_lb.insert("end", f"  {icon}  {tbl}  ({ncols} cols)")
        total = len(cat)
        self._tc_cnt.config(text=f"{len(items)}/{total}")
        total_cols = sum(len(i.get("columns",{})) for i in cat.values())
        self._tc_stats.config(
            text=f"🗄 {total} tables  ·  {total_cols} total columns  ·  Oracle Fusion verified")

    def _tc_select(self, _e=None):
        sel = self._tc_lb.curselection()
        if not sel or sel[0] >= len(self._tc_items):
            return
        tbl_name, info = self._tc_items[sel[0]]
        mod  = info.get("module","?")
        cat  = info.get("category","")
        ncol = len(info.get("columns",{}))
        self._tc_title.config(
            text="%s   [%s]  %s  %d columns" % (tbl_name, mod, cat, ncol))
        d = self._tc_detail
        d.config(state="normal")
        d.delete("1.0","end")

        # Table name + description
        d.insert("end", tbl_name, "tbl")
        d.insert("end", "\n")
        desc = info.get("description","")
        if desc:
            d.insert("end", desc, "desc")
            d.insert("end", "\n\n")

        # Module/schema
        d.insert("end", "MODULE / SCHEMA / CATEGORY\n", "sec")
        meta_str = ("  Module: %s  |  Schema: %s  |  Category: %s\n\n"
                    % (mod, info.get("schema","?"), cat))
        d.insert("end", meta_str, "dim")

        # Primary key
        pks = info.get("primary_key", [])
        if pks:
            d.insert("end", "PRIMARY KEY\n", "sec")
            d.insert("end", "  [PK] " + ", ".join(pks) + "\n\n", "pk")

        # Foreign keys
        fks = info.get("foreign_keys", [])
        if fks:
            d.insert("end", "FOREIGN KEYS (%d)\n" % len(fks), "sec")
            for fk in fks:
                cs = ", ".join(fk.get("columns", []))
                rt = fk.get("ref_table","")
                rc = ", ".join(fk.get("ref_columns", []))
                d.insert("end", "  %s  ->  %s (%s)\n" % (cs, rt, rc), "fk")
            d.insert("end", "\n")

        # Columns
        cols = info.get("columns", {})
        d.insert("end", "COLUMNS (%d)\n" % len(cols), "sec")
        hdr = ("  %-38s %-22s %-5s %s\n" % ("Column", "Type", "Null", "Description"))
        d.insert("end", hdr, "sec")
        d.insert("end", "  " + "-"*90 + "\n", "sep")
        for cn, ci in cols.items():
            nn  = "!" if not ci.get("nullable", True) else " "
            nns = "NO " if not ci.get("nullable", True) else "YES"
            row = ("  %s %-38s %-22s %-5s %s\n"
                   % (nn, cn, ci.get("type",""), nns, ci.get("desc","")))
            tag = "nn" if not ci.get("nullable", True) else "dim"
            d.insert("end", "  " + nn + " ", tag)
            d.insert("end", "%-38s" % cn, "col")
            d.insert("end", "%-22s" % ci.get("type",""), "typ")
            d.insert("end", "%-5s " % nns, tag)
            d.insert("end", ci.get("desc","") + "\n", "dim")
        d.config(state="disabled")

    def _tc_add_table(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Add Table to Catalog"); dlg.geometry("700x540")
        dlg.configure(bg=BRAND["bg2"]); dlg.resizable(True,True); dlg.grab_set()
        tk.Frame(dlg,bg=BRAND["accent"],height=4).pack(fill="x")
        tk.Label(dlg,text="➕  Add Oracle Fusion Table",
                 font=("Segoe UI",12,"bold"),bg=BRAND["bg2"],
                 fg=BRAND["text"],pady=10).pack(fill="x",padx=16)
        tk.Frame(dlg,bg=BRAND["border"],height=1).pack(fill="x")
        fm = tk.Frame(dlg,bg=BRAND["bg2"]); fm.pack(fill="both",expand=True,padx=16,pady=8)
        def lbl(t): tk.Label(fm,text=t,font=("Segoe UI",9,"bold"),
                              bg=BRAND["bg2"],fg=BRAND["text2"],anchor="w").pack(fill="x",pady=(6,2))
        lbl("Table Name *  (e.g. PER_ALL_PEOPLE_F)")
        tv = tk.StringVar(); te = tk.Entry(fm,textvariable=tv,bg=BRAND["bg4"],fg=BRAND["text"],
                                            insertbackground=BRAND["text"],relief="flat",
                                            font=("Segoe UI",10)); te.pack(fill="x",ipady=5)
        lbl("Module  (GL / AP / AR / HCM / PO / FA / CE / SLA)")
        mv = tk.StringVar(value="GL"); tk.Entry(fm,textvariable=mv,bg=BRAND["bg4"],fg=BRAND["text"],
                                                 insertbackground=BRAND["text"],relief="flat",
                                                 font=("Segoe UI",10),width=10).pack(anchor="w",ipady=4)
        lbl("Description")
        dv = tk.StringVar(); tk.Entry(fm,textvariable=dv,bg=BRAND["bg4"],fg=BRAND["text"],
                                       insertbackground=BRAND["text"],relief="flat",
                                       font=("Segoe UI",10)).pack(fill="x",ipady=4)
        lbl("Primary Key  (comma separated)")
        pkv = tk.StringVar(); tk.Entry(fm,textvariable=pkv,bg=BRAND["bg4"],fg=BRAND["text"],
                                        insertbackground=BRAND["text"],relief="flat",
                                        font=("Segoe UI",10)).pack(fill="x",ipady=4)
        lbl("Columns  (one per line:  COLUMN_NAME | VARCHAR2(30) | Description)")
        ct = tk.Text(fm,bg=BRAND["bg4"],fg=BRAND["text"],insertbackground=BRAND["text"],
                     relief="flat",font=("Consolas",9),height=7,padx=8,pady=5)
        ct.pack(fill="both",expand=True)
        tk.Frame(dlg,bg=BRAND["border"],height=1).pack(fill="x")
        br = tk.Frame(dlg,bg=BRAND["bg2"],pady=8); br.pack(fill="x",padx=16)
        sl = tk.Label(br,text="",bg=BRAND["bg2"],fg=BRAND["green"],font=("Segoe UI",9))
        sl.pack(side="left")
        def do_save():
            import json as _j
            tbl_name = tv.get().strip().upper()
            if not tbl_name: sl.config(text="⚠ Table name required",fg=BRAND["red"]); return
            cols = {}
            for line in ct.get("1.0","end").splitlines():
                parts = [x.strip() for x in line.split("|")]
                if parts and parts[0]:
                    cols[parts[0].upper()] = {
                        "type": parts[1] if len(parts)>1 else "VARCHAR2(240)",
                        "nullable": True,
                        "desc": parts[2] if len(parts)>2 else ""}
            cat = load_catalog()
            cat[tbl_name] = {
                "description": dv.get().strip(), "schema": mv.get().strip().upper(),
                "module": mv.get().strip().upper(), "category": "",
                "primary_key": [c.strip() for c in pkv.get().split(",") if c.strip()],
                "foreign_keys": [], "columns": cols,
            }
            from pathlib import Path
            (Path(__file__).parent/"data"/"oracle_tables.json").write_text(
                _j.dumps(cat,indent=2,ensure_ascii=False))
            sl.config(text=f"✅ Saved: {tbl_name}  ({len(cols)} cols)",fg=BRAND["green"])
            self._tc_refresh()
            self.root.after(1500,dlg.destroy)
        tk.Button(br,text=" 💾  Save ",bg=BRAND["accent"],fg="white",
                  activebackground=BRAND["accent2"],relief="flat",
                  font=("Segoe UI",10,"bold"),cursor="hand2",
                  padx=12,pady=6,command=do_save).pack(side="right",padx=4)
        tk.Button(br,text=" Cancel ",bg=BRAND["bg4"],fg=BRAND["text2"],
                  activebackground=BRAND["bg3"],relief="flat",
                  font=("Segoe UI",10),cursor="hand2",
                  padx=12,pady=6,command=dlg.destroy).pack(side="right",padx=4)
        te.focus()

    # ══════════════════════════════════════════════════════════════════════
    # SQL LIBRARY TAB
    # ══════════════════════════════════════════════════════════════════════
    def _build_library(self, p):
        # Top toolbar
        top = tk.Frame(p, bg=BRAND["bg2"], pady=8, padx=14); top.pack(fill="x")
        self._lib_stats_lbl = tk.Label(top, text="", font=("Segoe UI",9),
                                        bg=BRAND["bg2"], fg=BRAND["text3"])
        self._lib_stats_lbl.pack(side="left")

        bts = tk.Frame(top, bg=BRAND["bg2"]); bts.pack(side="right")
        def btn(parent, label, color, cmd):
            tk.Button(parent, text=label, bg=BRAND["bg3"], fg=color,
                      activebackground=BRAND["bg4"], activeforeground=BRAND["text"],
                      relief="flat", font=("Segoe UI",9,"bold"), cursor="hand2",
                      padx=9, pady=5, command=cmd).pack(side="left", padx=3)

        btn(bts, " + New SQL ",         BRAND["green"],  self._open_dialog)
        btn(bts, " 📂 Import File(s) ", BRAND["cyan"],   self._import_files)
        btn(bts, " 🌐 Oracle Docs URL ",BRAND["yellow"], self._import_oracle_url)
        self._del_multi_btn = tk.Button(
            bts, text=" 🗑 Delete Sel. ",
            bg=BRAND["bg3"], fg=BRAND["red"],
            activebackground=BRAND["bg4"], activeforeground="#fca5a5",
            relief="flat", font=("Segoe UI",9,"bold"), cursor="hand2",
            padx=9, pady=5, state="disabled", command=self._delete_multi)
        self._del_multi_btn.pack(side="left", padx=3)

        tk.Frame(p, bg=BRAND["accent"], height=2).pack(fill="x")

        # Category tabs
        cat_bar = tk.Frame(p, bg=BRAND["bg3"]); cat_bar.pack(fill="x")
        self._cat_btns = {}
        for ct, col in [("ALL","#94a3b8"),("Module","#60a5fa"),
                         ("Tech","#f97316"),("Common","#fde68a")]:
            b = tk.Button(cat_bar, text=f"  {ct}  ",
                          bg=BRAND["accent"] if ct=="ALL" else BRAND["bg3"],
                          fg="white" if ct=="ALL" else col,
                          activebackground=BRAND["bg4"], relief="flat",
                          font=("Segoe UI",9,"bold"), cursor="hand2", pady=8,
                          command=lambda c=ct: self._set_cat(c))
            b.pack(side="left"); self._cat_btns[ct] = b

        # Sub-filter + search
        sub = tk.Frame(p, bg=BRAND["bg2"], pady=6, padx=14); sub.pack(fill="x")
        self._mod_btns_frame = tk.Frame(sub, bg=BRAND["bg2"])
        self._mod_btns_frame.pack(side="left")
        srch = tk.Frame(sub, bg=BRAND["bg2"]); srch.pack(side="left", padx=(14,0))
        tk.Label(srch, text="🔍", bg=BRAND["bg2"],
                 fg=BRAND["accent"], font=("Segoe UI",11)).pack(side="left")
        self._lib_search_entry = tk.Entry(
            srch, textvariable=self._lib_search,
            bg=BRAND["bg4"], fg=BRAND["text"],
            insertbackground=BRAND["text"],
            relief="flat", font=("Segoe UI",10), width=28)
        self._lib_search_entry.pack(side="left", ipady=4, padx=(3,0))
        self._lib_search_entry.bind("<Return>", lambda e: self._refresh_library())
        tk.Label(srch, text="  title · table name · tag · SQL body",
                 bg=BRAND["bg2"], fg=BRAND["text3"],
                 font=("Segoe UI",8)).pack(side="left")
        tk.Button(srch, text="✕", bg=BRAND["bg4"], fg=BRAND["text3"],
                  relief="flat", cursor="hand2", font=("Segoe UI",9),
                  command=lambda: self._lib_search.set("")).pack(side="left", padx=2)
        tk.Frame(p, bg=BRAND["border"], height=1).pack(fill="x")

        # Paned layout
        pw2 = tk.PanedWindow(p, orient="horizontal",
                              bg=BRAND["bg"], sashwidth=5, bd=0)
        pw2.pack(fill="both", expand=True)

        # List pane
        lp = tk.Frame(pw2, bg=BRAND["bg3"], width=300); pw2.add(lp, minsize=220)
        lp_hdr = tk.Frame(lp, bg=BRAND["bg4"], pady=7, padx=10); lp_hdr.pack(fill="x")
        tk.Label(lp_hdr, text="SAVED QUERIES", font=("Segoe UI",8,"bold"),
                 bg=BRAND["bg4"], fg=BRAND["accent"]).pack(side="left")
        self._lib_cnt = tk.Label(lp_hdr, text="", font=("Segoe UI",8),
                                  bg=BRAND["bg4"], fg=BRAND["text3"])
        self._lib_cnt.pack(side="right")
        tk.Label(lp, text="Ctrl+Click = multi-select  ·  Dbl-click = copy",
                 font=("Segoe UI",7,"italic"), bg=BRAND["bg4"],
                 fg=BRAND["text3"], pady=2).pack(fill="x")
        lf2 = tk.Frame(lp, bg=BRAND["bg3"]); lf2.pack(fill="both", expand=True)
        self._lib_lb = tk.Listbox(
            lf2, bg="#ffffff", fg="#334155",
            selectbackground=BRAND["accent"], selectforeground="white",
            relief="flat", activestyle="none",
            font=("Segoe UI",10), bd=0, highlightthickness=0,
            selectmode=tk.EXTENDED)
        sb3 = tk.Scrollbar(lf2, orient="vertical", command=self._lib_lb.yview,
                           bg=BRAND["bg3"], troughcolor=BRAND["bg3"], width=6)
        self._lib_lb.config(yscrollcommand=sb3.set)
        sb3.pack(side="right", fill="y")
        self._lib_lb.pack(fill="both", expand=True, padx=2)
        self._lib_lb.bind("<<ListboxSelect>>", self._on_lib_select)
        self._lib_lb.bind("<Double-Button-1>", lambda e: self._copy_sel())

        # Detail pane
        dp = tk.Frame(pw2, bg=BRAND["bg"]); pw2.add(dp, minsize=500)

        dhdr = tk.Frame(dp, bg=BRAND["bg2"], pady=8, padx=14); dhdr.pack(fill="x")
        self._lib_title = tk.Label(
            dhdr, text="← Select a query to view",
            font=("Segoe UI",12,"bold"), bg=BRAND["bg2"],
            fg=BRAND["text"], wraplength=620, justify="left")
        self._lib_title.pack(side="left", fill="x", expand=True)
        bf = tk.Frame(dhdr, bg=BRAND["bg2"]); bf.pack(side="right")
        def action_btn(parent, text, color, cmd, key="disabled"):
            b = tk.Button(parent, text=text, bg=BRAND["bg3"], fg=color,
                          activebackground=BRAND["bg4"], activeforeground=BRAND["text"],
                          relief="flat", font=("Segoe UI",9,"bold"), cursor="hand2",
                          padx=9, pady=5, state=key, command=cmd)
            b.pack(side="left", padx=2); return b
        self._bcopy = action_btn(bf,"📋 Copy",  BRAND["cyan"],  self._copy_sel)
        self._bedit = action_btn(bf,"✏ Edit",   BRAND["yellow"],self._edit_sel)
        self._bdel  = action_btn(bf,"🗑 Delete", BRAND["red"],   self._del_sel)

        tk.Frame(dp, bg=BRAND["accent"], height=2).pack(fill="x")
        self._lib_meta = tk.Label(dp, text="", font=("Segoe UI",8),
                                   bg=BRAND["bg2"], fg=BRAND["text3"],
                                   anchor="w", padx=14, pady=5, wraplength=860)
        self._lib_meta.pack(fill="x")
        self._lib_tags_frame = tk.Frame(dp, bg=BRAND["bg2"], padx=14)
        self._lib_tags_frame.pack(fill="x", pady=(0,4))
        tk.Frame(dp, bg=BRAND["border"], height=1).pack(fill="x")

        sql_hdr = tk.Frame(dp, bg=BRAND["bg3"], pady=5, padx=14); sql_hdr.pack(fill="x")
        tk.Label(sql_hdr, text="SQL", font=("Segoe UI",8,"bold"),
                 bg=BRAND["bg3"], fg=BRAND["accent"]).pack(side="left")
        self._sql_lines_lbl = tk.Label(sql_hdr, text="", font=("Segoe UI",8),
                                        bg=BRAND["bg3"], fg=BRAND["text3"])
        self._sql_lines_lbl.pack(side="right")

        self._lib_sql = scrolledtext.ScrolledText(
            dp, bg="#ffffff", fg="#1e293b",
            insertbackground="#1e293b",
            relief="flat", font=("Consolas",10), wrap="none",
            state="disabled", bd=0, highlightthickness=0, padx=14, pady=10)
        self._lib_sql.pack(fill="both", expand=True)
        _setup_light_tags(self._lib_sql)

        self._set_cat("ALL")

    # ── Category ──────────────────────────────────────────────────────────
    def _set_cat(self, ct: str):
        self._lib_cat.set(ct)
        for name, b in self._cat_btns.items():
            if name == ct:
                b.config(bg=BRAND["accent"], fg="white")
            else:
                col = {"ALL":"#94a3b8","Module":"#60a5fa",
                        "Tech":"#f97316","Common":"#fde68a"}.get(name, BRAND["text2"])
                b.config(bg=BRAND["bg3"], fg=col)
        for w in self._mod_btns_frame.winfo_children(): w.destroy()
        self._lib_mod.set("ALL")
        mods = ["ALL"] + (CATEGORY_GROUPS.get(ct, [m for g in CATEGORY_GROUPS.values() for m in g])
                          if ct != "ALL" else [m for g in CATEGORY_GROUPS.values() for m in g])
        for m in mods:
            col = MODULE_COLORS.get(m, BRAND["text2"])
            tk.Radiobutton(
                self._mod_btns_frame, text=m,
                variable=self._lib_mod, value=m,
                bg=BRAND["bg2"], fg=col, selectcolor=BRAND["bg4"],
                activebackground=BRAND["bg2"], activeforeground=BRAND["text"],
                font=("Segoe UI",8),
                command=self._refresh_library).pack(side="left", padx=2)
        self._refresh_library()

    # ══════════════════════════════════════════════════════════════════════
    # TAG SETUP
    # ══════════════════════════════════════════════════════════════════════
    def _setup_out_tags(self):
        o = self._out
        o.tag_configure("you",    foreground=BRAND["accent"],  font=("Segoe UI",9,"bold"))
        o.tag_configure("ai",     foreground=BRAND["cyan"],    font=("Segoe UI",9,"bold"))
        o.tag_configure("sep",    foreground=BRAND["text3"])
        o.tag_configure("body",   foreground=BRAND["text"],    font=("Segoe UI",10))
        o.tag_configure("head1",  foreground=BRAND["accent"],  font=("Segoe UI",11,"bold"))
        o.tag_configure("head2",  foreground=BRAND["cyan"],    font=("Segoe UI",10,"bold"))
        o.tag_configure("sa",     foreground=BRAND["text2"],   font=("Segoe UI",10))
        o.tag_configure("tlink",  foreground=BRAND["cyan"],    font=("Consolas",10,"bold"))
        o.tag_configure("tip",    foreground=BRAND["yellow"],  font=("Segoe UI",9,"italic"))
        o.tag_configure("dim",    foreground=BRAND["text3"],   font=("Segoe UI",9))
        o.tag_configure("lib_title",foreground=BRAND["accent"],font=("Segoe UI",9,"bold"),
                         background=BRAND["bg3"])

    def _setup_info_tags(self):
        i = self._info
        i.tag_configure("title", foreground="#f97316",  font=("Segoe UI",10,"bold"))
        i.tag_configure("mod",   foreground="#f97316",  font=("Segoe UI",8,"bold"))
        i.tag_configure("sec",   foreground="#0284c7",  font=("Segoe UI",8,"bold"))
        i.tag_configure("tbl",   foreground="#0284c7",  font=("Consolas",9,"bold"), underline=True)
        i.tag_configure("col",   foreground="#065f46",  font=("Consolas",8))
        i.tag_configure("pk",    foreground="#d97706",  font=("Consolas",8,"bold"))
        i.tag_configure("sa_lnk",foreground="#475569",  font=("Segoe UI",9))
        i.tag_configure("dim",   foreground="#64748b",  font=("Segoe UI",8,"italic"))

    # ══════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ══════════════════════════════════════════════════════════════════════
    def _refresh_sidebar(self):
        q   = self._search_var.get().strip().lower()
        mod = self._filter_mod.get()
        items = []
        for sa, info in SA_DATA.items():
            if mod != "ALL" and info["module"] != mod: continue
            if q:
                if q not in sa.lower() and \
                   not any(q.upper().replace(" ","_") in t for t in info.get("tables",[])):
                    continue
            items.append((sa, info))
        items.sort(key=lambda x: x[0])
        self._sa_items = items
        self._sa_lb.delete(0, "end")
        icons = {"ERP/SCM":"[ERP]","HCM":"[HCM]","CX":" [CX]"}
        for sa, info in items:
            self._sa_lb.insert("end", f"  {icons.get(info['module'],'     ')}  {sa}")
        self._sa_cnt.config(text=f"{len(items)}")

    def _on_sa_click(self, _e=None):
        sel = self._sa_lb.curselection()
        if not sel: return
        sa, info = self._sa_items[sel[0]]
        self._current_sa = sa
        self._info_show_sa(sa, info)
        self._ask(f"Generate SQL for {sa} subject area module {info['module']}", silent=True)

    # ══════════════════════════════════════════════════════════════════════
    # INFO PANEL
    # ══════════════════════════════════════════════════════════════════════
    def _info_hint(self):
        i = self._info
        i.config(state="normal"); i.delete("1.0","end")
        i.insert("end","Click a subject area\nor search a table name\nto see column details.","dim")
        i.config(state="disabled")

    def _info_show_sa(self, sa, info):
        i = self._info; i.config(state="normal"); i.delete("1.0","end")
        i.insert("end", f"{info['module']}\n","mod")
        i.insert("end", f"{sa}\n\n","title")
        i.insert("end", f"TABLES ({len(info['tables'])})\n","sec")
        i.insert("end", "Click any table for details\n\n","dim")
        for tbl in info["tables"]:
            tag = f"t_{tbl}"
            i.insert("end", f"  {tbl}\n", tag)
            i.tag_configure(tag, foreground=BRAND["cyan"],
                             font=("Consolas",9,"underline"))
            i.tag_bind(tag,"<Button-1>", lambda e,t=tbl: self._info_show_tbl(t))
            i.tag_bind(tag,"<Enter>",    lambda e: i.config(cursor="hand2"))
            i.tag_bind(tag,"<Leave>",    lambda e: i.config(cursor=""))
        if info.get("presentation_tables"):
            i.insert("end","\nOTBI PRESENTATION TABLES\n","sec")
            for pt in info["presentation_tables"][:8]:
                i.insert("end",f"  • {pt}\n","sa_lnk")
        i.config(state="disabled")

    def _info_show_tbl(self, tbl: str):
        oracle_path = BASE_DIR / "data" / "oracle_tables.json"
        oracle_info = {}
        if oracle_path.exists():
            try:
                oracle_info = json.loads(oracle_path.read_text()).get(tbl, {})
            except Exception:
                pass
        tinfo = TBL_DATA.get(tbl, {})
        cols  = tinfo.get("columns", [])
        sas   = tinfo.get("subject_areas", [])
        i = self._info; i.config(state="normal"); i.delete("1.0","end")
        btag = "back_btn"
        i.insert("end","← Back\n\n",btag)
        i.tag_configure(btag, foreground=BRAND["accent"],
                         font=("Segoe UI",9,"underline"))
        i.tag_bind(btag,"<Button-1>",
                   lambda e: self._info_show_sa(self._current_sa, SA_DATA[self._current_sa])
                   if self._current_sa else None)
        i.tag_bind(btag,"<Enter>",lambda e:i.config(cursor="hand2"))
        i.tag_bind(btag,"<Leave>",lambda e:i.config(cursor=""))
        i.insert("end","TABLE\n","sec")
        i.insert("end",f"{tbl}\n","tbl")
        if oracle_info.get("description"):
            i.insert("end",f"\n{oracle_info['description']}\n","dim")
        if oracle_info.get("primary_key"):
            i.insert("end","\nPRIMARY KEY\n","sec")
            for pk in oracle_info["primary_key"]:
                i.insert("end",f"  🔑 {pk}\n","pk")
        if oracle_info.get("foreign_keys"):
            i.insert("end","\nFOREIGN KEYS\n","sec")
            for fk in oracle_info["foreign_keys"]:
                cs = ", ".join(fk.get("columns",[]))
                i.insert("end",f"  {cs} → {fk.get('ref_table','')}\n","col")
        rich_cols = oracle_info.get("columns", {})
        all_cols  = list(rich_cols.keys()) if rich_cols else cols
        i.insert("end",f"\nCOLUMNS ({len(all_cols)})\n","sec")
        for col in all_cols[:50]:
            if col in rich_cols:
                ci   = rich_cols[col]
                nn   = "✦" if not ci.get("nullable",True) else " "
                i.insert("end",f"  {nn} {col:<34}","col")
                i.insert("end",f" {ci.get('type',''):<16} {ci.get('desc','')[:35]}\n","dim")
            else:
                i.insert("end",f"    {col}\n","col")
        if len(all_cols)>50:
            i.insert("end",f"  ... +{len(all_cols)-50} more\n","dim")
        i.insert("end",f"\nIN {len(sas)} SUBJECT AREA(S)\n","sec")
        for sa in sas[:10]:
            stag=f"sa_{id(sa)}"
            i.insert("end",f"  • {sa}\n",stag)
            i.tag_configure(stag,foreground=BRAND["text2"],font=("Segoe UI",9))
            i.tag_bind(stag,"<Button-1>",lambda e,s=sa:(self._info_show_sa(s,SA_DATA[s]),setattr(self,"_current_sa",s)))
            i.tag_bind(stag,"<Enter>",lambda e:i.config(cursor="hand2"))
            i.tag_bind(stag,"<Leave>",lambda e:i.config(cursor=""))
        i.config(state="disabled")

    # ══════════════════════════════════════════════════════════════════════
    # CHAT / GENERATE
    # ══════════════════════════════════════════════════════════════════════
    def _welcome(self):
        o = self._out; o.config(state="normal")
        o.insert("end","\n  ORBRICK SQL AUTOMATION\n","head1")
        o.insert("end","  Oracle Fusion BIP SQL Generator  ·  orbrick.com\n","dim")
        o.insert("end","  " + "─"*56 + "\n","sep")
        o.insert("end",
                 f"\n  {len(SA_DATA)} Subject Areas  ·  {len(TBL_DATA)} Oracle Fusion Tables\n"
                 "  Oracle (+) joins  ·  BIP parameters  ·  Column-validated\n\n","body")
        o.insert("end","  QUICK EXAMPLES\n","head2")
        o.insert("end",
                 "  • AR customer transaction SQL\n"
                 "  • AP invoice and AP payment with supplier\n"
                 "  • GL journal with code combination and SLA\n"
                 "  • Employee salary with organization\n"
                 "  • PO with lines and supplier\n"
                 "  • Bank statement reconciliation\n\n","tip")
        o.insert("end",
                 "  📚 Use the SQL Library tab to save and reuse your own reports.\n","dim")
        o.config(state="disabled")

    def _on_enter(self, event):
        if not (event.state & 0x1): self._ask(); return "break"

    def _ask(self, text: str = None, silent: bool = False):
        if self._busy: return
        if text is None: text = self._inp.get("1.0","end").strip()
        if not text: return
        if not silent: self._inp.delete("1.0","end")

        lib_hits = find_relevant(text, top_n=2)

        o = self._out; o.config(state="normal")
        o.insert("end","\n")
        o.insert("end","  YOU  ","you")
        o.insert("end","─"*50+"\n","sep")
        o.insert("end",f"  {text}\n","body")

        # Library hits
        if lib_hits:
            o.insert("end","\n  📚 FROM YOUR SQL LIBRARY\n","head2")
            o.insert("end","  " + "─"*50 + "\n","sep")
            for e in lib_hits:
                mcol  = MODULE_COLORS.get(e.get("module","OTH"), BRAND["text2"])
                mod_t = f"mb_{e['id']}"
                ltag  = f"lh_{e['id']}"
                o.insert("end","  ")
                o.insert("end",f" {e.get('module','?')} ", mod_t)
                o.tag_configure(mod_t, foreground="white",
                                 background=mcol, font=("Segoe UI",8,"bold"))
                o.insert("end","  ")
                o.insert("end",e["title"],ltag)
                o.tag_configure(ltag, foreground=BRAND["accent"],
                                 font=("Segoe UI",10,"bold","underline"))
                o.tag_bind(ltag,"<Button-1>",lambda ev,en=e:self._show_lib_entry(en))
                o.tag_bind(ltag,"<Enter>",lambda ev:o.config(cursor="hand2"))
                o.tag_bind(ltag,"<Leave>",lambda ev:o.config(cursor=""))
                if e.get("description"):
                    o.insert("end",f"\n  📝 {e['description']}","dim")
                tbls=e.get("tables",[])
                if tbls:
                    o.insert("end",f"\n  📊 {', '.join(tbls[:4])}{'...' if len(tbls)>4 else ''}","dim")
                o.insert("end","\n\n")
            o.insert("end","  " + "─"*50 + "\n","sep")

        o.insert("end","  ORBRICK  ","ai")
        o.insert("end","─"*50+"\n","sep")
        o.config(state="disabled")

        self._busy = True
        threading.Thread(
            target=lambda: self.root.after(0, lambda: self._show_result(answer(text))),
            daemon=True).start()

    def _show_lib_entry(self, entry: dict):
        increment_use(entry["id"])
        self.root.after(60, self._refresh_library)
        o = self._out; o.config(state="normal")
        o.insert("end",f"\n  📚 LIBRARY: {entry['title']}\n","head2")
        if entry.get("description"):
            o.insert("end",f"  {entry['description']}\n","dim")
        o.insert("end","\n")
        self._embed_sql_box(entry["sql"], f"Library SQL: {entry['title']}")
        o.config(state="disabled"); o.see("end")

    def _show_result(self, result: str):
        self._render_answer(result)
        # Auto-validate the generated SQL
        ss = result.find("-- ===")
        se = result.rfind("\nTABLES USED")
        if ss > 0 and se > ss:
            sql_txt = result[ss:se].strip()
            v = validate_sql(sql_txt)
            o = self._out; o.config(state="normal")
            if v["errors"]:
                for err in v["errors"]:
                    o.insert("end", f"  ⚠ VALIDATOR: {err.split(chr(10))[0]}\n","tip")
            o.insert("end","\n")
            o.config(state="disabled")
        else:
            o = self._out; o.config(state="normal"); o.insert("end","\n")
            o.config(state="disabled")
        self._busy = False; self._inp.focus()

    def _render_answer(self, raw: str):
        o = self._out; o.config(state="normal")
        ss = raw.find("-- ===")
        if ss == -1: ss = raw.find("SELECT\n")
        se = raw.rfind("\nTABLES USED")
        if ss > 0 and se > ss:
            gm     = raw.find("GENERATED BIP SQL")
            before = raw[:gm] if gm > 0 else ""
            sql_t  = raw[ss:se].strip()
            after  = raw[se:]
        else:
            before, sql_t, after = raw, "", ""
        for line in before.splitlines(): self._rline(o, line)
        if sql_t: self._embed_sql_box(sql_t, "GENERATED BIP SQL  ·  Oracle (+) joins  ·  Orbrick SQL Automation")
        for line in after.splitlines(): self._rline(o, line)
        o.config(state="disabled"); o.see("end")

    def _embed_sql_box(self, sql_txt: str, title: str):
        """Embed a white editable SQL widget in the chat output."""
        o = self._out
        o.insert("end","\n")
        tt = f"st_{id(sql_txt)}"
        o.insert("end",f"  ▌ {title}\n", tt)
        o.tag_configure(tt, foreground=BRAND["accent"],
                         font=("Segoe UI",9,"bold"), background=BRAND["bg3"])
        o.insert("end","  ")

        # White SQL Text widget
        frame = tk.Frame(o, bg="#cbd5e1", bd=1, relief="solid",
                         highlightthickness=0)
        line_count = sql_txt.count("\n") + 1
        sql_box = tk.Text(
            frame, bg=BRAND["bg_white"], fg=BRAND["text_dark"],
            insertbackground=BRAND["text_dark"],
            font=("Consolas",10), wrap="none", relief="flat", bd=0,
            highlightthickness=0, padx=16, pady=10,
            width=82, height=min(max(line_count+1,8),32))
        sb_v = tk.Scrollbar(frame, orient="vertical",   command=sql_box.yview, width=8)
        sb_h = tk.Scrollbar(frame, orient="horizontal", command=sql_box.xview, width=8)
        sql_box.config(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        sb_v.pack(side="right",  fill="y")
        sb_h.pack(side="bottom", fill="x")
        sql_box.pack(side="left", fill="both", expand=True)
        _setup_light_tags(sql_box)

        for line in sql_txt.splitlines():
            _insert_sql(sql_box, line, light=True)

        # Button bar
        btn_bar = tk.Frame(o, bg=BRAND["bg3"])

        def do_copy():
            cur = sql_box.get("1.0","end-1c")
            self.root.clipboard_clear(); self.root.clipboard_append(cur)
            copy_btn.config(text="✅ Copied!", fg=BRAND["green"])
            self.root.after(1500, lambda: copy_btn.config(text="📋 Copy SQL",fg=BRAND["cyan"]))

        def do_save():
            self._open_dialog(prefill=sql_box.get("1.0","end-1c"))

        def do_format():
            cur = sql_box.get("1.0","end-1c")
            sql_box.delete("1.0","end")
            for line in _format_sql(cur).splitlines():
                _insert_sql(sql_box, line, light=True)

        copy_btn = tk.Button(btn_bar, text="📋 Copy SQL",
                              bg=BRAND["bg3"], fg=BRAND["cyan"],
                              activebackground=BRAND["bg4"], relief="flat",
                              font=("Segoe UI",9,"bold"), cursor="hand2",
                              padx=10, pady=5, command=do_copy)
        copy_btn.pack(side="left", padx=4, pady=4)
        tk.Button(btn_bar, text="💾 Save to Library",
                  bg=BRAND["bg3"], fg=BRAND["green"],
                  activebackground=BRAND["bg4"], relief="flat",
                  font=("Segoe UI",9,"bold"), cursor="hand2",
                  padx=10, pady=5, command=do_save).pack(side="left", padx=2)
        tk.Button(btn_bar, text="⬜ Format",
                  bg=BRAND["bg3"], fg=BRAND["yellow"],
                  activebackground=BRAND["bg4"], relief="flat",
                  font=("Segoe UI",9,"bold"), cursor="hand2",
                  padx=10, pady=5, command=do_format).pack(side="left", padx=2)
        tk.Label(btn_bar, text=f"{line_count} lines  ·  editable",
                 bg=BRAND["bg3"], fg=BRAND["text3"],
                 font=("Segoe UI",8)).pack(side="right", padx=10)

        o.window_create("end", window=frame)
        o.insert("end","\n")
        o.window_create("end", window=btn_bar)
        o.insert("end","\n\n")

    def _rline(self, o, line: str):
        if not line.strip(): o.insert("end","\n"); return
        if re.match(r"^[A-Z ]{5,}={3,}|^={10,}",line):
            h=line.rstrip("= ").strip()
            if h: o.insert("end","\n  "+h+"\n","head2"); o.insert("end","  "+"─"*54+"\n","sep")
            else:  o.insert("end","  "+"─"*54+"\n","sep")
        elif re.match(r"^TABLE:",line): o.insert("end","  "+line+"\n","head1")
        elif re.match(r"^\s*•\s+[A-Z][A-Z0-9_]{3,}_",line):
            m=re.search(r"([A-Z][A-Z0-9_]{3,}_(?:ALL|F|V|B|TL|M|VL|S|X|GT))",line)
            if m:
                o.insert("end",line[:m.start()],"body")
                o.insert("end",m.group(1),"tlink")
                o.insert("end",line[m.end():]+"\n","body")
            else: o.insert("end",line+"\n","body")
        elif re.match(r"^\s*\[(?:ERP/SCM|HCM|CX)\]",line):
            m=re.match(r"^(\s*\[(?:ERP/SCM|HCM|CX)\]\s*)(.*)",line)
            if m: o.insert("end",m.group(1),"dim"); o.insert("end",m.group(2)+"\n","sa")
        elif line.startswith("TIP:"): o.insert("end","  "+line+"\n","tip")
        else: o.insert("end","  "+line+"\n","body")

    # ══════════════════════════════════════════════════════════════════════
    # LIBRARY
    # ══════════════════════════════════════════════════════════════════════
    def _refresh_library(self):
        q   = self._lib_search.get().strip()
        mod = self._lib_mod.get()
        ct  = self._lib_cat.get()
        tf  = ct if ct != "ALL" else "ALL"
        results = lib_search(q, mod, tf)
        self._lib_items = [e for _,e in results]
        self._lib_lb.delete(0,"end")
        ICONS={"AP":"💰","AR":"📥","GL":"📊","PO":"🛒","HCM":"👤","FA":"🏗",
               "SCM":"📦","PRJ":"📋","CE":"🏦","XLA":"🔗","OTH":"📄",
               "PLSQL":"⚙","VIEW":"👁","PACKAGE":"📦","TRIGGER":"⚡",
               "REPORT":"📊","API":"🔌","LOOKUP":"🔍","FLEX":"🔧",
               "SECURITY":"🔒","AUDIT":"📋","SETUP":"⚙","UTIL":"🛠"}
        for e in self._lib_items:
            icon   = ICONS.get(e.get("module","OTH"),"📄")
            ct_tag = (f" [{e.get('category_type','')}]"
                      if e.get("category_type","Module") != "Module" else "")
            self._lib_lb.insert("end",f"  {icon}  {e['title']}{ct_tag}")
        total = len(get_all())
        self._lib_cnt.config(text=f"{len(self._lib_items)}/{total}")
        stats = get_stats()
        mc = "  ".join(f"{m}:{n}" for m,n in list(stats["modules"].items())[:5])
        self._lib_stats_lbl.config(text=f"📚 {stats['total']} saved  ·  {mc}")
        sel = self._lib_lb.curselection()
        self._del_multi_btn.config(state="normal" if len(sel)>1 else "disabled")
        if not self._lib_items: self._clear_detail()

    def _on_lib_select(self, _e=None):
        sel = self._lib_lb.curselection()
        self._del_multi_btn.config(state="normal" if len(sel)>1 else "disabled")
        if not sel: return
        idx = sel[-1]
        if idx>=len(self._lib_items): return
        self._sel_entry = self._lib_items[idx]
        self._show_detail(self._sel_entry)

    def _show_detail(self, e: dict):
        mcol = MODULE_COLORS.get(e.get("module","OTH"), BRAND["text2"])
        self._lib_title.config(
            text=f"[{e.get('module','?')}]  {e['title']}", fg=mcol)
        tbls     = e.get("tables",[])
        tbls_str = ", ".join(tbls[:5]) + (f" +{len(tbls)-5}" if len(tbls)>5 else "")
        self._lib_meta.config(
            text=(f"Category: {e.get('category_type','Module')}  ·  "
                  f"Created: {e.get('created','-')}  ·  Updated: {e.get('updated','-')}  ·  "
                  f"Used: {e.get('use_count',0)}×\n"
                  f"Tables: {tbls_str or 'none'}\n"
                  f"Description: {e.get('description','—')}"))
        for w in self._lib_tags_frame.winfo_children(): w.destroy()
        for tag in e.get("tags",[]):
            tk.Label(self._lib_tags_frame, text=f"  #{tag}  ",
                     bg=BRAND["bg3"], fg=BRAND["accent"],
                     font=("Segoe UI",8), padx=2, pady=2
                     ).pack(side="left", padx=2)
        sql = e.get("sql","") or ""
        self._lib_sql.config(state="normal"); self._lib_sql.delete("1.0","end")
        for line in sql.splitlines():
            _insert_sql(self._lib_sql, line, light=False)
        self._lib_sql.config(state="disabled")
        self._sql_lines_lbl.config(text=f"{len(sql.splitlines())} lines")
        for b in (self._bcopy,self._bedit,self._bdel): b.config(state="normal")

    def _clear_detail(self):
        self._lib_title.config(text="← Select a query to view",fg=BRAND["text"])
        self._lib_meta.config(text="")
        for w in self._lib_tags_frame.winfo_children(): w.destroy()
        self._lib_sql.config(state="normal"); self._lib_sql.delete("1.0","end")
        self._lib_sql.config(state="disabled")
        self._sql_lines_lbl.config(text="")
        for b in (self._bcopy,self._bedit,self._bdel): b.config(state="disabled")
        self._sel_entry = None

    def _copy_sel(self):
        if not self._sel_entry: return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._sel_entry.get("sql",""))
        increment_use(self._sel_entry["id"])
        self.root.after(60, self._refresh_library)
        self._bcopy.config(text="✅ Copied!",fg=BRAND["green"])
        self.root.after(1500,lambda:self._bcopy.config(text="📋 Copy",fg=BRAND["cyan"]))

    def _edit_sel(self):
        if self._sel_entry: self._open_dialog(edit=self._sel_entry)

    def _del_sel(self):
        if not self._sel_entry: return
        if messagebox.askyesno("Delete",f"Delete '{self._sel_entry['title']}'?",icon="warning"):
            delete_entry(self._sel_entry["id"])
            self._clear_detail(); self._refresh_library()

    def _delete_multi(self):
        sel = self._lib_lb.curselection()
        if len(sel)<2: return
        titles=[self._lib_items[i]["title"] for i in sel if i<len(self._lib_items)]
        if not messagebox.askyesno("Delete Multiple",
            f"Delete {len(titles)} queries?\n"+"\n".join(f"  • {t}" for t in titles[:6])+
            (f"\n  +{len(titles)-6} more" if len(titles)>6 else ""),icon="warning"): return
        ids=[self._lib_items[i]["id"] for i in sel if i<len(self._lib_items)]
        removed=delete_multiple(ids)
        self._clear_detail(); self._refresh_library()
        messagebox.showinfo("Deleted",f"Deleted {removed} queries.")

    # ══════════════════════════════════════════════════════════════════════
    # ADD / EDIT DIALOG
    # ══════════════════════════════════════════════════════════════════════
    def _open_dialog(self, edit=None, prefill: str=""):
        dlg=tk.Toplevel(self.root)
        dlg.title("Edit SQL" if edit else "Add SQL to Library")
        dlg.geometry("980x760"); dlg.configure(bg=BRAND["bg2"])
        dlg.resizable(True,True); dlg.grab_set()

        # Dialog header
        dhdr=tk.Frame(dlg,bg=BRAND["accent"],pady=10,padx=16); dhdr.pack(fill="x")
        tk.Label(dhdr,text="✏ Edit SQL" if edit else "➕ Add SQL to Library",
                 font=("Segoe UI",13,"bold"),bg=BRAND["accent"],fg="white").pack(side="left")

        main=tk.Frame(dlg,bg=BRAND["bg2"]); main.pack(fill="both",expand=True,padx=14,pady=10)

        # Left form
        left=tk.Frame(main,bg=BRAND["bg2"],width=330); left.pack(side="left",fill="y",padx=(0,10))
        left.pack_propagate(False)

        def lbl(t):
            tk.Label(left,text=t,font=("Segoe UI",9,"bold"),
                     bg=BRAND["bg2"],fg=BRAND["text2"],anchor="w").pack(fill="x",pady=(8,2))

        lbl("Title *")
        tv=tk.StringVar(value=edit["title"] if edit else "")
        te=tk.Entry(left,textvariable=tv,bg=BRAND["bg4"],fg=BRAND["text"],
                    insertbackground=BRAND["text"],relief="flat",font=("Segoe UI",10))
        te.pack(fill="x",ipady=5)

        lbl("Description")
        dv=tk.StringVar(value=edit.get("description","") if edit else "")
        tk.Entry(left,textvariable=dv,bg=BRAND["bg4"],fg=BRAND["text"],
                 insertbackground=BRAND["text"],relief="flat",font=("Segoe UI",10)).pack(fill="x",ipady=4)

        lbl("Tags (comma separated)")
        tagv=tk.StringVar(value=", ".join(edit.get("tags",[])) if edit else "")
        tk.Entry(left,textvariable=tagv,bg=BRAND["bg4"],fg=BRAND["text"],
                 insertbackground=BRAND["text"],relief="flat",font=("Segoe UI",10)).pack(fill="x",ipady=4)

        row2=tk.Frame(left,bg=BRAND["bg2"]); row2.pack(fill="x",pady=(8,0))
        mf=tk.Frame(row2,bg=BRAND["bg2"]); mf.pack(side="left",fill="x",expand=True)
        tk.Label(mf,text="Module",font=("Segoe UI",9,"bold"),bg=BRAND["bg2"],fg=BRAND["text2"]).pack(anchor="w")
        mv=tk.StringVar(value=edit.get("module","AP") if edit else "AP")
        mod_cb=ttk.Combobox(mf,textvariable=mv,
                             values=[m for g in CATEGORY_GROUPS.values() for m in g],
                             state="readonly",width=11,font=("Segoe UI",10))
        mod_cb.pack(ipady=3,fill="x")
        cf=tk.Frame(row2,bg=BRAND["bg2"]); cf.pack(side="right",padx=(8,0))
        tk.Label(cf,text="Category",font=("Segoe UI",9,"bold"),bg=BRAND["bg2"],fg=BRAND["text2"]).pack(anchor="w")
        ctv=tk.StringVar(value=edit.get("category_type","Module") if edit else "Module")
        ttk.Combobox(cf,textvariable=ctv,values=["Module","Tech","Common"],
                     state="readonly",width=10,font=("Segoe UI",10)).pack(ipady=3)

        tk.Frame(left,bg=BRAND["border"],height=1).pack(fill="x",pady=(14,6))
        status_lbl=tk.Label(left,text="",font=("Segoe UI",8,"italic"),
                             bg=BRAND["bg2"],fg=BRAND["green"],wraplength=300,justify="left")
        status_lbl.pack(fill="x",pady=(0,4))

        def do_analyze():
            sql=sqt.get("1.0","end").strip()
            if not sql: status_lbl.config(text="⚠ Paste SQL first",fg=BRAND["red"]); return
            status_lbl.config(text="Analysing SQL…",fg=BRAND["yellow"]); dlg.update()
            try:
                meta=analyze_sql(sql)
                if not tv.get() or tv.get().startswith("Untitled"): tv.set(meta["title"])
                if not dv.get(): dv.set(meta["description"])
                if not tagv.get(): tagv.set(", ".join(meta["tags"]))
                mv.set(meta["module"])
                status_lbl.config(
                    text=f"✅ Auto-filled:\n{meta['title']}\nModule: {meta['module']}  Tables: {len(meta['tables'])}",
                    fg=BRAND["green"])
            except Exception as ex:
                status_lbl.config(text=f"Error: {ex}",fg=BRAND["red"])

        tk.Button(left,text=" 🤖  Re-Analyse SQL ",
                  bg=BRAND["accent"],fg="white",
                  activebackground=BRAND["accent2"],activeforeground="white",
                  relief="flat",font=("Segoe UI",10,"bold"),cursor="hand2",
                  pady=7,command=do_analyze).pack(fill="x")
        tk.Label(left,
                 text="Fields are auto-filled when you paste SQL →\nClick Re-Analyse to override with fresh suggestions",
                 font=("Segoe UI",8,"italic"),bg=BRAND["bg2"],
                 fg=BRAND["text3"],justify="left").pack(anchor="w",pady=(6,0))

        # Right SQL editor
        right=tk.Frame(main,bg=BRAND["bg2"]); right.pack(side="right",fill="both",expand=True)
        tk.Label(right,text="SQL *",font=("Segoe UI",9,"bold"),
                 bg=BRAND["bg2"],fg=BRAND["text2"]).pack(anchor="w",pady=(0,4))
        sqt=scrolledtext.ScrolledText(right,bg="#0d1117",fg="#e5e7eb",
                                       insertbackground="white",relief="flat",
                                       font=("Consolas",10),wrap="none",padx=10,pady=8)
        sqt.pack(fill="both",expand=True)

        # Fields filled manually by user

        # Auto-fill removed per user request - user fills manually
        # Auto-Fill button still available for manual trigger

        if edit:
            sqt.insert("1.0",edit.get("sql",""))
            right.after(200, _auto_analyze_silent)  # pre-fill when editing
        elif prefill:
            sqt.insert("1.0",prefill)
            right.after(200, _auto_analyze_silent)  # pre-fill when saving from generator

        # Footer
        tk.Frame(dlg,bg=BRAND["accent"],height=2).pack(fill="x")
        br=tk.Frame(dlg,bg=BRAND["bg2"],pady=10); br.pack(fill="x",padx=14)
        sl=tk.Label(br,text="",font=("Segoe UI",9),bg=BRAND["bg2"],fg=BRAND["green"]); sl.pack(side="left")

        def do_save():
            t=tv.get().strip(); s=sqt.get("1.0","end").strip()
            if not t: sl.config(text="⚠ Title required",fg=BRAND["red"]); return
            if not s: sl.config(text="⚠ SQL required",  fg=BRAND["red"]); return
            entry=save_entry(title=t,sql=s,description=dv.get().strip(),
                             tags=tagv.get(),module=mv.get(),category_type=ctv.get())
            self._refresh_library()
            for i2,e2 in enumerate(self._lib_items):
                if e2["id"]==entry["id"]:
                    self._lib_lb.selection_clear(0,"end")
                    self._lib_lb.selection_set(i2); self._lib_lb.see(i2)
                    self._sel_entry=e2; self._show_detail(e2); break
            sl.config(text=f"✅ Saved: {t}",fg=BRAND["green"])
            self.root.after(1200,dlg.destroy)

        def do_validate():
            sql_txt = sqt.get("1.0","end").strip()
            if not sql_txt:
                sl.config(text="⚠ Paste SQL first",fg=BRAND["red"]); return
            from sql_validator import validate_sql as _vsql
            r = _vsql(sql_txt)
            msgs = [f"Quality Score: {r['score']}/100"]
            for err in r["errors"]:   msgs.append("❌ "+err.split("\n")[0][:70])
            for wrn in r["warnings"]: msgs.append("⚠ "+wrn.split("\n")[0][:70])
            if not r["errors"] and not r["warnings"]: msgs.append("✅ SQL looks correct!")
            col = BRAND["green"] if r["score"]>=90 else (BRAND["yellow"] if r["score"]>=70 else BRAND["red"])
            sl.config(text="\n".join(msgs[:6]),fg=col)

        tk.Button(br,text=" 🔍 Validate ",
                  bg=BRAND["bg3"],fg=BRAND["cyan"],
                  activebackground=BRAND["bg4"],activeforeground=BRAND["text"],
                  relief="flat",font=("Segoe UI",10,"bold"),cursor="hand2",
                  padx=10,pady=6,command=do_validate).pack(side="right",padx=3)
        tk.Button(br,text=" 💾  Save to Library ",
                  bg=BRAND["accent"],fg="white",
                  activebackground=BRAND["accent2"],activeforeground="white",
                  relief="flat",font=("Segoe UI",10,"bold"),cursor="hand2",
                  padx=14,pady=6,command=do_save).pack(side="right",padx=4)
        tk.Button(br,text=" Cancel ",
                  bg=BRAND["bg4"],fg=BRAND["text2"],
                  activebackground=BRAND["bg3"],activeforeground=BRAND["text"],
                  relief="flat",font=("Segoe UI",10),cursor="hand2",
                  padx=14,pady=6,command=dlg.destroy).pack(side="right",padx=4)
        te.focus(); dlg.bind("<Escape>",lambda e:dlg.destroy())

    # ══════════════════════════════════════════════════════════════════════
    # FILE IMPORT
    # ══════════════════════════════════════════════════════════════════════
    def _import_files(self):
        paths=filedialog.askopenfilenames(
            title="Select SQL / TXT / JSON files",
            filetypes=[("SQL","*.sql"),("Text","*.txt"),("JSON","*.json"),("All","*.*")],
            parent=self.root)
        if not paths: return
        ta=ts=0; errors=[]
        for path in paths:
            p=Path(path)
            try:
                text=p.read_text(encoding="utf-8",errors="replace")
                entries=[]
                if p.suffix.lower()==".json":
                    try:
                        d=json.loads(text)
                        entries=d if isinstance(d,list) else ([d] if "sql" in d else [])
                    except json.JSONDecodeError as je: errors.append(f"{p.name}: {je}"); continue
                else:
                    for chunk in re.split(r"\n--\s*[=─]{4,}[^\n]*\n",text):
                        chunk=chunk.strip()
                        if not chunk: continue
                        tm=re.search(r"--\s*(?:Report|Title|Name|SQL):\s*(.+)",chunk,re.I)
                        entries.append({"title":tm.group(1).strip() if tm else p.stem,"sql":chunk})
                a,s=bulk_import(entries); ta+=a; ts+=s
            except Exception as ex: errors.append(f"{p.name}: {ex}")
        msg=f"Import complete!\n\n✅ Added: {ta}\n⏭ Skipped: {ts} (duplicates)"
        if errors: msg+="\n\n⚠ Errors:\n"+"\n".join(errors[:5])
        messagebox.showinfo("Import Results",msg)
        self._refresh_library()

    # ══════════════════════════════════════════════════════════════════════
    # ORACLE DOCS URL IMPORTER
    # ══════════════════════════════════════════════════════════════════════
    def _import_oracle_url(self):
        import urllib.request
        dlg=tk.Toplevel(self.root)
        dlg.title("Import Oracle Docs Table"); dlg.geometry("820x560")
        dlg.configure(bg=BRAND["bg2"]); dlg.resizable(True,True); dlg.grab_set()
        dhdr=tk.Frame(dlg,bg=BRAND["accent"],pady=10,padx=16); dhdr.pack(fill="x")
        tk.Label(dhdr,text="🌐  Import Oracle Fusion Table from Documentation",
                 font=("Segoe UI",12,"bold"),bg=BRAND["accent"],fg="white").pack(side="left")
        fm=tk.Frame(dlg,bg=BRAND["bg2"]); fm.pack(fill="both",expand=True,padx=16,pady=10)
        tk.Label(fm,text="Single URL:",font=("Segoe UI",9,"bold"),bg=BRAND["bg2"],fg=BRAND["text2"]).pack(anchor="w")
        url_var=tk.StringVar(value="https://docs.oracle.com/en/cloud/saas/financials/26b/oedmf/")
        url_e=tk.Entry(fm,textvariable=url_var,bg=BRAND["bg4"],fg=BRAND["text"],
                        insertbackground=BRAND["text"],relief="flat",font=("Segoe UI",10))
        url_e.pack(fill="x",ipady=5)
        tk.Label(fm,text="OR multiple URLs (one per line):",font=("Segoe UI",9,"bold"),
                 bg=BRAND["bg2"],fg=BRAND["text2"],pady=4).pack(anchor="w")
        multi=tk.Text(fm,bg=BRAND["bg4"],fg=BRAND["text"],insertbackground=BRAND["text"],
                      relief="flat",font=("Segoe UI",9),height=4,padx=8,pady=4)
        multi.pack(fill="x")
        res_out=scrolledtext.ScrolledText(fm,bg=BRAND["bg3"],fg=BRAND["text"],
                                           relief="flat",font=("Consolas",9),
                                           height=9,state="disabled",padx=8,pady=4)
        res_out.pack(fill="both",expand=True,pady=(8,0))
        tk.Frame(dlg,bg=BRAND["accent"],height=2).pack(fill="x")
        br=tk.Frame(dlg,bg=BRAND["bg2"],pady=8); br.pack(fill="x",padx=16)
        st=tk.Label(br,text="",font=("Segoe UI",9),bg=BRAND["bg2"],fg=BRAND["green"]); st.pack(side="left")

        def fetch():
            urls_raw=multi.get("1.0","end").strip()
            urls=[u.strip() for u in urls_raw.splitlines() if u.strip().startswith("http")]
            if not urls:
                s=url_var.get().strip()
                if s: urls=[s]
            if not urls: st.config(text="⚠ Enter a URL",fg=BRAND["red"]); return
            res_out.config(state="normal"); res_out.delete("1.0","end")
            fetch_btn.config(state="disabled",text="Fetching…"); dlg.update()
            oracle_path=BASE_DIR/"data"/"oracle_tables.json"
            oracle_data={}
            try:
                if oracle_path.exists(): oracle_data=json.loads(oracle_path.read_text())
            except: pass
            added=[]
            for url in urls:
                res_out.insert("end",f"Fetching: {url.split('/')[-1][:50]}…\n")
                res_out.config(state="disabled"); dlg.update(); res_out.config(state="normal")
                try:
                    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html,*/*"})
                    with urllib.request.urlopen(req,timeout=15) as r:
                        html=r.read().decode("utf-8","replace")
                    tbl_name=""
                    for pat in [r"<h1[^>]*>\s*([A-Z][A-Z0-9_]+)\s*</h1>",r"<title>\s*([A-Z][A-Z0-9_]+)"]:
                        m=re.search(pat,html)
                        if m: tbl_name=m.group(1).strip(); break
                    col_dict={}
                    for cname,dtype in re.findall(r"<td[^>]*>\s*([A-Z][A-Z0-9_]{2,})\s*</td>\s*<td[^>]*>(NUMBER|VARCHAR2[^<]*|TIMESTAMP[^<]*|DATE[^<]*)",html):
                        if cname not in ("Name","Columns","Table","Column","Previous","Next"):
                            col_dict[cname]={"type":dtype.strip()[:30],"desc":""}
                    if tbl_name and col_dict:
                        oracle_data[tbl_name]={"description":"","columns":col_dict,"primary_key":[],"foreign_keys":[],"source":url}
                        added.append(tbl_name)
                        res_out.insert("end",f"  ✅ {tbl_name}: {len(col_dict)} columns\n")
                    else:
                        res_out.insert("end",f"  ⚠ Could not parse: {url}\n")
                except Exception as ex:
                    res_out.insert("end",f"  ❌ {ex}\n")
            if added:
                oracle_path.write_text(json.dumps(oracle_data,indent=2))
                res_out.insert("end",f"\n✅ Saved {len(added)} table(s) to oracle_tables.json\n")
                st.config(text=f"✅ Imported {len(added)} table(s)",fg=BRAND["green"])
            else:
                st.config(text="⚠ No tables imported",fg=BRAND["red"])
            res_out.config(state="disabled")
            fetch_btn.config(state="normal",text=" 🔍 Fetch & Import ")

        fetch_btn=tk.Button(br,text=" 🔍 Fetch & Import ",
                             bg=BRAND["accent"],fg="white",activebackground=BRAND["accent2"],
                             relief="flat",font=("Segoe UI",10,"bold"),cursor="hand2",
                             padx=12,pady=6,
                             command=lambda:threading.Thread(target=fetch,daemon=True).start())
        fetch_btn.pack(side="right",padx=4)
        tk.Button(br,text=" Close ",bg=BRAND["bg4"],fg=BRAND["text2"],
                  activebackground=BRAND["bg3"],relief="flat",font=("Segoe UI",10),
                  cursor="hand2",padx=12,pady=6,command=dlg.destroy).pack(side="right",padx=4)
        url_e.focus()


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    OrbrickApp(root)
    root.mainloop()
