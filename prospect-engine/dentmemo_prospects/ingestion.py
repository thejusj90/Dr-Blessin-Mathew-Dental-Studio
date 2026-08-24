import csv, hashlib, re, unicodedata
from pathlib import Path
from .models import Dentist

ALIASES = {
 "dentist_name": ("dentist_name","doctor_name","name","dentist","doctor"),
 "registration_number": ("registration_number","registration_no","reg_no","registration","regnumber"),
 "city": ("city","town"), "district": ("district",), "state": ("state",),
 "address": ("address","postal_address","clinic_address")}

def key(value): return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")

def map_columns(headers):
    keyed = {key(h): h for h in headers if h}
    result = {canonical: next((keyed[a] for a in aliases if a in keyed), None)
              for canonical, aliases in ALIASES.items()}
    if not result["dentist_name"]: raise ValueError("CSV needs a dentist name column")
    return result

def normalize_name(name):
    value = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    value = re.sub(r"[^A-Za-z0-9 ]", " ", value)
    words = value.upper().split()
    while words and words[0] in {"DR", "DOCTOR"}: words.pop(0)
    while words and words[-1] in {"BDS", "MDS", "FDS", "DDS", "DMD"}: words.pop()
    return " ".join(words)

def dentist_id(registration, name, city, state):
    reg = re.sub(r"[^A-Z0-9]", "", (registration or "").upper())
    seed = f"REG|{reg}|{state.strip().upper()}" if reg else f"NAME|{normalize_name(name)}|{city.strip().upper()}|{state.strip().upper()}"
    return "dent_" + hashlib.sha256(seed.encode()).hexdigest()[:20]

def load_csv(path, state, import_batch=""):
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f); mapping = map_columns(reader.fieldnames or [])
        records=[]
        for row in reader:
            get=lambda c: (row.get(mapping.get(c) or "", "") or "").strip()
            name=get("dentist_name")
            if not name: continue
            row_state=get("state") or state; city=get("city"); reg=get("registration_number")
            records.append(Dentist(dentist_id(reg,name,city,row_state), reg, name,
                normalize_name(name), row_state, city, get("address"), str(path), "registry", import_batch))
    return records

def deduplicate(records):
    seen={}; duplicates=[]
    for record in records:
        if record.dentist_id in seen: duplicates.append(record)
        else: seen[record.dentist_id]=record
    return list(seen.values()), duplicates

