"""
sql_engine.py  —  Orbrick SQL Automation
Generates Oracle Fusion BIP SQL with correct (+) joins.
All columns validated against OTBI mapping + physical whitelist.
"""
import json, re
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Load OTBI data ─────────────────────────────────────────────────────────
with open(BASE_DIR / "data" / "subject_areas.json", encoding="utf-8") as f:
    SA_DATA = json.load(f)

with open(BASE_DIR / "data" / "tables.json", encoding="utf-8") as f:
    TBL_DATA = json.load(f)

# ── Physical column whitelist ──────────────────────────────────────────────
# Columns that exist in Oracle physical tables but are NOT in the OTBI mapping.
# These are FK/PK columns needed for joins and key report columns.
PHYS = {
    "GL_IMPORT_REFERENCES": {
                         "JE_BATCH_ID","JE_HEADER_ID","JE_LINE_NUM",
                         "GL_SL_LINK_ID","GL_SL_LINK_TABLE",
                         "REFERENCE_1","REFERENCE_2","REFERENCE_3",
                         "REFERENCE_4","REFERENCE_5","REFERENCE_6",
                         "REFERENCE_7","REFERENCE_8","REFERENCE_9",
                         "REFERENCE_10","ORIGINATING_TRANSACTION_DATE"},
    "XLA_TRANSACTION_ENTITIES": {
                         "ENTITY_ID","APPLICATION_ID","LEDGER_ID",
                         "ENTITY_CODE","TRANSACTION_NUMBER",
                         "SOURCE_ID_INT_1","SOURCE_ID_INT_2"},
    "GL_JE_HEADERS":   {"LEDGER_ID","JE_HEADER_ID","JE_BATCH_ID","PERIOD_NAME","NAME",
                         "STATUS","DESCRIPTION","JE_CATEGORY","JE_SOURCE","CURRENCY_CODE",
                         "DEFAULT_EFFECTIVE_DATE","POSTED_DATE","DATE_CREATED","ACTUAL_FLAG",
                         "CURRENCY_CONVERSION_RATE","RUNNING_TOTAL_DR","RUNNING_TOTAL_CR",
                         "RUNNING_TOTAL_ACCOUNTED_DR","RUNNING_TOTAL_ACCOUNTED_CR"},
    "GL_JE_LINES":     {"JE_HEADER_ID","JE_LINE_NUM","CODE_COMBINATION_ID","LEDGER_ID",
                         "PERIOD_NAME","EFFECTIVE_DATE","DESCRIPTION","ACCOUNTED_DR",
                         "ACCOUNTED_CR","ENTERED_DR","ENTERED_CR","CURRENCY_CODE",
                         "REFERENCE_1","REFERENCE_2","STAT_AMOUNT","LINE_TYPE_CODE",
                         "GL_SL_LINK_ID","GL_SL_LINK_TABLE","SUBLEDGER_DOC_SEQUENCE_VALUE"},
    "GL_CODE_COMBINATIONS": {"CODE_COMBINATION_ID","CHART_OF_ACCOUNTS_ID","LEDGER_ID",
                              "SEGMENT1","SEGMENT2","SEGMENT3","SEGMENT4","SEGMENT5",
                              "SEGMENT6","ACCOUNT_TYPE","ENABLED_FLAG","SUMMARY_FLAG",
                              "START_DATE_ACTIVE","END_DATE_ACTIVE","DESCRIPTION"},
    "GL_LEDGERS":      {"LEDGER_ID","NAME","SHORT_NAME","CURRENCY_CODE","DESCRIPTION",
                         "PERIOD_SET_NAME","LEDGER_CATEGORY_CODE","CHART_OF_ACCOUNTS_ID",
                         "OBJECT_TYPE_CODE","ACCOUNTED_PERIOD_TYPE"},
    "GL_BALANCES":     {"CODE_COMBINATION_ID","LEDGER_ID","PERIOD_NAME","CURRENCY_CODE",
                         "ACTUAL_FLAG","PERIOD_NET_DR","PERIOD_NET_CR",
                         "BEGIN_BALANCE_DR","BEGIN_BALANCE_CR","TRANSLATED_FLAG"},
    "FUN_ALL_BUSINESS_UNITS_V": {"BUSINESS_UNIT_ID","BU_NAME","NAME","STATUS",
                                   "DATE_FROM","DATE_TO","DEFAULT_CURRENCY_CODE"},
    "AP_INVOICES_ALL": {"INVOICE_ID","VENDOR_ID","VENDOR_SITE_ID","PARTY_ID","ORG_ID",
                         "SET_OF_BOOKS_ID","INVOICE_NUM","INVOICE_DATE","INVOICE_TYPE_LOOKUP_CODE",
                         "INVOICE_CURRENCY_CODE","INVOICE_AMOUNT","AMOUNT_PAID",
                         "PAYMENT_STATUS_FLAG","APPROVAL_STATUS","WFAPPROVAL_STATUS",
                         "GL_DATE","CANCELLED_DATE","DESCRIPTION","SOURCE","VOUCHER_NUM",
                         "TERMS_DATE","PAYMENT_CURRENCY_CODE","BASE_AMOUNT","EXCHANGE_RATE",
                         "ACCTS_PAY_CODE_COMBINATION_ID"},
    "AP_INVOICE_LINES_ALL":{"INVOICE_ID","LINE_NUMBER","LINE_TYPE_LOOKUP_CODE","AMOUNT",
                             "DESCRIPTION","ACCOUNTING_DATE","BASE_AMOUNT","PO_HEADER_ID",
                             "DIST_CODE_COMBINATION_ID"},
    "AP_INVOICE_DISTRIBUTIONS_ALL":{"INVOICE_ID","INVOICE_LINE_NUMBER","DISTRIBUTION_LINE_NUMBER",
                                    "DIST_CODE_COMBINATION_ID","LINE_TYPE_LOOKUP_CODE",
                                    "AMOUNT","ACCOUNTING_DATE","ORG_ID","BASE_AMOUNT"},
    "AP_CHECKS_ALL":   {"CHECK_ID","VENDOR_ID","VENDOR_SITE_ID","ORG_ID","CHECK_NUMBER",
                         "CHECK_DATE","CURRENCY_CODE","AMOUNT","BASE_AMOUNT",
                         "STATUS_LOOKUP_CODE","PAYMENT_TYPE_FLAG","BANK_ACCOUNT_NAME",
                         "CHECKRUN_NAME","CLEARED_DATE","CLEARED_AMOUNT","VOID_DATE",
                         "EXTERNAL_BANK_ACCOUNT_ID"},
    "AP_INVOICE_PAYMENTS_ALL":{"INVOICE_PAYMENT_ID","INVOICE_ID","CHECK_ID","PAYMENT_NUM",
                                "AMOUNT","DISCOUNT_TAKEN","ACCOUNTING_DATE","PERIOD_NAME",
                                "INVOICE_BASE_AMOUNT","PAYMENT_BASE_AMOUNT","ORG_ID"},
    "AP_HOLDS_ALL":    {"INVOICE_ID","HOLD_LOOKUP_CODE","HOLD_DATE","RELEASE_LOOKUP_CODE",
                         "RELEASE_DATE","HOLD_REASON"},
    "AP_PAYMENT_SCHEDULES_ALL":{"INVOICE_ID","PAYMENT_NUM","DUE_DATE","GROSS_AMOUNT",
                                 "AMOUNT_REMAINING","PAYMENT_STATUS_FLAG","SECOND_DISC_DATE"},
    "POZ_SUPPLIERS":   {"VENDOR_ID","PARTY_ID","SEGMENT1","VENDOR_TYPE_LOOKUP_CODE",
                         "ONE_TIME_FLAG","END_DATE_ACTIVE","FEDERAL_REPORTABLE_FLAG"},
    "POZ_SUPPLIER_SITES_ALL_M":{"VENDOR_ID","VENDOR_SITE_ID","VENDOR_SITE_CODE","ORG_ID",
                                 "CITY","STATE","COUNTRY","PAY_SITE_FLAG",
                                 "INVOICE_CURRENCY_CODE","PAYMENT_CURRENCY_CODE"},
    "HZ_PARTIES":      {"PARTY_ID","PARTY_NAME","PARTY_TYPE","PARTY_NUMBER",
                         "EMAIL_ADDRESS","ADDRESS1","CITY","COUNTRY","STATUS"},
    "HZ_CUST_ACCOUNTS":{"CUST_ACCOUNT_ID","PARTY_ID","ACCOUNT_NUMBER","ACCOUNT_NAME",
                         "CUSTOMER_CLASS_CODE","STATUS","CREDIT_LIMIT"},
    "HZ_CUST_SITE_USES_ALL":{"SITE_USE_ID","CUST_ACCT_SITE_ID","SITE_USE_CODE",
                               "PRIMARY_FLAG","STATUS","ORG_ID"},
    "HZ_CONTACT_POINTS":     {"CONTACT_POINT_ID","OWNER_TABLE_NAME","OWNER_TABLE_ID","PARTY_ID",
                              "CONTACT_POINT_TYPE","PRIMARY_FLAG","STATUS",
                              "EMAIL_ADDRESS","PHONE_NUMBER","PHONE_AREA_CODE",
                              "PHONE_COUNTRY_CODE","PHONE_LINE_TYPE","PHONE_EXTENSION",
                              "CONTACT_POINT_PURPOSE"},
    "HZ_LOCATIONS":          {"LOCATION_ID","ADDRESS1","ADDRESS2","ADDRESS3","ADDRESS4",
                              "CITY","STATE","PROVINCE","POSTAL_CODE","COUNTRY",
                              "COUNTY","DESCRIPTION"},
    "HZ_PARTY_SITES":        {"PARTY_SITE_ID","PARTY_ID","LOCATION_ID","PARTY_SITE_NUMBER",
                              "PARTY_SITE_NAME","IDENTIFYING_ADDRESS_FLAG","STATUS",
                              "START_DATE_ACTIVE","END_DATE_ACTIVE"},
    "HZ_PARTY_SITE_USES":    {"PARTY_SITE_USE_ID","PARTY_SITE_ID","SITE_USE_TYPE",
                              "PRIMARY_PER_TYPE","STATUS"},
    "HZ_CUSTOMER_PROFILES_F":{"CUST_ACCOUNT_ID","SITE_USE_ID","CREDIT_HOLD",
                              "CREDIT_LIMIT","CREDIT_CURRENCY_CODE","CREDIT_CHECKING",
                              "ACCOUNT_STATUS","CREDIT_CLASSIFICATION",
                              "EFFECTIVE_START_DATE","EFFECTIVE_END_DATE"},
    "HZ_CUST_ACCT_SITES_ALL":{"CUST_ACCT_SITE_ID","CUST_ACCOUNT_ID","PARTY_SITE_ID","ORG_ID"},
    "RA_CUSTOMER_TRX_ALL":{"CUSTOMER_TRX_ID","BILL_TO_CUSTOMER_ID","BILL_TO_SITE_USE_ID",
                            "SHIP_TO_CUSTOMER_ID","ORG_ID","SET_OF_BOOKS_ID","TRX_NUMBER",
                            "TRX_DATE","INVOICE_CURRENCY_CODE","COMPLETE_FLAG","EXCHANGE_RATE",
                            "EXCHANGE_RATE_TYPE","EXCHANGE_DATE","DOC_SEQUENCE_VALUE",
                            "COMMENTS","BILLING_DATE","TERM_ID","DUE_DATE"},
    "RA_CUSTOMER_TRX_LINES_ALL":{"CUSTOMER_TRX_LINE_ID","CUSTOMER_TRX_ID","LINE_NUMBER",
                                  "LINE_TYPE","DESCRIPTION","EXTENDED_AMOUNT","QUANTITY_INVOICED",
                                  "UNIT_SELLING_PRICE","REVENUE_AMOUNT","MEMO_LINE_ID"},
    "AR_ADJUSTMENTS_ALL":{"ADJUSTMENT_ID","CUSTOMER_TRX_ID","RECEIVABLES_TRX_ID",
                           "CODE_COMBINATION_ID","ORG_ID","ADJUSTMENT_NUMBER","ADJUSTMENT_TYPE",
                           "AMOUNT","APPLY_DATE","GL_DATE","REASON_CODE","STATUS",
                           "LINE_ADJUSTED","TAX_ADJUSTED","FREIGHT_ADJUSTED","POSTABLE","COMMENTS"},
    "AR_CASH_RECEIPTS_ALL":{"CASH_RECEIPT_ID","PAY_FROM_CUSTOMER","ORG_ID","RECEIPT_NUMBER",
                             "RECEIPT_DATE","AMOUNT","CURRENCY_CODE","STATUS","COMMENTS",
                             "DEPOSIT_DATE","DOC_SEQUENCE_VALUE","TYPE"},
    "AR_PAYMENT_SCHEDULES_ALL":{"PAYMENT_SCHEDULE_ID","CUSTOMER_ID","CUSTOMER_TRX_ID",
                                 "CASH_RECEIPT_ID","AMOUNT_DUE_ORIGINAL","AMOUNT_DUE_REMAINING",
                                 "AMOUNT_APPLIED","AMOUNT_ADJUSTED","DUE_DATE","CLASS",
                                 "STATUS","ACTUAL_DATE_CLOSED","TRX_NUMBER"},
    "XLA_AE_HEADERS":  {"AE_HEADER_ID","APPLICATION_ID","LEDGER_ID","EVENT_ID","ENTITY_ID",
                         "ACCOUNTING_DATE","PERIOD_NAME","ACCOUNTING_ENTRY_STATUS_CODE",
                         "BALANCE_TYPE_CODE","JE_CATEGORY_NAME","DESCRIPTION","EVENT_TYPE_CODE",
                         "DOC_SEQUENCE_VALUE","GL_TRANSFER_STATUS_CODE"},
    "XLA_AE_LINES":    {"AE_HEADER_ID","AE_LINE_NUM","APPLICATION_ID","CODE_COMBINATION_ID",
                         "GL_SL_LINK_ID","GL_SL_LINK_TABLE","CURRENCY_CODE","ACCOUNTING_DATE",
                         "ENTERED_DR","ENTERED_CR","ACCOUNTED_DR","ACCOUNTED_CR",
                         "ACCOUNTING_CLASS_CODE","DESCRIPTION","PARTY_ID"},
    "PO_HEADERS_ALL":  {"PO_HEADER_ID","SEGMENT1","TYPE_LOOKUP_CODE","VENDOR_ID",
                         "VENDOR_SITE_ID","ORG_ID","CURRENCY_CODE","AUTHORIZATION_STATUS",
                         "CREATION_DATE","APPROVED_DATE","COMMENTS","AMOUNT_AGREED","AGENT_ID"},
    "PO_LINES_ALL":    {"PO_LINE_ID","PO_HEADER_ID","LINE_NUM","ITEM_DESCRIPTION",
                         "UNIT_MEAS_LOOKUP_CODE","UNIT_PRICE","QUANTITY","AMOUNT","CANCEL_DATE"},
    "PO_LINE_LOCATIONS_ALL":{"LINE_LOCATION_ID","PO_LINE_ID","PO_HEADER_ID","SHIPMENT_NUM",
                              "QUANTITY","QUANTITY_RECEIVED","QUANTITY_BILLED",
                              "NEED_BY_DATE","PROMISED_DATE"},
    "PO_DISTRIBUTIONS_ALL":{"PO_DISTRIBUTION_ID","LINE_LOCATION_ID","PO_LINE_ID","PO_HEADER_ID",
                             "CODE_COMBINATION_ID","DISTRIBUTION_NUM","QUANTITY_ORDERED",
                             "AMOUNT_ORDERED","AMOUNT_BILLED","DESTINATION_TYPE_CODE"},
    "POR_REQUISITION_HEADERS_ALL":{"REQUISITION_HEADER_ID","ORG_ID","SEGMENT1",
                                    "AUTHORIZATION_STATUS","CREATION_DATE","DESCRIPTION"},
    "POR_REQUISITION_LINES_ALL":{"REQUISITION_LINE_ID","REQUISITION_HEADER_ID","LINE_NUM",
                                  "ITEM_DESCRIPTION","UNIT_PRICE","QUANTITY","NEED_BY_DATE"},
    "RCV_SHIPMENT_HEADERS":{"SHIPMENT_HEADER_ID","VENDOR_ID","ORG_ID","RECEIPT_NUM",
                             "SHIPMENT_NUM","RECEIPT_SOURCE_CODE","SHIPPED_DATE"},
    "RCV_SHIPMENT_LINES":{"SHIPMENT_LINE_ID","SHIPMENT_HEADER_ID","PO_HEADER_ID","LINE_NUM",
                           "QUANTITY_RECEIVED","QUANTITY_SHIPPED","ITEM_DESCRIPTION",
                           "UNIT_OF_MEASURE","DESTINATION_TYPE_CODE"},
    "FA_BOOKS":        {"ASSET_ID","BOOK_TYPE_CODE","COST","SALVAGE_VALUE","DATE_PLACED_IN_SERVICE",
                         "DEPRECIATE_FLAG","DEPRN_METHOD_CODE","LIFE_IN_MONTHS","ADJUSTED_COST",
                         "DATE_EFFECTIVE","DATE_INEFFECTIVE"},
    "FA_ADDITIONS_B":  {"ASSET_ID","ASSET_NUMBER","ASSET_TYPE","DESCRIPTION","CURRENT_UNITS",
                         "IN_USE_FLAG","OWNED_LEASED","MANUFACTURER_NAME","MODEL_NUMBER"},
    "FA_BOOK_CONTROLS":{"BOOK_TYPE_CODE","BOOK_TYPE_NAME","BOOK_CLASS"},
    "FA_DEPRN_SUMMARY":{"ASSET_ID","BOOK_TYPE_CODE","PERIOD_COUNTER","DEPRN_AMOUNT",
                         "YTD_DEPRN","DEPRN_RESERVE","COST","DEPRN_EXPENSE_ACCT_CCID"},
    "CE_STATEMENT_HEADERS":{"STATEMENT_HEADER_ID","BANK_ACCOUNT_ID","STATEMENT_NUMBER",
                             "STATEMENT_DATE","CONTROL_BEGIN_BALANCE","CONTROL_ENDING_BALANCE"},
    "CE_STATEMENT_LINES":{"STATEMENT_LINE_ID","STATEMENT_HEADER_ID","AMOUNT","BOOKING_DATE",
                           "TRX_DATE","FLOW_INDICATOR","CUSTOMER_REFERENCE"},
    "CE_BANK_ACCOUNTS":{"BANK_ACCOUNT_ID","BANK_PARTY_ID","BANK_ACCOUNT_NAME",
                         "MASKED_ACCOUNT_NUM","CURRENCY_CODE"},
    "PER_ALL_PEOPLE_F":{"PERSON_ID","PERSON_NUMBER","START_DATE","EFFECTIVE_START_DATE",
                         "EFFECTIVE_END_DATE","DATE_OF_BIRTH"},
    "PER_ALL_ASSIGNMENTS_M":{"PERSON_ID","ASSIGNMENT_ID","ASSIGNMENT_NUMBER","ORGANIZATION_ID",
                              "JOB_ID","POSITION_ID","BUSINESS_UNIT_ID","GRADE_ID",
                              "EMPLOYMENT_CATEGORY","ASSIGNMENT_TYPE","PRIMARY_FLAG",
                              "ASSIGNMENT_STATUS_TYPE","EFFECTIVE_START_DATE","EFFECTIVE_END_DATE",
                              "SYSTEM_PERSON_TYPE"},
    "PER_PERSON_NAMES_F_V":{"PERSON_ID","FULL_NAME","FIRST_NAME","LAST_NAME","DISPLAY_NAME",
                              "NAME_TYPE","EFFECTIVE_START_DATE","EFFECTIVE_END_DATE"},
    "HR_ALL_ORGANIZATION_UNITS_F":{"ORGANIZATION_ID","TYPE","EFFECTIVE_START_DATE","EFFECTIVE_END_DATE"},
    "HR_ORGANIZATION_UNITS_F_TL":{"ORGANIZATION_ID","NAME","LANGUAGE"},
    "PER_JOBS_F_TL":   {"JOB_ID","NAME","LANGUAGE"},
    "HR_ALL_POSITIONS_F_TL":{"POSITION_ID","NAME","LANGUAGE"},
    "PAY_PAYROLL_ACTIONS":{"PAYROLL_ACTION_ID","PAYROLL_ID","ACTION_TYPE","ACTION_STATUS",
                            "EFFECTIVE_DATE","DATE_EARNED","DISPLAY_RUN_NUMBER"},
    "PAY_ASSIGNMENT_ACTIONS":{"ASSIGNMENT_ACTION_ID","PAYROLL_ACTION_ID","ASSIGNMENT_ID",
                               "ACTION_STATUS"},
    "PAY_RUN_RESULTS":{"RUN_RESULT_ID","ASSIGNMENT_ACTION_ID","ELEMENT_TYPE_ID","STATUS"},
    "PAY_RUN_RESULT_VALUES":{"RUN_RESULT_VALUE_ID","RUN_RESULT_ID","INPUT_VALUE_ID","RESULT_VALUE"},
    "PAY_ELEMENT_TYPES_F":{"ELEMENT_TYPE_ID","ELEMENT_NAME","CLASSIFICATION_ID",
                            "EFFECTIVE_START_DATE","EFFECTIVE_END_DATE"},
    "PAY_INPUT_VALUES_F":{"INPUT_VALUE_ID","ELEMENT_TYPE_ID","NAME","UOM",
                           "EFFECTIVE_START_DATE","EFFECTIVE_END_DATE"},
    "PJF_PROJECTS_ALL_VL":{"PROJECT_ID","SEGMENT1","NAME","PROJECT_STATUS_CODE",
                            "START_DATE","COMPLETION_DATE","ORG_ID"},
    "PJF_TASKS_V":     {"TASK_ID","PROJECT_ID","TASK_NUMBER","TASK_NAME"},
    "PJC_EXP_ITEMS_ALL":{"EXPENDITURE_ITEM_ID","PROJECT_ID","TASK_ID","EXPENDITURE_ITEM_DATE",
                          "QUANTITY","DENOM_RAW_COST","DENOM_CURRENCY_CODE","ACCT_RAW_COST",
                          "SYSTEM_LINKAGE_FUNCTION"},
    "AR_RECEIVABLES_TRX_ALL":{"RECEIVABLES_TRX_ID","NAME","TYPE"},
}


def col_ok(tbl: str, col: str) -> bool:
    """True if column exists in OTBI mapping OR physical whitelist."""
    if col in TBL_DATA.get(tbl, {}).get("columns", []):
        return True
    return col in PHYS.get(tbl, set())


# ── FK relationships ───────────────────────────────────────────────────────
# (child_table, child_col, parent_table, parent_col, is_outer_join)
FK_MAP = [
    # GL
    ("GL_JE_LINES",    "JE_HEADER_ID",        "GL_JE_HEADERS",    "JE_HEADER_ID",        False),
    ("GL_JE_LINES",    "CODE_COMBINATION_ID",  "GL_CODE_COMBINATIONS","CODE_COMBINATION_ID",False),
    ("GL_JE_HEADERS",  "LEDGER_ID",            "GL_LEDGERS",       "LEDGER_ID",           False),
    # GL -> SLA via GL_IMPORT_REFERENCES (correct Oracle Fusion join chain)
    # gir outer-joins to jel: for each GL line get optional SLA reference
    ("GL_IMPORT_REFERENCES", "JE_HEADER_ID",  "GL_JE_LINES",  "JE_HEADER_ID",         True),
    ("GL_IMPORT_REFERENCES", "JE_LINE_NUM",   "GL_JE_LINES",  "JE_LINE_NUM",          True),
    ("GL_IMPORT_REFERENCES", "GL_SL_LINK_ID", "XLA_AE_LINES", "GL_SL_LINK_ID",        False),
    ("XLA_AE_HEADERS",       "ENTITY_ID",     "XLA_TRANSACTION_ENTITIES","ENTITY_ID", True),
    ("XLA_AE_LINES",   "AE_HEADER_ID",         "XLA_AE_HEADERS",   "AE_HEADER_ID",        False),
    ("XLA_AE_LINES",   "CODE_COMBINATION_ID",  "GL_CODE_COMBINATIONS","CODE_COMBINATION_ID",True),
    ("XLA_AE_HEADERS", "LEDGER_ID",            "GL_LEDGERS",       "LEDGER_ID",           True),
    ("GL_BALANCES",    "CODE_COMBINATION_ID",  "GL_CODE_COMBINATIONS","CODE_COMBINATION_ID",False),
    ("GL_BALANCES",    "LEDGER_ID",            "GL_LEDGERS",       "LEDGER_ID",           False),
    # AP
    ("AP_INVOICES_ALL","VENDOR_ID",            "POZ_SUPPLIERS",    "VENDOR_ID",           False),
    ("AP_INVOICES_ALL","VENDOR_SITE_ID",       "POZ_SUPPLIER_SITES_ALL_M","VENDOR_SITE_ID",True),
    ("AP_INVOICES_ALL","ORG_ID",               "FUN_ALL_BUSINESS_UNITS_V","BUSINESS_UNIT_ID",True),
    ("AP_INVOICES_ALL","SET_OF_BOOKS_ID",      "GL_LEDGERS",       "LEDGER_ID",           True),
    ("AP_INVOICE_LINES_ALL","INVOICE_ID",      "AP_INVOICES_ALL",  "INVOICE_ID",          True),
    ("AP_INVOICE_DISTRIBUTIONS_ALL","INVOICE_ID","AP_INVOICES_ALL","INVOICE_ID",          True),
    ("AP_INVOICE_DISTRIBUTIONS_ALL","INVOICE_LINE_NUMBER","AP_INVOICE_LINES_ALL","LINE_NUMBER",True),
    ("AP_INVOICE_DISTRIBUTIONS_ALL","DIST_CODE_COMBINATION_ID","GL_CODE_COMBINATIONS","CODE_COMBINATION_ID",True),
    ("AP_INVOICE_PAYMENTS_ALL","INVOICE_ID",   "AP_INVOICES_ALL",  "INVOICE_ID",          True),
    ("AP_INVOICE_PAYMENTS_ALL","CHECK_ID",     "AP_CHECKS_ALL",    "CHECK_ID",            False),
    ("AP_CHECKS_ALL",  "VENDOR_ID",            "POZ_SUPPLIERS",    "VENDOR_ID",           False),
    ("AP_CHECKS_ALL",  "ORG_ID",               "FUN_ALL_BUSINESS_UNITS_V","BUSINESS_UNIT_ID",True),
    ("AP_HOLDS_ALL",   "INVOICE_ID",           "AP_INVOICES_ALL",  "INVOICE_ID",          False),
    ("AP_PAYMENT_SCHEDULES_ALL","INVOICE_ID",  "AP_INVOICES_ALL",  "INVOICE_ID",          False),
    ("POZ_SUPPLIERS",  "PARTY_ID",             "HZ_PARTIES",       "PARTY_ID",            True),
    ("POZ_SUPPLIER_SITES_ALL_M","VENDOR_ID",   "POZ_SUPPLIERS",    "VENDOR_ID",           False),
    # AR
    ("RA_CUSTOMER_TRX_ALL","BILL_TO_CUSTOMER_ID","HZ_CUST_ACCOUNTS","CUST_ACCOUNT_ID",   False),
    ("RA_CUSTOMER_TRX_ALL","ORG_ID",           "FUN_ALL_BUSINESS_UNITS_V","BUSINESS_UNIT_ID",True),
    ("RA_CUSTOMER_TRX_ALL","SET_OF_BOOKS_ID",  "GL_LEDGERS",       "LEDGER_ID",           True),
    ("RA_CUSTOMER_TRX_LINES_ALL","CUSTOMER_TRX_ID","RA_CUSTOMER_TRX_ALL","CUSTOMER_TRX_ID",True),
    ("HZ_CUST_ACCOUNTS","PARTY_ID",            "HZ_PARTIES",       "PARTY_ID",            False),
    ("AR_ADJUSTMENTS_ALL","CUSTOMER_TRX_ID",   "RA_CUSTOMER_TRX_ALL","CUSTOMER_TRX_ID",  False),
    ("AR_ADJUSTMENTS_ALL","CODE_COMBINATION_ID","GL_CODE_COMBINATIONS","CODE_COMBINATION_ID",True),
    ("AR_ADJUSTMENTS_ALL","ORG_ID",            "FUN_ALL_BUSINESS_UNITS_V","BUSINESS_UNIT_ID",True),
    ("AR_CASH_RECEIPTS_ALL","PAY_FROM_CUSTOMER","HZ_CUST_ACCOUNTS","CUST_ACCOUNT_ID",    True),
    ("AR_CASH_RECEIPTS_ALL","ORG_ID",          "FUN_ALL_BUSINESS_UNITS_V","BUSINESS_UNIT_ID",True),
    ("AR_PAYMENT_SCHEDULES_ALL","CUSTOMER_TRX_ID","RA_CUSTOMER_TRX_ALL","CUSTOMER_TRX_ID",True),
    ("AR_PAYMENT_SCHEDULES_ALL","CUSTOMER_ID", "HZ_CUST_ACCOUNTS","CUST_ACCOUNT_ID",     True),
    # HZ Customer master FKs
    ("HZ_CUST_ACCT_SITES_ALL", "CUST_ACCOUNT_ID","HZ_CUST_ACCOUNTS","CUST_ACCOUNT_ID",   False),
    ("HZ_CUST_ACCT_SITES_ALL", "PARTY_SITE_ID",  "HZ_PARTY_SITES",  "PARTY_SITE_ID",    False),
    ("HZ_CUST_SITE_USES_ALL",  "CUST_ACCT_SITE_ID","HZ_CUST_ACCT_SITES_ALL","CUST_ACCT_SITE_ID",False),
    ("HZ_PARTY_SITES",         "PARTY_ID",        "HZ_PARTIES",      "PARTY_ID",         False),
    ("HZ_PARTY_SITES",         "LOCATION_ID",     "HZ_LOCATIONS",    "LOCATION_ID",      False),
    ("HZ_CONTACT_POINTS",      "OWNER_TABLE_ID",  "HZ_PARTIES",      "PARTY_ID",         False),
    ("HZ_CUSTOMER_PROFILES_F", "CUST_ACCOUNT_ID", "HZ_CUST_ACCOUNTS","CUST_ACCOUNT_ID",  True),
    # PO
    ("PO_HEADERS_ALL", "VENDOR_ID",            "POZ_SUPPLIERS",    "VENDOR_ID",           True),
    ("PO_HEADERS_ALL", "ORG_ID",               "FUN_ALL_BUSINESS_UNITS_V","BUSINESS_UNIT_ID",True),
    ("PO_LINES_ALL",   "PO_HEADER_ID",         "PO_HEADERS_ALL",   "PO_HEADER_ID",        False),
    ("PO_LINE_LOCATIONS_ALL","PO_LINE_ID",      "PO_LINES_ALL",     "PO_LINE_ID",          True),
    ("PO_DISTRIBUTIONS_ALL","PO_LINE_ID",       "PO_LINES_ALL",     "PO_LINE_ID",          True),
    ("PO_DISTRIBUTIONS_ALL","CODE_COMBINATION_ID","GL_CODE_COMBINATIONS","CODE_COMBINATION_ID",True),
    ("POR_REQUISITION_LINES_ALL","REQUISITION_HEADER_ID","POR_REQUISITION_HEADERS_ALL","REQUISITION_HEADER_ID",False),
    ("RCV_SHIPMENT_LINES","SHIPMENT_HEADER_ID", "RCV_SHIPMENT_HEADERS","SHIPMENT_HEADER_ID",False),
    ("RCV_SHIPMENT_LINES","PO_HEADER_ID",       "PO_HEADERS_ALL",   "PO_HEADER_ID",        True),
    # FA
    ("FA_BOOKS",       "ASSET_ID",             "FA_ADDITIONS_B",   "ASSET_ID",            False),
    ("FA_BOOKS",       "BOOK_TYPE_CODE",       "FA_BOOK_CONTROLS", "BOOK_TYPE_CODE",      False),
    ("FA_DEPRN_SUMMARY","ASSET_ID",            "FA_ADDITIONS_B",   "ASSET_ID",            False),
    ("FA_DEPRN_SUMMARY","BOOK_TYPE_CODE",      "FA_BOOK_CONTROLS", "BOOK_TYPE_CODE",      False),
    # CE
    ("CE_STATEMENT_LINES","STATEMENT_HEADER_ID","CE_STATEMENT_HEADERS","STATEMENT_HEADER_ID",False),
    ("CE_STATEMENT_HEADERS","BANK_ACCOUNT_ID",  "CE_BANK_ACCOUNTS", "BANK_ACCOUNT_ID",    False),
    # HCM
    ("PER_ALL_ASSIGNMENTS_M","PERSON_ID",        "PER_ALL_PEOPLE_F", "PERSON_ID",          False),
    ("PER_PERSON_NAMES_F_V","PERSON_ID",         "PER_ALL_PEOPLE_F", "PERSON_ID",          False),
    ("PER_ALL_ASSIGNMENTS_M","ORGANIZATION_ID",  "HR_ALL_ORGANIZATION_UNITS_F","ORGANIZATION_ID",True),
    ("HR_ORGANIZATION_UNITS_F_TL","ORGANIZATION_ID","HR_ALL_ORGANIZATION_UNITS_F","ORGANIZATION_ID",False),
    ("PER_ALL_ASSIGNMENTS_M","JOB_ID",           "PER_JOBS_F_TL",    "JOB_ID",             True),
    ("PER_ALL_ASSIGNMENTS_M","POSITION_ID",      "HR_ALL_POSITIONS_F_TL","POSITION_ID",    True),
    # Payroll
    ("PAY_ASSIGNMENT_ACTIONS","PAYROLL_ACTION_ID","PAY_PAYROLL_ACTIONS","PAYROLL_ACTION_ID",False),
    ("PAY_ASSIGNMENT_ACTIONS","ASSIGNMENT_ID",   "PER_ALL_ASSIGNMENTS_M","ASSIGNMENT_ID",  False),
    ("PAY_RUN_RESULTS","ASSIGNMENT_ACTION_ID",   "PAY_ASSIGNMENT_ACTIONS","ASSIGNMENT_ACTION_ID",False),
    ("PAY_RUN_RESULT_VALUES","RUN_RESULT_ID",    "PAY_RUN_RESULTS",  "RUN_RESULT_ID",      False),
    ("PAY_RUN_RESULTS","ELEMENT_TYPE_ID",        "PAY_ELEMENT_TYPES_F","ELEMENT_TYPE_ID",  True),
    ("PAY_RUN_RESULT_VALUES","INPUT_VALUE_ID",   "PAY_INPUT_VALUES_F","INPUT_VALUE_ID",    True),
    # Project
    ("PJC_EXP_ITEMS_ALL","PROJECT_ID",           "PJF_PROJECTS_ALL_VL","PROJECT_ID",       False),
    ("PJC_EXP_ITEMS_ALL","TASK_ID",              "PJF_TASKS_V",      "TASK_ID",            True),
]

# ── Key SELECT columns per table ───────────────────────────────────────────
# (alias, column, report_label)
KEY_COLS = {
    "GL_IMPORT_REFERENCES": [
        ("gir","GL_SL_LINK_ID","SL Link ID"),
        ("gir","GL_SL_LINK_TABLE","SL Link Table"),
        ("gir","REFERENCE_1","Reference 1"),
        ("gir","REFERENCE_2","Reference 2"),
        ("gir","REFERENCE_3","Reference 3"),
    ],
    "XLA_TRANSACTION_ENTITIES": [
        ("xte","ENTITY_CODE","Entity Code"),
        ("xte","TRANSACTION_NUMBER","Source Transaction"),
    ],
    "GL_JE_HEADERS": [
        ("jeh","PERIOD_NAME","Period"),
        ("jeh","JE_CATEGORY","Journal Category"),
        ("jeh","JE_SOURCE","Journal Source"),
        ("jeh","NAME","Journal Name"),
        ("jeh","DESCRIPTION","Journal Description"),
        ("jeh","STATUS","Status"),
        ("jeh","CURRENCY_CODE","Currency"),
        ("jeh","DEFAULT_EFFECTIVE_DATE","Effective Date"),
        ("jeh","ACTUAL_FLAG","Actual Flag"),
        ("jeh","POSTED_DATE","Posted Date"),
    ],
    "GL_JE_LINES": [
        ("jel","JE_LINE_NUM","Line Number"),
        ("jel","DESCRIPTION","Line Description"),
        ("jel","ACCOUNTED_DR","Accounted Debit"),
        ("jel","ACCOUNTED_CR","Accounted Credit"),
        ("jel","ENTERED_DR","Entered Debit"),
        ("jel","ENTERED_CR","Entered Credit"),
    ],
    "GL_CODE_COMBINATIONS": [
        ("gcc","SEGMENT1","Company"),
        ("gcc","SEGMENT2","Cost Center"),
        ("gcc","SEGMENT3","Account"),
        ("gcc","SEGMENT4","Sub Account"),
        ("gcc","SEGMENT5","Product"),
        ("gcc","CODE_COMBINATION_ID","CCID"),
        ("gcc","ACCOUNT_TYPE","Account Type"),
    ],
    "GL_LEDGERS": [
        ("gl","NAME","Ledger"),
        ("gl","CURRENCY_CODE","Ledger Currency"),
    ],
    "GL_BALANCES": [
        ("glb","PERIOD_NAME","Period"),
        ("glb","CURRENCY_CODE","Currency"),
        ("glb","ACTUAL_FLAG","Balance Type"),
        ("glb","PERIOD_NET_DR","Period Net Dr"),
        ("glb","PERIOD_NET_CR","Period Net Cr"),
        ("glb","BEGIN_BALANCE_DR","Begin Balance Dr"),
        ("glb","BEGIN_BALANCE_CR","Begin Balance Cr"),
    ],
    "XLA_AE_HEADERS": [
        ("xah","ACCOUNTING_DATE","SLA Accounting Date"),
        ("xah","PERIOD_NAME","SLA Period"),
        ("xah","ACCOUNTING_ENTRY_STATUS_CODE","SLA Status"),
        ("xah","JE_CATEGORY_NAME","SLA Category"),
        ("xah","EVENT_TYPE_CODE","Event Type"),
        ("xah","DESCRIPTION","SLA Description"),
    ],
    "XLA_AE_LINES": [
        ("xal","ACCOUNTED_DR","SLA Accounted Dr"),
        ("xal","ACCOUNTED_CR","SLA Accounted Cr"),
        ("xal","ENTERED_DR","SLA Entered Dr"),
        ("xal","ENTERED_CR","SLA Entered Cr"),
        ("xal","ACCOUNTING_CLASS_CODE","Accounting Class"),
        ("xal","DESCRIPTION","Line Description"),
    ],
    "FUN_ALL_BUSINESS_UNITS_V": [
        ("bu","BU_NAME","Business Unit"),
    ],
    "AP_INVOICES_ALL": [
        ("inv","INVOICE_NUM","Invoice Number"),
        ("inv","INVOICE_DATE","Invoice Date"),
        ("inv","INVOICE_TYPE_LOOKUP_CODE","Invoice Type"),
        ("inv","INVOICE_CURRENCY_CODE","Currency"),
        ("inv","INVOICE_AMOUNT","Invoice Amount"),
        ("inv","AMOUNT_PAID","Amount Paid"),
        ("inv","PAYMENT_STATUS_FLAG","Payment Status"),
        ("inv","APPROVAL_STATUS","Approval Status"),
        ("inv","GL_DATE","GL Date"),
        ("inv","CANCELLED_DATE","Cancelled Date"),
        ("inv","DESCRIPTION","Description"),
        ("inv","SOURCE","Source"),
        ("inv","VOUCHER_NUM","Voucher Number"),
        ("inv","TERMS_DATE","Terms Date"),
    ],
    "AP_INVOICE_LINES_ALL": [
        ("lin","LINE_NUMBER","Line Number"),
        ("lin","LINE_TYPE_LOOKUP_CODE","Line Type"),
        ("lin","AMOUNT","Line Amount"),
        ("lin","DESCRIPTION","Line Description"),
        ("lin","ACCOUNTING_DATE","Accounting Date"),
    ],
    "AP_INVOICE_DISTRIBUTIONS_ALL": [
        ("dist","DIST_CODE_COMBINATION_ID","CCID"),
        ("dist","AMOUNT","Distribution Amount"),
        ("dist","ACCOUNTING_DATE","Dist Accounting Date"),
        ("dist","LINE_TYPE_LOOKUP_CODE","Dist Type"),
    ],
    "AP_CHECKS_ALL": [
        ("chk","CHECK_NUMBER","Payment Number"),
        ("chk","CHECK_DATE","Payment Date"),
        ("chk","CURRENCY_CODE","Payment Currency"),
        ("chk","AMOUNT","Payment Amount"),
        ("chk","STATUS_LOOKUP_CODE","Payment Status"),
        ("chk","BANK_ACCOUNT_NAME","Bank Account"),
        ("chk","CHECKRUN_NAME","Payment Batch"),
        ("chk","CLEARED_DATE","Cleared Date"),
        ("chk","VOID_DATE","Void Date"),
    ],
    "AP_INVOICE_PAYMENTS_ALL": [
        ("pmt","PAYMENT_NUM","Payment Schedule"),
        ("pmt","AMOUNT","Payment Applied"),
        ("pmt","ACCOUNTING_DATE","Payment Accounting Date"),
    ],
    "AP_HOLDS_ALL": [
        ("hld","HOLD_LOOKUP_CODE","Hold Type"),
        ("hld","HOLD_DATE","Hold Date"),
        ("hld","RELEASE_LOOKUP_CODE","Release Type"),
        ("hld","RELEASE_DATE","Release Date"),
        ("hld","HOLD_REASON","Hold Reason"),
    ],
    "AP_PAYMENT_SCHEDULES_ALL": [
        ("ps","PAYMENT_NUM","Payment Schedule"),
        ("ps","DUE_DATE","Due Date"),
        ("ps","GROSS_AMOUNT","Gross Amount"),
        ("ps","AMOUNT_REMAINING","Amount Remaining"),
        ("ps","PAYMENT_STATUS_FLAG","Schedule Status"),
    ],
    "POZ_SUPPLIERS": [
        ("sup","SEGMENT1","Supplier Number"),
        ("sup","VENDOR_TYPE_LOOKUP_CODE","Supplier Type"),
    ],
    "HZ_PARTIES": [
        ("hz","PARTY_NAME","Supplier/Customer Name"),
        ("hz","PARTY_TYPE","Party Type"),
    ],
    "POZ_SUPPLIER_SITES_ALL_M": [
        ("site","VENDOR_SITE_CODE","Supplier Site"),
        ("site","CITY","City"),
        ("site","PAY_SITE_FLAG","Pay Site"),
        ("site","VENDOR_SITE_ID","Vendor Site ID"),
    ],
    "HZ_CONTACT_POINTS": [
        ("cp","CONTACT_POINT_TYPE","Contact Type"),
        ("cp","PRIMARY_FLAG","Primary"),
        ("cp","EMAIL_ADDRESS","Email"),
        ("cp","PHONE_NUMBER","Phone Number"),
        ("cp","PHONE_AREA_CODE","Area Code"),
        ("cp","PHONE_LINE_TYPE","Phone Type"),
        ("cp","CONTACT_POINT_PURPOSE","Purpose"),
    ],
    "HZ_LOCATIONS": [
        ("loc","ADDRESS1","Address Line 1"),
        ("loc","ADDRESS2","Address Line 2"),
        ("loc","CITY","City"),
        ("loc","STATE","State"),
        ("loc","POSTAL_CODE","Postal Code"),
        ("loc","COUNTRY","Country"),
        ("loc","COUNTY","County"),
    ],
    "HZ_PARTY_SITES": [
        ("ps","PARTY_SITE_NUMBER","Party Site Number"),
        ("ps","PARTY_SITE_NAME","Site Name"),
        ("ps","IDENTIFYING_ADDRESS_FLAG","Primary Address"),
        ("ps","STATUS","Status"),
    ],
    "HZ_CUSTOMER_PROFILES_F": [
        ("prof","CREDIT_HOLD","Credit Hold"),
        ("prof","CREDIT_LIMIT","Credit Limit"),
        ("prof","CREDIT_CURRENCY_CODE","Credit Currency"),
        ("prof","CREDIT_CHECKING","Credit Checking"),
        ("prof","ACCOUNT_STATUS","Account Status"),
        ("prof","CREDIT_CLASSIFICATION","Credit Classification"),
    ],
    "HZ_CUST_ACCOUNTS": [
        ("cust","ACCOUNT_NUMBER","Customer Account Number"),
        ("cust","ACCOUNT_NAME","Customer Account Name"),
        ("cust","CUSTOMER_CLASS_CODE","Customer Class"),
        ("cust","STATUS","Customer Status"),
    ],
    "RA_CUSTOMER_TRX_ALL": [
        ("trx","TRX_NUMBER","Transaction Number"),
        ("trx","TRX_DATE","Transaction Date"),
        ("trx","INVOICE_CURRENCY_CODE","Currency"),
        ("trx","EXCHANGE_RATE","Exchange Rate"),
        ("trx","COMPLETE_FLAG","Complete"),
        ("trx","COMMENTS","Comments"),
        ("trx","BILLING_DATE","Billing Date"),
        ("trx","DUE_DATE","Due Date"),
        ("trx","DOC_SEQUENCE_VALUE","Document Number"),
    ],
    "RA_CUSTOMER_TRX_LINES_ALL": [
        ("trl","LINE_NUMBER","Line Number"),
        ("trl","LINE_TYPE","Line Type"),
        ("trl","DESCRIPTION","Line Description"),
        ("trl","EXTENDED_AMOUNT","Line Amount"),
        ("trl","QUANTITY_INVOICED","Quantity"),
        ("trl","UNIT_SELLING_PRICE","Unit Price"),
    ],
    "AR_ADJUSTMENTS_ALL": [
        ("adj","ADJUSTMENT_NUMBER","Adjustment Number"),
        ("adj","ADJUSTMENT_TYPE","Adjustment Type"),
        ("adj","AMOUNT","Adjustment Amount"),
        ("adj","APPLY_DATE","Apply Date"),
        ("adj","GL_DATE","GL Date"),
        ("adj","REASON_CODE","Reason Code"),
        ("adj","STATUS","Status"),
        ("adj","LINE_ADJUSTED","Line Adjusted"),
        ("adj","TAX_ADJUSTED","Tax Adjusted"),
        ("adj","COMMENTS","Comments"),
    ],
    "AR_CASH_RECEIPTS_ALL": [
        ("rcpt","RECEIPT_NUMBER","Receipt Number"),
        ("rcpt","RECEIPT_DATE","Receipt Date"),
        ("rcpt","AMOUNT","Receipt Amount"),
        ("rcpt","CURRENCY_CODE","Currency"),
        ("rcpt","STATUS","Status"),
        ("rcpt","TYPE","Receipt Type"),
        ("rcpt","DEPOSIT_DATE","Deposit Date"),
        ("rcpt","COMMENTS","Comments"),
    ],
    "AR_PAYMENT_SCHEDULES_ALL": [
        ("ps","TRX_NUMBER","Transaction Number"),
        ("ps","DUE_DATE","Due Date"),
        ("ps","CLASS","Class"),
        ("ps","AMOUNT_DUE_ORIGINAL","Original Amount"),
        ("ps","AMOUNT_DUE_REMAINING","Amount Remaining"),
        ("ps","AMOUNT_APPLIED","Amount Applied"),
        ("ps","AMOUNT_ADJUSTED","Amount Adjusted"),
        ("ps","STATUS","Status"),
        ("ps","ACTUAL_DATE_CLOSED","Close Date"),
    ],
    "PO_HEADERS_ALL": [
        ("poh","SEGMENT1","PO Number"),
        ("poh","TYPE_LOOKUP_CODE","PO Type"),
        ("poh","CURRENCY_CODE","Currency"),
        ("poh","AUTHORIZATION_STATUS","Status"),
        ("poh","CREATION_DATE","Creation Date"),
        ("poh","APPROVED_DATE","Approved Date"),
        ("poh","COMMENTS","Comments"),
    ],
    "PO_LINES_ALL": [
        ("pol","LINE_NUM","Line Number"),
        ("pol","ITEM_DESCRIPTION","Item Description"),
        ("pol","UNIT_MEAS_LOOKUP_CODE","UOM"),
        ("pol","UNIT_PRICE","Unit Price"),
        ("pol","QUANTITY","Quantity"),
        ("pol","AMOUNT","Amount"),
    ],
    "PO_LINE_LOCATIONS_ALL": [
        ("pll","SHIPMENT_NUM","Shipment Number"),
        ("pll","QUANTITY","Ordered Qty"),
        ("pll","QUANTITY_RECEIVED","Received Qty"),
        ("pll","QUANTITY_BILLED","Billed Qty"),
        ("pll","NEED_BY_DATE","Need By Date"),
        ("pll","PROMISED_DATE","Promised Date"),
    ],
    "POR_REQUISITION_HEADERS_ALL": [
        ("prh","SEGMENT1","Requisition Number"),
        ("prh","AUTHORIZATION_STATUS","Status"),
        ("prh","CREATION_DATE","Creation Date"),
        ("prh","DESCRIPTION","Description"),
    ],
    "POR_REQUISITION_LINES_ALL": [
        ("prl","LINE_NUM","Line Number"),
        ("prl","ITEM_DESCRIPTION","Item Description"),
        ("prl","UNIT_PRICE","Unit Price"),
        ("prl","QUANTITY","Quantity"),
        ("prl","NEED_BY_DATE","Need By Date"),
    ],
    "RCV_SHIPMENT_HEADERS": [
        ("rsh","RECEIPT_NUM","Receipt Number"),
        ("rsh","SHIPPED_DATE","Shipped Date"),
        ("rsh","RECEIPT_SOURCE_CODE","Source"),
    ],
    "RCV_SHIPMENT_LINES": [
        ("rsl","LINE_NUM","Line Number"),
        ("rsl","ITEM_DESCRIPTION","Item Description"),
        ("rsl","QUANTITY_RECEIVED","Qty Received"),
        ("rsl","QUANTITY_SHIPPED","Qty Shipped"),
        ("rsl","UNIT_OF_MEASURE","UOM"),
        ("rsl","DESTINATION_TYPE_CODE","Destination"),
    ],
    "FA_BOOKS": [
        ("fab","BOOK_TYPE_CODE","Book"),
        ("fab","COST","Cost"),
        ("fab","SALVAGE_VALUE","Salvage Value"),
        ("fab","DATE_PLACED_IN_SERVICE","Date in Service"),
        ("fab","DEPRN_METHOD_CODE","Depreciation Method"),
        ("fab","LIFE_IN_MONTHS","Life (Months)"),
        ("fab","ADJUSTED_COST","Adjusted Cost"),
    ],
    "FA_ADDITIONS_B": [
        ("faa","ASSET_NUMBER","Asset Number"),
        ("faa","ASSET_TYPE","Asset Type"),
        ("faa","DESCRIPTION","Asset Description"),
        ("faa","CURRENT_UNITS","Units"),
        ("faa","MANUFACTURER_NAME","Manufacturer"),
    ],
    "FA_BOOK_CONTROLS": [
        ("fbc","BOOK_TYPE_NAME","Book Name"),
        ("fbc","BOOK_CLASS","Book Class"),
    ],
    "FA_DEPRN_SUMMARY": [
        ("fds","DEPRN_AMOUNT","Depreciation Amount"),
        ("fds","YTD_DEPRN","YTD Depreciation"),
        ("fds","DEPRN_RESERVE","Accumulated Depreciation"),
        ("fds","COST","Cost"),
    ],
    "CE_STATEMENT_HEADERS": [
        ("csh","STATEMENT_NUMBER","Statement Number"),
        ("csh","STATEMENT_DATE","Statement Date"),
        ("csh","CONTROL_BEGIN_BALANCE","Opening Balance"),
        ("csh","CONTROL_ENDING_BALANCE","Closing Balance"),
    ],
    "CE_STATEMENT_LINES": [
        ("csl","AMOUNT","Amount"),
        ("csl","BOOKING_DATE","Booking Date"),
        ("csl","TRX_DATE","Transaction Date"),
        ("csl","FLOW_INDICATOR","Flow"),
        ("csl","CUSTOMER_REFERENCE","Reference"),
    ],
    "CE_BANK_ACCOUNTS": [
        ("cba","BANK_ACCOUNT_NAME","Bank Account"),
        ("cba","MASKED_ACCOUNT_NUM","Account Number"),
        ("cba","CURRENCY_CODE","Currency"),
    ],
    "PER_ALL_PEOPLE_F": [
        ("ppl","PERSON_NUMBER","Person Number"),
        ("ppl","START_DATE","Start Date"),
        ("ppl","DATE_OF_BIRTH","Date of Birth"),
    ],
    "PER_PERSON_NAMES_F_V": [
        ("pnm","FULL_NAME","Employee Name"),
        ("pnm","FIRST_NAME","First Name"),
        ("pnm","LAST_NAME","Last Name"),
    ],
    "PER_ALL_ASSIGNMENTS_M": [
        ("asg","ASSIGNMENT_NUMBER","Assignment Number"),
        ("asg","EMPLOYMENT_CATEGORY","Employment Category"),
        ("asg","ASSIGNMENT_STATUS_TYPE","Assignment Status"),
        ("asg","PRIMARY_FLAG","Primary"),
        ("asg","EFFECTIVE_START_DATE","Effective Start Date"),
        ("asg","EFFECTIVE_END_DATE","Effective End Date"),
        ("asg","SYSTEM_PERSON_TYPE","Person Type"),
    ],
    "HR_ORGANIZATION_UNITS_F_TL": [
        ("org","NAME","Organization Name"),
    ],
    "PER_JOBS_F_TL": [
        ("job","NAME","Job Name"),
    ],
    "HR_ALL_POSITIONS_F_TL": [
        ("pos","NAME","Position Name"),
    ],
    "PAY_PAYROLL_ACTIONS": [
        ("pya","DISPLAY_RUN_NUMBER","Payroll Run Number"),
        ("pya","EFFECTIVE_DATE","Payroll Effective Date"),
        ("pya","DATE_EARNED","Date Earned"),
        ("pya","ACTION_TYPE","Action Type"),
        ("pya","ACTION_STATUS","Action Status"),
    ],
    "PAY_ELEMENT_TYPES_F": [
        ("elt","ELEMENT_NAME","Element Name"),
    ],
    "PAY_INPUT_VALUES_F": [
        ("inv","NAME","Input Value Name"),
    ],
    "PAY_RUN_RESULT_VALUES": [
        ("rrv","RESULT_VALUE","Result Value"),
    ],
    "PJF_PROJECTS_ALL_VL": [
        ("prj","SEGMENT1","Project Number"),
        ("prj","NAME","Project Name"),
        ("prj","PROJECT_STATUS_CODE","Project Status"),
        ("prj","START_DATE","Project Start Date"),
        ("prj","COMPLETION_DATE","Project End Date"),
    ],
    "PJF_TASKS_V": [
        ("tsk","TASK_NUMBER","Task Number"),
        ("tsk","TASK_NAME","Task Name"),
    ],
    "PJC_EXP_ITEMS_ALL": [
        ("exp","EXPENDITURE_ITEM_DATE","Expenditure Date"),
        ("exp","QUANTITY","Quantity"),
        ("exp","DENOM_RAW_COST","Raw Cost"),
        ("exp","DENOM_CURRENCY_CODE","Currency"),
        ("exp","ACCT_RAW_COST","Accounted Cost"),
        ("exp","SYSTEM_LINKAGE_FUNCTION","Expenditure Type"),
    ],
}

# ── WHERE clause templates ─────────────────────────────────────────────────
WHERE_EXTRA = {
    "GL_JE_HEADERS": (
        "jeh.DEFAULT_EFFECTIVE_DATE >= NVL(TO_DATE(:P_START_DATE,'YYYY/MM/DD'), jeh.DEFAULT_EFFECTIVE_DATE)\n"
        "jeh.DEFAULT_EFFECTIVE_DATE <= NVL(TO_DATE(:P_END_DATE,'YYYY/MM/DD'),   jeh.DEFAULT_EFFECTIVE_DATE)\n"
        "jeh.LEDGER_ID           = NVL(:P_LEDGER_ID, jeh.LEDGER_ID)\n"
        "jeh.STATUS              = 'P'"
    ),
    "GL_BALANCES": (
        "glb.PERIOD_NAME  = NVL(:P_PERIOD_NAME, glb.PERIOD_NAME)\n"
        "glb.ACTUAL_FLAG   = 'A'\n"
        "glb.CURRENCY_CODE = 'USD'"
    ),
    "AP_INVOICES_ALL": (
        "inv.INVOICE_DATE >= NVL(TO_DATE(:P_START_DATE,'YYYY/MM/DD'), inv.INVOICE_DATE)\n"
        "inv.INVOICE_DATE <= NVL(TO_DATE(:P_END_DATE,'YYYY/MM/DD'),   inv.INVOICE_DATE)\n"
        "inv.ORG_ID        = NVL(:P_ORG_ID, inv.ORG_ID)\n"
        "inv.CANCELLED_DATE IS NULL"
    ),
    "AP_CHECKS_ALL": (
        "chk.CHECK_DATE >= NVL(TO_DATE(:P_START_DATE,'YYYY/MM/DD'), chk.CHECK_DATE)\n"
        "chk.CHECK_DATE <= NVL(TO_DATE(:P_END_DATE,'YYYY/MM/DD'),   chk.CHECK_DATE)\n"
        "chk.ORG_ID      = NVL(:P_ORG_ID, chk.ORG_ID)\n"
        "chk.STATUS_LOOKUP_CODE NOT IN ('VOIDED')"
    ),
    "RA_CUSTOMER_TRX_ALL": (
        "trx.TRX_DATE >= NVL(TO_DATE(:P_START_DATE,'YYYY/MM/DD'), trx.TRX_DATE)\n"
        "trx.TRX_DATE <= NVL(TO_DATE(:P_END_DATE,'YYYY/MM/DD'),   trx.TRX_DATE)\n"
        "trx.ORG_ID    = NVL(:P_ORG_ID, trx.ORG_ID)\n"
        "trx.COMPLETE_FLAG = 'Y'"
    ),
    "AR_ADJUSTMENTS_ALL": (
        "adj.APPLY_DATE >= NVL(TO_DATE(:P_START_DATE,'YYYY/MM/DD'), adj.APPLY_DATE)\n"
        "adj.APPLY_DATE <= NVL(TO_DATE(:P_END_DATE,'YYYY/MM/DD'),   adj.APPLY_DATE)\n"
        "adj.ORG_ID      = NVL(:P_ORG_ID, adj.ORG_ID)\n"
        "adj.STATUS      = 'A'"
    ),
    "AR_CASH_RECEIPTS_ALL": (
        "rcpt.RECEIPT_DATE >= NVL(TO_DATE(:P_START_DATE,'YYYY/MM/DD'), rcpt.RECEIPT_DATE)\n"
        "rcpt.RECEIPT_DATE <= NVL(TO_DATE(:P_END_DATE,'YYYY/MM/DD'),   rcpt.RECEIPT_DATE)\n"
        "rcpt.ORG_ID        = NVL(:P_ORG_ID, rcpt.ORG_ID)"
    ),
    "PO_HEADERS_ALL": (
        "poh.CREATION_DATE >= NVL(TO_DATE(:P_START_DATE,'YYYY/MM/DD'), poh.CREATION_DATE)\n"
        "poh.CREATION_DATE <= NVL(TO_DATE(:P_END_DATE,'YYYY/MM/DD'),   poh.CREATION_DATE)\n"
        "poh.ORG_ID         = NVL(:P_ORG_ID, poh.ORG_ID)\n"
        "poh.AUTHORIZATION_STATUS = 'APPROVED'"
    ),
    "PER_ALL_PEOPLE_F": (
        "ppl.EFFECTIVE_START_DATE <= SYSDATE\n"
        "ppl.EFFECTIVE_END_DATE   >= SYSDATE\n"
        "asg.EFFECTIVE_START_DATE <= SYSDATE\n"
        "asg.EFFECTIVE_END_DATE   >= SYSDATE\n"
        "asg.PRIMARY_FLAG         = 'Y'\n"
        "pnm.EFFECTIVE_START_DATE <= SYSDATE\n"
        "pnm.EFFECTIVE_END_DATE   >= SYSDATE\n"
        "pnm.NAME_TYPE            = 'GLOBAL'"
    ),
    "PAY_PAYROLL_ACTIONS": (
        "pya.EFFECTIVE_DATE >= NVL(TO_DATE(:P_START_DATE,'YYYY/MM/DD'), pya.EFFECTIVE_DATE)\n"
        "pya.EFFECTIVE_DATE <= NVL(TO_DATE(:P_END_DATE,'YYYY/MM/DD'),   pya.EFFECTIVE_DATE)\n"
        "pya.ACTION_TYPE IN ('R','Q','B')\n"
        "pya.ACTION_STATUS = 'C'"
    ),
    "CE_STATEMENT_HEADERS": (
        "csh.STATEMENT_DATE >= NVL(TO_DATE(:P_START_DATE,'YYYY/MM/DD'), csh.STATEMENT_DATE)\n"
        "csh.STATEMENT_DATE <= NVL(TO_DATE(:P_END_DATE,'YYYY/MM/DD'),   csh.STATEMENT_DATE)"
    ),
    "FA_BOOKS": (
        "fab.DATE_INEFFECTIVE IS NULL\n"
        "fab.DEPRECIATE_FLAG = 'YES'"
    ),
    "HZ_CUST_ACCOUNTS": (
        "cust.STATUS = 'A'"
    ),
    "PJF_PROJECTS_ALL_VL": (
        "prj.PROJECT_STATUS_CODE = NVL(:P_PROJECT_STATUS, prj.PROJECT_STATUS_CODE)\n"
        "prj.ORG_ID            = NVL(:P_ORG_ID, prj.ORG_ID)"
    ),
}

ORDER_BY = {
    "GL_JE_HEADERS":     "jeh.PERIOD_NAME, jeh.DEFAULT_EFFECTIVE_DATE, jeh.NAME, jel.JE_LINE_NUM",
    "GL_BALANCES":       "gcc.SEGMENT1, gcc.SEGMENT2, gcc.SEGMENT3",
    "AP_INVOICES_ALL":   "inv.INVOICE_DATE, sup.SEGMENT1, inv.INVOICE_NUM",
    "AP_CHECKS_ALL":     "chk.CHECK_DATE, chk.CHECK_NUMBER",
    "RA_CUSTOMER_TRX_ALL": "trx.TRX_DATE, cust.ACCOUNT_NUMBER, trx.TRX_NUMBER",
    "AR_ADJUSTMENTS_ALL":  "adj.APPLY_DATE, trx.TRX_NUMBER",
    "AR_CASH_RECEIPTS_ALL":"rcpt.RECEIPT_DATE, cust.ACCOUNT_NUMBER",
    "PO_HEADERS_ALL":    "poh.CREATION_DATE, sup.SEGMENT1, poh.SEGMENT1",
    "PER_ALL_PEOPLE_F":  "pnm.LAST_NAME, pnm.FIRST_NAME",
    "PAY_PAYROLL_ACTIONS":"pya.EFFECTIVE_DATE, pya.DISPLAY_RUN_NUMBER",
    "CE_STATEMENT_HEADERS":"csh.STATEMENT_DATE",
    "FA_BOOKS":          "faa.ASSET_NUMBER",
    "PJF_PROJECTS_ALL_VL":"prj.SEGMENT1",
    "XLA_AE_HEADERS":    "xah.ACCOUNTING_DATE, xal.AE_LINE_NUM",
}

# ── Intent map ─────────────────────────────────────────────────────────────
# (keyword_list, driver_table, extra_tables)
INTENT_MAP = [
    # AP
    (["ap invoice","payable invoice","invoice payable","accounts payable invoice","ap invoice and payment","invoice and payment"],
     "AP_INVOICES_ALL",
     ["AP_INVOICE_LINES_ALL","AP_INVOICE_DISTRIBUTIONS_ALL","POZ_SUPPLIERS","HZ_PARTIES",
      "POZ_SUPPLIER_SITES_ALL_M","GL_CODE_COMBINATIONS","GL_LEDGERS","FUN_ALL_BUSINESS_UNITS_V"]),

    (["ap payment","payable payment","ap check","vendor payment","payment check","check payment","and payment","with payment"],
     "AP_CHECKS_ALL",
     ["AP_INVOICE_PAYMENTS_ALL","POZ_SUPPLIERS","HZ_PARTIES","FUN_ALL_BUSINESS_UNITS_V",
      "CE_BANK_ACCOUNTS"]),

    (["ap hold","invoice hold","payable hold"],
     "AP_INVOICES_ALL",
     ["AP_HOLDS_ALL","POZ_SUPPLIERS","HZ_PARTIES"]),

    (["payment schedule","invoice installment","ap installment"],
     "AP_INVOICES_ALL",
     ["AP_PAYMENT_SCHEDULES_ALL","POZ_SUPPLIERS","HZ_PARTIES"]),

    # AR
    (["ar invoice","ar transaction","customer invoice","customer transaction",
      "receivable invoice","receivable transaction","ra customer","ar customer",
      "customer trx","ar trx"],
     "RA_CUSTOMER_TRX_ALL",
     ["RA_CUSTOMER_TRX_LINES_ALL","HZ_CUST_ACCOUNTS","HZ_PARTIES",
      "GL_LEDGERS","FUN_ALL_BUSINESS_UNITS_V"]),

    (["ar adjustment","receivable adjustment","transaction adjustment"],
     "AR_ADJUSTMENTS_ALL",
     ["RA_CUSTOMER_TRX_ALL","HZ_CUST_ACCOUNTS","HZ_PARTIES",
      "GL_CODE_COMBINATIONS","FUN_ALL_BUSINESS_UNITS_V"]),

    (["ar receipt","cash receipt","receivable receipt","customer receipt"],
     "AR_CASH_RECEIPTS_ALL",
     ["HZ_CUST_ACCOUNTS","HZ_PARTIES","FUN_ALL_BUSINESS_UNITS_V"]),

    # Customer master, contact points, addresses, profiles
    (["customer detail","customer master","customer information","customer data",
      "customer contact","contact point","customer address","customer profile",
      "customer account detail","hz party","hz cust","customer values",
      "customer phone","customer email","customer site","party detail",
      "customer name","account detail"],
     "HZ_CUST_ACCOUNTS",
     ["HZ_PARTIES","HZ_PARTY_SITES","HZ_LOCATIONS","HZ_CONTACT_POINTS",
      "HZ_CUSTOMER_PROFILES_F","HZ_CUST_ACCT_SITES_ALL","HZ_CUST_SITE_USES_ALL"]),

    (["ar aging","customer aging","receivable aging"],
     "AR_PAYMENT_SCHEDULES_ALL",
     ["RA_CUSTOMER_TRX_ALL","HZ_CUST_ACCOUNTS","HZ_PARTIES"]),

    # GL
    (["gl journal","journal entry","journal line","gl entry"],
     "GL_JE_HEADERS",
     ["GL_JE_LINES","GL_CODE_COMBINATIONS","GL_LEDGERS"]),

    (["gl journal sla","journal subledger","gl sla","journal with sla",
      "subledger journal","code combination sla","journal sla",
      "gl import references","subledger accounting journal"],
     "GL_JE_HEADERS",
     ["GL_JE_LINES","GL_IMPORT_REFERENCES","GL_CODE_COMBINATIONS",
      "GL_LEDGERS","XLA_AE_HEADERS","XLA_AE_LINES","XLA_TRANSACTION_ENTITIES"]),

    (["gl balance","account balance","trial balance","gl account balance"],
     "GL_BALANCES",
     ["GL_CODE_COMBINATIONS","GL_LEDGERS"]),

    (["subledger accounting","sla accounting","xla","xla accounting"],
     "XLA_AE_HEADERS",
     ["XLA_AE_LINES","GL_CODE_COMBINATIONS","GL_LEDGERS"]),

    # PO
    (["purchase order","po header","po approval","po line","blanket po"],
     "PO_HEADERS_ALL",
     ["PO_LINES_ALL","PO_LINE_LOCATIONS_ALL","POZ_SUPPLIERS","HZ_PARTIES",
      "FUN_ALL_BUSINESS_UNITS_V"]),

    (["po distribution","purchase distribution","po accounting"],
     "PO_HEADERS_ALL",
     ["PO_LINES_ALL","PO_DISTRIBUTIONS_ALL","GL_CODE_COMBINATIONS","POZ_SUPPLIERS"]),

    (["requisition","purchase requisition","pr line"],
     "POR_REQUISITION_HEADERS_ALL",
     ["POR_REQUISITION_LINES_ALL","FUN_ALL_BUSINESS_UNITS_V"]),

    (["po receipt","receiving","goods receipt","receipt po"],
     "RCV_SHIPMENT_HEADERS",
     ["RCV_SHIPMENT_LINES","PO_HEADERS_ALL","POZ_SUPPLIERS"]),

    # HCM
    (["employee","worker detail","person detail","employee list","staff"],
     "PER_ALL_PEOPLE_F",
     ["PER_PERSON_NAMES_F_V","PER_ALL_ASSIGNMENTS_M","HR_ORGANIZATION_UNITS_F_TL",
      "PER_JOBS_F_TL"]),

    (["employee salary","salary detail","compensation","pay element","payslip"],
     "PER_ALL_PEOPLE_F",
     ["PER_PERSON_NAMES_F_V","PER_ALL_ASSIGNMENTS_M","PAY_ASSIGNMENT_ACTIONS",
      "PAY_RUN_RESULTS","PAY_RUN_RESULT_VALUES","PAY_ELEMENT_TYPES_F","PAY_INPUT_VALUES_F"]),

    (["payroll run","payroll result","payroll action"],
     "PAY_PAYROLL_ACTIONS",
     ["PAY_ASSIGNMENT_ACTIONS","PER_ALL_ASSIGNMENTS_M","PER_PERSON_NAMES_F_V"]),

    # FA
    (["fixed asset","asset addition","capital asset","fa asset"],
     "FA_BOOKS",
     ["FA_ADDITIONS_B","FA_BOOK_CONTROLS"]),

    (["asset depreciation","depreciation","fa deprn","asset deprn"],
     "FA_DEPRN_SUMMARY",
     ["FA_ADDITIONS_B","FA_BOOK_CONTROLS"]),

    # CE
    (["bank statement","bank reconcil","cash management","ce statement"],
     "CE_STATEMENT_HEADERS",
     ["CE_STATEMENT_LINES","CE_BANK_ACCOUNTS"]),

    # Projects
    # Project module - comprehensive keywords
    (["project cost","project expenditure","project expense","pjc exp",
      "project module","project sql","project report","project data"],
     "PJC_EXP_ITEMS_ALL",
     ["PJF_PROJECTS_ALL_VL","PJF_TASKS_V"]),

    (["project billing","project invoice","project contract","project revenue",
      "contract invoice","billing invoice project","pjf billing",
      "project funding","project budget"],
     "PJF_PROJECTS_ALL_VL",
     ["PJF_TASKS_V","PJC_EXP_ITEMS_ALL"]),
]

# ── SQL detection ──────────────────────────────────────────────────────────
SQL_TRIGGERS = {
    # Explicit SQL keywords
    "generate","sql","query","report","bip","write sql","create sql",
    "show sql","give me","show me","get me","i need","i want",
    # Feature keywords
    "with join","with detail","detail","with code","with sla",
    "with subledger","with supplier","with customer","with payment",
    "with account","with segment","with gl","aging","analysis",
    # Action words
    "generate","create","build","fetch","extract","pull","list","all",
    # Module/domain words — searching for these implies wanting SQL
    "module","data","information","summary","invoice","payment",
    "journal","ledger","salary","payroll","employee","supplier",
    "customer","transaction","adjustment","receipt","order","asset",
    "billing","contract","revenue","cost","expenditure","statement",
    "bank","depreciation","balance","project",
}


def wants_sql(q: str) -> bool:
    ql = q.lower()
    return any(t in ql for t in SQL_TRIGGERS)


def detect_intent(query: str):
    """
    Returns (driver_table, extra_tables, hint, score).
    Merges ALL matching intents so multi-topic queries work.
    """
    q = query.lower()
    matches = []
    for keywords, driver, related in INTENT_MAP:
        score = sum(len(kw.split()) for kw in keywords if kw in q)
        if score > 0:
            matches.append((score, driver, list(related), keywords[0].title()))

    if not matches:
        return None, [], "", 0

    matches.sort(key=lambda x: -x[0])
    best_score, best_driver, best_tables, best_hint = matches[0]

    # Merge secondary intents whose score >= 1 (any keyword match)
    merged = list(best_tables)
    for score, driver, related, hint in matches[1:]:
        if score >= 1:
            if driver != best_driver and driver not in merged:
                merged.insert(0, driver)
            for t in related:
                if t not in merged:
                    merged.append(t)

    return best_driver, merged, best_hint, best_score


def build_sql(driver: str, extra_tables: list, query: str) -> str:
    """Build a complete Oracle (+) BIP SQL."""
    all_tables = [driver] + [t for t in extra_tables if t != driver]

    # Build alias map — KEY_COLS alias takes priority
    alias_map = {}
    used_aliases = {}
    for tbl in all_tables:
        if tbl in KEY_COLS:
            a = KEY_COLS[tbl][0][0]
        else:
            parts = [p for p in tbl.split("_") if p not in ("ALL","F","V","B","TL","M","VL")]
            a = "".join(p[0].lower() for p in parts[:3])
        # Deduplicate aliases
        base = a
        i = 2
        while a in used_aliases and used_aliases[a] != tbl:
            a = base + str(i); i += 1
        used_aliases[a] = tbl
        alias_map[tbl] = a

    # -- Header comment
    lines = [
        "-- ================================================================",
        f"-- Orbrick SQL Automation | Oracle Fusion BIP Report",
        f"-- Report     : {query[:60]}",
        f"-- Driver     : {driver}",
        f"-- Join Style : Oracle (+) outer-join  (BIP/OTBI standard)",
        f"-- Parameters : :P_START_DATE  :P_END_DATE  :P_ORG_ID",
        "-- ================================================================",
        "",
    ]

    # SELECT
    select_cols = []
    for tbl in all_tables:
        if tbl not in KEY_COLS:
            continue
        a = alias_map[tbl]
        for _, col, label in KEY_COLS[tbl]:
            if col_ok(tbl, col):
                select_cols.append(f"    {a}.{col:<42} \"{label}\"")

    if not select_cols:
        select_cols = ["    *"]

    lines.append("SELECT")
    for i, sc in enumerate(select_cols):
        sep = "," if i < len(select_cols) - 1 else ""
        lines.append(sc + sep)

    # FROM
    lines.append("")
    lines.append("FROM")
    for i, tbl in enumerate(all_tables):
        a   = alias_map[tbl]
        sep = "," if i < len(all_tables) - 1 else ""
        lines.append(f"      {tbl:<44}{a}{sep}")

    # WHERE — FK joins
    lines.append("")
    where_parts = []
    joined_pairs = set()
    tbl_set = set(all_tables)

    for child, cc, parent, pc, is_outer in FK_MAP:
        if child not in tbl_set or parent not in tbl_set:
            continue
        pair = tuple(sorted([child, parent, cc]))
        if pair in joined_pairs:
            continue
        joined_pairs.add(pair)
        ca = alias_map.get(child, "?")
        pa = alias_map.get(parent, "?")
        outer = "(+)" if is_outer else ""
        where_parts.append(f"{ca}.{cc}{outer} = {pa}.{pc}")

    # WHERE — driver-specific filters
    driver_where = WHERE_EXTRA.get(driver, "")
    if driver_where:
        for line in driver_where.splitlines():
            where_parts.append(line.strip())

    if where_parts:
        lines.append("WHERE " + where_parts[0])
        for wp in where_parts[1:]:
            lines.append("AND   " + wp)

    # ORDER BY
    ob = ORDER_BY.get(driver, "")
    # Validate order-by aliases exist
    if ob:
        valid_ob_parts = []
        for part in ob.split(","):
            part = part.strip()
            alias = part.split(".")[0] if "." in part else ""
            if alias in used_aliases or not alias:
                valid_ob_parts.append(part)
        if valid_ob_parts:
            lines.append("")
            lines.append("ORDER BY")
            lines.append("    " + ", ".join(valid_ob_parts))

    return "\n".join(lines)


def answer(query: str) -> str:
    """Main entry point. Returns formatted response string."""
    q = query.strip()
    driver, extra, hint, score = detect_intent(q)

    gen_sql = wants_sql(q) or score > 0

    if not driver:
        # No intent matched — show subject area search
        return _search_sa(q)

    if not gen_sql:
        # Show table info only
        return _describe_driver(driver, extra)

    # Build SQL
    sql = build_sql(driver, extra, q)
    all_tables = [driver] + [t for t in extra if t != driver]
    tbl_list = "\n".join(f"  • {t}" for t in all_tables)

    return (
        f"GENERATED BIP SQL\n"
        f"{'='*60}\n"
        f"{sql}\n"
        f"\nTABLES USED ({len(all_tables)})\n"
        f"{'='*60}\n"
        f"{tbl_list}\n"
        f"\nTIP: All joins use Oracle (+) syntax required for BIP/OTBI.\n"
        f"Columns validated against OTBI mapping and Oracle physical schema.\n"
    )


def _describe_driver(driver: str, extra: list) -> str:
    all_tables = [driver] + extra
    lines = [f"DATABASE TABLES\n{'='*52}"]
    for tbl in all_tables:
        info   = TBL_DATA.get(tbl, {})
        cols   = info.get("columns", [])
        sas    = info.get("subject_areas", [])[:2]
        lines.append(f"\nTABLE: {tbl}  ({len(cols)} columns)")
        if sas:
            lines.append(f"  Used in: {', '.join(sas)}")
        for c in cols[:12]:
            lines.append(f"  • {c}")
        if len(cols) > 12:
            lines.append(f"  ... +{len(cols)-12} more columns")
    lines.append(f"\nTIP: Type 'generate sql for {driver}' to get a ready BIP SQL.")
    return "\n".join(lines)


def _search_sa(q: str) -> str:
    q_up = q.upper().replace(" ", "_")
    q_lo = q.lower()
    hits = []
    for sa, info in SA_DATA.items():
        if q_lo in sa.lower() or any(q_up in t for t in info.get("tables", [])):
            hits.append((sa, info))
    if not hits:
        return (f"No subject area or table found matching '{q}'.\n"
                f"Try: 'AP invoice SQL', 'GL journal report', 'AR customer transaction'")
    lines = [f"MATCHING SUBJECT AREAS\n{'='*52}"]
    for sa, info in hits[:10]:
        tbls = info.get("tables", [])
        lines.append(f"\n[{info['module']}]  {sa}")
        lines.append(f"  Tables ({len(tbls)}):")
        for t in tbls[:5]:
            lines.append(f"  • {t}")
    return "\n".join(lines)


def find_matching_sa(query: str) -> list:
    q = query.lower()
    return [(sa, info) for sa, info in SA_DATA.items()
            if q in sa.lower()]
