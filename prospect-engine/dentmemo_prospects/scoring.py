DEFAULT = {"google_confirmed":20,"google_probable":10,"owner_high":20,"owner_medium":15,
"website":10,"phone":10,"email":5,"instagram":5,"facebook":3,"linkedin":2,
"identity_high":10,"multiple_sources":5,"no_clinic":-10,"identity_low":-20}

def load_weights(path):
    try:
        import yaml
    except ImportError:
        return {"prospect": DEFAULT, "identity": None}
    with open(path, encoding="utf-8") as stream:
        configured = yaml.safe_load(stream) or {}
    return {"prospect": {**DEFAULT, **configured.get("prospect", {})},
            "identity": configured.get("identity")}

def identity_score(signals, weights=None):
    weights = weights or {"exact_name":30,"same_city":20,"same_state":10,"dentist_profession":15,
      "two_clinic_sources":20,"registration_match":40,"conflicting_city":-25,"conflicting_profession":-40}
    score=sum(weights.get(k,0) for k,v in signals.items() if v)
    return ("high" if score >= 60 else "medium" if score >= 35 else "low"), score

def prospect_score(p, identity="low", weights=None):
    w=weights or DEFAULT; score=0
    gp=p.get("google_business_presence")
    score += w["google_confirmed"] if gp=="confirmed" else w["google_probable"] if gp=="probable" else 0
    owner=p.get("practice_owner_likelihood")
    score += w["owner_high"] if owner=="high" else w["owner_medium"] if owner=="medium" else 0
    for key,wk in (("website","website"),("public_phone","phone"),("public_email","email"),("instagram_url","instagram"),("facebook_url","facebook"),("linkedin_url","linkedin")):
        if p.get(key): score += w[wk]
    if identity=="high": score += w["identity_high"]
    if len(p.get("source_urls") or []) >= 2: score += w["multiple_sources"]
    if not p.get("clinic_name"): score += w["no_clinic"]
    if identity=="low": score += w["identity_low"]
    return max(0,min(100,score))

def segment(score): return "A" if score>=75 else "B" if score>=55 else "C" if score>=35 else "D"

def tags(p, identity, manual=False):
    out=[]
    if p.get("practice_owner_likelihood")=="high": out.append("clinic_owner")
    if p.get("practice_owner_likelihood")=="medium": out.append("independent_dentist")
    for field, tag in (("website","has_website"),("instagram_url","has_instagram"),("public_phone","has_phone"),("public_email","has_email")):
        if p.get(field): out.append(tag)
    if p.get("google_business_presence") in {"confirmed","probable"}: out.append("has_google_presence")
    if identity=="low": out.append("low_confidence")
    if manual: out.append("manual_review")
    return out
