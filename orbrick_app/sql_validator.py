"""
sql_validator.py — Orbrick SQL Automation
Validates SQL against oracle_tables.json:
  - Table exists in catalog
  - Columns exist in that table
  - Suggests fixes for unknown columns
"""
import json, re
from pathlib import Path

BASE_DIR = Path(__file__).parent
CATALOG_FILE = BASE_DIR / "data" / "oracle_tables.json"

def load_catalog() -> dict:
    if CATALOG_FILE.exists():
        try:
            return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def validate_sql(sql: str) -> dict:
    """
    Validate SQL against oracle_tables.json.
    Returns dict with:
      - errors: list of definite problems
      - warnings: list of possible issues
      - info: list of informational notes
      - tables_found: list of (table, alias) pairs detected
      - score: 0-100 quality score
    """
    catalog = load_catalog()
    errors   = []
    warnings = []
    info     = []
    score    = 100

    if not sql.strip():
        return {"errors":[],"warnings":[],"info":[],"tables_found":[],"score":0}

    # ── Step 1: Extract table/alias pairs from FROM clause ──────────────
    clean = re.sub(r'--[^\n]*', '', sql)  # strip comments
    tables_found = []  # list of (table_name, alias)
    alias_to_table = {}

    from_match = re.search(
        r'\bFROM\b\s+(.*?)(?:\bWHERE\b|\bORDER\s+BY\b|\bGROUP\s+BY\b|$)',
        clean, re.I | re.DOTALL)

    TPREFIX = (
        'GL_','AP_','AR_','HZ_','PO_','POR_','RCV_','FA_','CE_','XLA_',
        'PER_','PAY_','HR_','RA_','FUN_','POZ_','PON_','PJF_','PJC_',
        'IBY_','ZX_','FND_','BEN_','OTA_','MTL_','ACN_','GMS_',
    )

    if from_match:
        for entry in from_match.group(1).split(','):
            parts = entry.strip().split()
            if not parts:
                continue
            tbl = parts[0].strip().upper()
            alias = parts[1].strip().upper() if len(parts) > 1 else tbl
            # Skip if not an Oracle table name
            if not any(tbl.startswith(p) for p in TPREFIX):
                continue
            tables_found.append((tbl, alias))
            alias_to_table[alias] = tbl

    # ── Step 2: Check each table against catalog ────────────────────────
    for tbl, alias in tables_found:
        if tbl in catalog:
            info.append(f"✅ {tbl} ({alias}) — found in catalog ({len(catalog[tbl]['columns'])} columns)")
        else:
            warnings.append(f"⚠ {tbl} ({alias}) — not in local catalog (may still be valid)")
            score -= 5

    # ── Step 3: Extract alias.COLUMN references and validate ───────────
    # Match: alias.COLUMN_NAME  (not inside comments, not in string literals)
    col_refs = re.findall(r'\b([A-Za-z][A-Za-z0-9_]*)\s*\.\s*([A-Z_][A-Z0-9_]+)\b', clean.upper())

    validated_cols   = []
    unknown_cols     = []
    unknown_alias    = []

    for alias, col in col_refs:
        # Skip common non-table aliases
        if alias in ('NVL','TO_DATE','TO_CHAR','TRUNC','ROUND','SUBSTR','UPPER','LOWER',
                     'COUNT','SUM','AVG','MIN','MAX','COALESCE','DECODE','CASE'):
            continue

        tbl = alias_to_table.get(alias)

        if tbl is None:
            # Alias not in FROM — might be subquery or CTE
            if alias not in [a for _,a in tables_found]:
                unknown_alias.append(f"  ⚠  {alias}.{col} — alias '{alias}' not found in FROM clause")
            continue

        if tbl not in catalog:
            # Table not in catalog — can't validate columns
            continue

        tbl_cols = catalog[tbl]["columns"]
        if col in tbl_cols:
            validated_cols.append(f"  ✅ {alias}.{col}")
        else:
            # Check if it's a known FK/common column not in our catalog slice
            COMMON_FK_COLS = {
                'CREATION_DATE','CREATED_BY','LAST_UPDATE_DATE','LAST_UPDATED_BY',
                'LAST_UPDATE_LOGIN','OBJECT_VERSION_NUMBER','ATTRIBUTE1','ATTRIBUTE2',
                'ATTRIBUTE3','ATTRIBUTE4','ATTRIBUTE5','ATTRIBUTE_CATEGORY',
                'REQUEST_ID','PROGRAM_APPLICATION_ID','PROGRAM_ID','PROGRAM_UPDATE_DATE',
                'ORG_ID','SET_OF_BOOKS_ID','LEGAL_ENTITY_ID','BUSINESS_GROUP_ID',
            }
            if col in COMMON_FK_COLS:
                info.append(f"  ℹ  {alias}.{col} — standard audit/FK column (not in catalog slice)")
            else:
                unknown_cols.append((alias, col, tbl))
                score -= 10

    # Report column issues
    for alias, col, tbl in unknown_cols:
        tbl_col_list = list(catalog[tbl]["columns"].keys())
        # Find close matches
        close = [c for c in tbl_col_list if col[:4] in c or c[:4] in col][:3]
        msg = f"❌ {alias}.{col} — column not found in {tbl}"
        if close:
            msg += f"\n     Did you mean: {', '.join(close)}?"
        errors.append(msg)

    if unknown_alias and len(unknown_alias) <= 3:
        warnings.extend(unknown_alias)

    # ── Step 4: Check GL-SLA link integrity ────────────────────────────
    has_gl = any(t in ('GL_JE_HEADERS','GL_JE_LINES') for t,_ in tables_found)
    has_xla= any(t in ('XLA_AE_HEADERS','XLA_AE_LINES') for t,_ in tables_found)
    has_gir= any(t == 'GL_IMPORT_REFERENCES' for t,_ in tables_found)

    if has_gl and has_xla and not has_gir:
        errors.append(
            "❌ GL + XLA tables present but GL_IMPORT_REFERENCES is missing!\n"
            "     GL → SLA requires: GL_JE_LINES → GL_IMPORT_REFERENCES → XLA_AE_LINES\n"
            "     Add: GL_IMPORT_REFERENCES gir to FROM clause\n"
            "     And: gir.JE_HEADER_ID(+) = jel.JE_HEADER_ID\n"
            "          gir.JE_LINE_NUM(+)   = jel.JE_LINE_NUM\n"
            "          gir.GL_SL_LINK_ID    = xal.GL_SL_LINK_ID"
        )
        score -= 20

    # ── Step 5: Check date-effective table filters ──────────────────────
    DATE_EFF_TABLES = {
        'PER_ALL_PEOPLE_F', 'PER_ALL_ASSIGNMENTS_M', 'PER_ALL_ASSIGNMENTS_F',
        'PER_PERSON_NAMES_F', 'PER_JOBS_F', 'PER_JOBS_F_TL',
        'HR_ALL_ORGANIZATION_UNITS_F', 'HR_ALL_POSITIONS_F',
        'PAY_ELEMENT_TYPES_F', 'PAY_INPUT_VALUES_F', 'PAY_ELEMENT_ENTRIES_F',
        'PAY_ELEMENT_ENTRY_VALUES_F', 'PAY_ALL_PAYROLLS_F',
    }
    sql_upper = sql.upper()
    for tbl, alias in tables_found:
        if tbl in DATE_EFF_TABLES:
            has_eff_filter = (
                f'{alias}.EFFECTIVE_START_DATE' in sql_upper or
                f'{alias}.EFFECTIVE_END_DATE' in sql_upper
            )
            if not has_eff_filter:
                warnings.append(
                    f"⚠ {tbl} ({alias}) is date-effective but has no EFFECTIVE_START/END_DATE filter.\n"
                    f"     Add: {alias}.EFFECTIVE_START_DATE <= SYSDATE\n"
                    f"          AND {alias}.EFFECTIVE_END_DATE >= SYSDATE"
                )
                score -= 5

    score = max(0, min(100, score))

    return {
        "errors":        errors,
        "warnings":      warnings,
        "info":          info,
        "validated_cols":validated_cols,
        "tables_found":  tables_found,
        "score":         score,
        "catalog_size":  len(catalog),
    }
