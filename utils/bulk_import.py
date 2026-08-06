"""
Reads a bulk employee data file (CSV or Excel) and normalizes it into a
list of plain dicts ready to insert as IDCard rows.

Column headers are matched flexibly (case/space/underscore-insensitive)
against the reference sheet used for this project:
    Sr. No, Name, Employee Code, Blood Group,
    Unit Landline number, Emergency Contact Number, Employee Contact Number
Any extra/missing columns are handled gracefully.
"""

import pandas as pd

COLUMN_ALIASES = {
    "sr_no": ["sr no", "sr.no", "sr. no", "s.no", "sno", "serial", "sl no"],
    "name": ["name", "employee name", "full name"],
    "employee_code": ["employee code", "emp code", "empcode", "employee id", "emp id", "id"],
    "designation": ["designation", "role", "title"],
    "blood_group": ["blood group", "bloodgroup", "blood grp"],
    "landline": ["unit landline number", "landline", "landline number", "unit landline"],
    "emergency_contact": ["emergency contact number", "emergency contact", "emergency no"],
    "employee_contact": ["employee contact number", "employee contact", "contact number", "mobile", "phone"],
    "email": ["email", "e-mail", "email id", "email address"],
}


def _normalize(col: str) -> str:
    return str(col).strip().lower().replace(".", "").replace("_", " ")


def _build_column_map(columns):
    normalized = {_normalize(c): c for c in columns}
    mapping = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[field] = normalized[alias]
                break
    return mapping


def read_bulk_file(filepath: str) -> list[dict]:
    if filepath.lower().endswith(".csv"):
        df = pd.read_csv(filepath, dtype=str)
    else:
        df = pd.read_excel(filepath, dtype=str)

    df = df.dropna(how="all")
    col_map = _build_column_map(df.columns)

    if "name" not in col_map or "employee_code" not in col_map:
        raise ValueError(
            "Could not find required 'Name' and 'Employee Code' columns in the uploaded file. "
            "Please check the column headers match the reference sheet."
        )

    records = []
    for _, row in df.iterrows():
        name = str(row.get(col_map.get("name"), "")).strip()
        code = str(row.get(col_map.get("employee_code"), "")).strip()
        if not name or not code or name.lower() == "nan" or code.lower() == "nan":
            continue

        def get(field, default=""):
            col = col_map.get(field)
            if col is None:
                return default
            val = row.get(col)
            if val is None or str(val).lower() == "nan":
                return default
            return str(val).strip()

        sr_no_raw = get("sr_no")
        try:
            sr_no = int(float(sr_no_raw)) if sr_no_raw else None
        except ValueError:
            sr_no = None

        # Employee codes / phone numbers often come through as floats (e.g. 253729.0)
        def clean_number(val):
            if val.endswith(".0"):
                return val[:-2]
            return val

        records.append({
            "sr_no": sr_no,
            "name": name,
            "employee_code": clean_number(code),
            "designation": get("designation"),
            "blood_group": get("blood_group"),
            "landline": clean_number(get("landline")),
            "emergency_contact": clean_number(get("emergency_contact")),
            "employee_contact": clean_number(get("employee_contact")),
            "email": get("email"),
        })

    return records
