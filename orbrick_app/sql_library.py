"""sql_library.py — Orbrick SQL Library"""
import json, re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
LIB_FILE = BASE_DIR / "data" / "sql_library.json"

MODULE_PATTERNS = {
    "AP":  [r'\bAP_INVOICE', r'\bAP_CHECK', r'\bAP_PAYMENT', r'\bPOZ_SUPPLIER'],
    "AR":  [r'\bRA_CUSTOMER', r'\bAR_ADJUST', r'\bAR_CASH_RECEIPT', r'\bHZ_CUST_ACCOUNT'],
    "GL":  [r'\bGL_JE_', r'\bGL_BALANCE', r'\bGL_LEDGER', r'\bGL_CODE_COMB'],
    "PO":  [r'\bPO_HEADER', r'\bPO_LINE', r'\bPO_DISTRIB', r'\bPOR_REQUISI'],
    "HCM": [r'\bPER_ALL_PEOPLE', r'\bPER_ALL_ASSIGN', r'\bPAY_PAYROLL', r'\bPER_PERSON_NAME'],
    "FA":  [r'\bFA_ADDITION', r'\bFA_BOOK', r'\bFA_DEPRN'],
    "SCM": [r'\bRCV_SHIPMENT', r'\bINV_', r'\bMTL_'],
    "PRJ": [r'\bPJF_PROJECT', r'\bPJC_EXP'],
    "CE":  [r'\bCE_STATEMENT', r'\bCE_BANK'],
    "XLA": [r'\bXLA_AE_'],
}

CATEGORY_GROUPS = {
    "Module":  ["AP","AR","GL","PO","HCM","FA","SCM","PRJ","CE","XLA","OTH"],
    "Tech":    ["PLSQL","VIEW","PACKAGE","TRIGGER","REPORT","API"],
    "Common":  ["LOOKUP","FLEX","SECURITY","AUDIT","SETUP","UTIL"],
}

MODULE_COLORS = {
    "AP":"#2563eb","AR":"#db2777","GL":"#059669","PO":"#d97706",
    "HCM":"#7c3aed","FA":"#ca8a04","SCM":"#0891b2","PRJ":"#65a30d",
    "CE":"#0d9488","XLA":"#4f46e5","OTH":"#6b7280",
    "PLSQL":"#dc2626","VIEW":"#0284c7","PACKAGE":"#9333ea",
    "TRIGGER":"#e11d48","REPORT":"#16a34a","API":"#06b6d4",
    "LOOKUP":"#d97706","FLEX":"#0891b2","SECURITY":"#dc2626",
    "AUDIT":"#16a34a","SETUP":"#7c3aed","UTIL":"#f97316",
}

TITLE_MAP = {
    "AP_INVOICES_ALL":             "AP Invoice",
    "AP_CHECKS_ALL":               "AP Payment",
    "AP_INVOICE_PAYMENTS_ALL":     "AP Invoice Payment",
    "AR_ADJUSTMENTS_ALL":          "AR Adjustment",
    "RA_CUSTOMER_TRX_ALL":         "AR Customer Transaction",
    "AR_CASH_RECEIPTS_ALL":        "AR Cash Receipt",
    "AR_PAYMENT_SCHEDULES_ALL":    "AR Aging",
    "GL_JE_HEADERS":               "GL Journal",
    "GL_BALANCES":                 "GL Balance",
    "PO_HEADERS_ALL":              "Purchase Order",
    "POR_REQUISITION_HEADERS_ALL": "Purchase Requisition",
    "RCV_SHIPMENT_HEADERS":        "PO Receipt",
    "PER_ALL_PEOPLE_F":            "Employee",
    "PAY_PAYROLL_ACTIONS":         "Payroll Run",
    "FA_ADDITIONS_B":              "Fixed Asset",
    "FA_DEPRN_SUMMARY":            "Asset Depreciation",
    "CE_STATEMENT_HEADERS":        "Bank Statement",
    "XLA_AE_HEADERS":              "Subledger Accounting",
    "PJF_PROJECTS_ALL_VL":         "Project",
    "PJC_EXP_ITEMS_ALL":           "Project Cost",
}

TAG_MAP = {
    "AP_INVOICES_ALL":             ["invoice","ap","payable"],
    "AP_CHECKS_ALL":               ["payment","check","ap"],
    "RA_CUSTOMER_TRX_ALL":         ["invoice","transaction","ar","customer"],
    "AR_ADJUSTMENTS_ALL":          ["adjustment","ar"],
    "AR_CASH_RECEIPTS_ALL":        ["receipt","ar","cash"],
    "AR_PAYMENT_SCHEDULES_ALL":    ["aging","schedule","ar"],
    "GL_JE_HEADERS":               ["journal","gl","entry"],
    "GL_BALANCES":                 ["balance","gl","trial"],
    "GL_CODE_COMBINATIONS":        ["coa","account","segment","gl"],
    "PO_HEADERS_ALL":              ["po","purchase-order","procurement"],
    "PER_ALL_PEOPLE_F":            ["employee","person","hcm"],
    "PAY_PAYROLL_ACTIONS":         ["payroll","salary","hcm"],
    "FA_ADDITIONS_B":              ["asset","fixed-asset","fa"],
    "FA_DEPRN_SUMMARY":            ["depreciation","asset","fa"],
    "CE_STATEMENT_HEADERS":        ["bank","statement","cash"],
    "XLA_AE_HEADERS":              ["sla","subledger","accounting","xla"],
    "POZ_SUPPLIERS":               ["supplier","vendor","ap"],
    "HZ_PARTIES":                  ["party","customer","supplier"],
    "HZ_CUST_ACCOUNTS":            ["customer","account","ar"],
    "PJF_PROJECTS_ALL_VL":         ["project","prj"],
    "PJC_EXP_ITEMS_ALL":           ["expense","cost","project"],
}


def _detect_module(sql: str) -> str:
    su = sql.upper()
    tables = _extract_tables(sql)
    # Check patterns against full text
    for mod, patterns in MODULE_PATTERNS.items():
        if any(re.search(p, su) for p in patterns):
            return mod
    # Fallback: check table prefixes
    for tbl in tables:
        prefix = tbl.split("_")[0]
        if prefix in ("GL","XLA"): return "GL"
        if prefix in ("AP","POZ"): return "AP"
        if prefix in ("AR","RA","HZ"): return "AR"
        if prefix in ("PO","POR","RCV"): return "PO"
        if prefix in ("PER","PAY","HR"): return "HCM"
        if prefix in ("FA",): return "FA"
        if prefix in ("CE",): return "CE"
        if prefix in ("PJF","PJC"): return "PRJ"
    return "OTH"


_TPREFIX = (
    'GL_','AP_','AR_','HZ_','PO_','POR_','RCV_','FA_','CE_','XLA_',
    'PER_','PAY_','HR_','RA_','FUN_','POZ_','PON_','PJF_','PJC_',
    'IBY_','ZX_','OKC_','FND_','BEN_','OTA_','MTL_','MFG_','WIP_',
    'CST_','INV_','ONT_','OE_','WSH_','ACN_','GMS_','AHL_',
)

def _extract_tables(sql: str) -> list:
    """
    Extract table names from SQL using FROM clause parsing.
    Most reliable: scans the FROM ... WHERE block for table identifiers.
    Falls back to prefix matching for subqueries / inline views.
    """
    # Strip comments
    clean = re.sub(r'--[^\n]*', '', sql).upper()

    tables = set()

    # Primary: parse FROM clause entries  (TABLE_NAME  alias,  TABLE_NAME  alias)
    from_match = re.search(
        r'\bFROM\b\s+(.*?)(?:\bWHERE\b|\bORDER\s+BY\b|\bGROUP\s+BY\b|$)',
        clean, re.DOTALL)
    if from_match:
        for entry in from_match.group(1).split(','):
            tbl = entry.strip().split()[0] if entry.strip() else ''
            if any(tbl.startswith(p) for p in _TPREFIX) and len(tbl) >= 5:
                tables.add(tbl)

    # Secondary: any word starting with a known prefix anywhere in SQL
    for word in re.findall(r'\b([A-Z][A-Z0-9_]{4,})\b', clean):
        if any(word.startswith(p) for p in _TPREFIX):
            tables.add(word)

    return sorted(tables)


def analyze_sql(sql: str) -> dict:
    """Auto-generate metadata from SQL text. Called on paste for instant suggestions."""
    tables  = _extract_tables(sql)
    module  = _detect_module(sql)

    MOD_NAMES = {
        "AP":"Accounts Payable","AR":"Accounts Receivable","GL":"General Ledger",
        "PO":"Procurement","HCM":"Human Capital Management","FA":"Fixed Assets",
        "SCM":"Supply Chain","PRJ":"Projects","CE":"Cash Management",
        "XLA":"Subledger Accounting","OTH":"Oracle Fusion",
    }

    # ── Smart title ───────────────────────────────────────────────────
    # 1. Check for -- Report: comment first
    comment_title = re.search(r'--\s*(?:Report|Title|Name):\s*(.+)', sql, re.I)
    if comment_title:
        title = comment_title.group(1).strip()[:80]
    else:
        found = [TITLE_MAP[t] for t in tables if t in TITLE_MAP]
        unique = list(dict.fromkeys(found))[:3]
        if unique:
            title = " + ".join(unique) + " Report"
        else:
            title = f"{MOD_NAMES.get(module, module)} Report"

    # ── Smart description ─────────────────────────────────────────────
    main_tbls = [t for t in tables
                 if not any(t.endswith(s) for s in ("_TL","_B","_GT","_F_V"))][:4]
    
    # Detect what the SQL does from WHERE clause
    sql_up = sql.upper()
    features = []
    if "GL_IMPORT_REFERENCES" in sql_up or "GL_SL_LINK_ID" in sql_up:
        features.append("subledger accounting (SLA)")
    if "XLA_AE_LINES" in sql_up or "XLA_AE_HEADERS" in sql_up:
        features.append("SLA accounting entries")
    if "GL_CODE_COMBINATIONS" in sql_up or "SEGMENT1" in sql_up:
        features.append("GL account combinations")
    if "HZ_CONTACT_POINTS" in sql_up:
        features.append("contact points")
    if "HZ_LOCATIONS" in sql_up or "HZ_PARTY_SITES" in sql_up:
        features.append("addresses")
    if "AP_INVOICE_PAYMENTS" in sql_up or "AP_CHECKS" in sql_up:
        features.append("payments")
    if "PAY_RUN_RESULT" in sql_up or "PAY_ELEMENT" in sql_up:
        features.append("payroll elements")
    if ":P_START_DATE" in sql_up or ":P_END_DATE" in sql_up:
        features.append("date range parameters")
    if ":P_LEDGER_ID" in sql_up:
        features.append("ledger parameter")
    if ":P_ORG_ID" in sql_up:
        features.append("org/BU parameter")

    mod_name = MOD_NAMES.get(module, module)
    tbl_str  = ", ".join(main_tbls[:3])
    feat_str = ("; includes " + ", ".join(features)) if features else ""
    description = (
        f"{mod_name} Oracle Fusion BIP report. "
        f"Tables: {tbl_str}{feat_str}. "
        f"Oracle (+) outer-join syntax for BIP/OTBI."
    )

    # ── Smart tags ────────────────────────────────────────────────────
    tags = {module.lower(), "bip", "fusion", "oracle"}
    # Module-specific base tags
    base_tags = {"GL":["gl","journal","ledger"],"AP":["ap","payable","invoice"],
                 "AR":["ar","receivable","customer"],"PO":["po","purchase","procurement"],
                 "HCM":["hcm","employee","hr"],"FA":["fa","asset","fixed-asset"],
                 "CE":["ce","bank","cash"],"XLA":["xla","subledger","sla"],
                 "PRJ":["project","prj"],"SCM":["scm","supply-chain"]}
    tags.update(base_tags.get(module, []))
    # Table-specific tags
    for tbl in tables:
        for pattern_tbl, t_tags in TAG_MAP.items():
            if pattern_tbl in tbl:
                tags.update(t_tags)
    # Feature-specific tags
    if "subledger" in " ".join(features): tags.add("sla")
    if "contact" in " ".join(features):   tags.add("contact-point")
    if "payments" in " ".join(features):  tags.add("payment")
    if "payroll" in " ".join(features):   tags.add("payroll")
    if "address" in " ".join(features):   tags.add("address")

    return {
        "title":       title,
        "description": description,
        "module":      module,
        "tables":      tables,
        "tags":        sorted(tags)[:14],
    }


def _load() -> list:
    if LIB_FILE.exists():
        try:
            return json.loads(LIB_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save(entries: list):
    LIB_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIB_FILE.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def get_all() -> list:
    return _load()


def save_entry(title: str, sql: str, description: str = "",
               tags: str = "", module: str = "",
               category_type: str = "Module",
               auto_analyze: bool = False) -> dict:
    entries = _load()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if auto_analyze:
        meta = analyze_sql(sql)
        if not title or title.startswith("Untitled"):
            title = meta["title"]
        if not description:
            description = meta["description"]
        if not module:
            module = meta["module"]
        if not tags:
            tags = ", ".join(meta["tags"])

    if not module:
        module = _detect_module(sql)

    tables   = _extract_tables(sql)
    tag_list = [t.strip().lower() for t in re.split(r'[,;\s]+', tags) if t.strip()]

    # Update if title exists
    existing = next((e for e in entries if e["title"].lower() == title.lower()), None)
    if existing:
        existing.update({"sql":sql,"description":description,"tags":tag_list,
                          "module":module,"category_type":category_type,
                          "tables":tables,"updated":now})
        _save(entries)
        return existing

    entry = {
        "id":            f"q{len(entries)+1:04d}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "title":         title,
        "description":   description,
        "module":        module,
        "category_type": category_type,
        "tags":          tag_list,
        "tables":        tables,
        "sql":           sql,
        "created":       now,
        "updated":       now,
        "use_count":     0,
    }
    entries.append(entry)
    _save(entries)
    return entry


def delete_entry(eid: str) -> bool:
    entries = _load()
    new = [e for e in entries if e["id"] != eid]
    if len(new) < len(entries):
        _save(new); return True
    return False


def delete_multiple(eids: list) -> int:
    entries = _load()
    id_set  = set(eids)
    new     = [e for e in entries if e["id"] not in id_set]
    removed = len(entries) - len(new)
    _save(new)
    return removed


def increment_use(eid: str):
    entries = _load()
    for e in entries:
        if e["id"] == eid:
            e["use_count"] = e.get("use_count", 0) + 1
            break
    _save(entries)


def bulk_import(items: list) -> tuple:
    existing  = _load()
    ex_titles = {e["title"].lower() for e in existing}
    added = skipped = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for item in items:
        s = item.get("sql","").strip()
        if not s:
            skipped += 1; continue
        t = item.get("title","").strip()
        if not t:
            t = analyze_sql(s)["title"]
        if t.lower() in ex_titles:
            skipped += 1; continue
        meta  = analyze_sql(s)
        tags  = item.get("tags",[])
        if isinstance(tags, str):
            tags = [x.strip() for x in re.split(r'[,;\s]+', tags) if x.strip()]
        if not tags:
            tags = meta["tags"]
        entry = {
            "id":            f"q{len(existing)+added+1:04d}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{added}",
            "title":         t,
            "description":   item.get("description","") or meta["description"],
            "module":        item.get("module","") or meta["module"],
            "category_type": item.get("category_type","Module"),
            "tags":          tags,
            "tables":        meta["tables"],
            "sql":           s,
            "created":       now, "updated": now, "use_count": 0,
        }
        existing.append(entry)
        ex_titles.add(t.lower())
        added += 1
    _save(existing)
    return added, skipped


def search(query: str = "", module_filter: str = "ALL",
           type_filter: str = "ALL") -> list:
    entries = _load()
    q = query.lower().strip()

    if not q and module_filter == "ALL" and type_filter == "ALL":
        return [(0, e) for e in sorted(entries, key=lambda x: -x.get("use_count", 0))]

    results = []
    for e in entries:
        if module_filter != "ALL" and e.get("module") != module_filter:
            continue
        if type_filter != "ALL" and e.get("category_type","Module") != type_filter:
            continue
        if not q:
            results.append((1, e))
            continue

        score        = 0.0
        title_l      = e.get("title","").lower()
        desc_l       = e.get("description","").lower()
        tags_l       = " ".join(e.get("tags",[])).lower()
        tables_upper = " ".join(e.get("tables",[]))
        sql_upper    = e.get("sql","").upper()

        if q == title_l:                                   score += 100
        elif q in title_l:                                 score += 30 + len(q)/max(len(title_l),1)*10
        qu = q.upper().replace(" ","_")
        if qu in tables_upper:                             score += 25
        if q in tags_l:                                    score += 20
        for tag in e.get("tags",[]):
            if q in tag.lower():                           score += 8
        if q in desc_l:                                    score += 10
        if qu in sql_upper:                                score += 8
        for w in [w for w in q.split() if len(w) > 2]:
            if w in title_l:                               score += 8
            if w in tags_l:                                score += 5
            if w.upper() in tables_upper:                  score += 6
            if w in desc_l:                                score += 3
            if w.upper() in sql_upper:                     score += 2
        if score >= 5:
            results.append((score, e))

    results.sort(key=lambda x: (-x[0], x[1].get("title","")))
    return results


def find_relevant(query: str, top_n: int = 3) -> list:
    results = search(query)
    return [e for sc, e in results[:top_n] if sc >= 5]


def get_stats() -> dict:
    entries = _load()
    modules = {}
    for e in entries:
        m = e.get("module","OTH")
        modules[m] = modules.get(m, 0) + 1
    return {
        "total":     len(entries),
        "modules":   modules,
        "most_used": sorted(entries, key=lambda x: x.get("use_count",0), reverse=True)[:5],
    }
