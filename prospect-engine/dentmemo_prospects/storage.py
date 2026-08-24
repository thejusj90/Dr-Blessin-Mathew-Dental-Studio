import json, sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

def now(): return datetime.now(timezone.utc).isoformat()

SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS dentists (
 dentist_id TEXT PRIMARY KEY, registration_number TEXT, original_name TEXT NOT NULL,
 normalized_name TEXT NOT NULL, source_state TEXT NOT NULL, source_city TEXT,
 source_address TEXT, source_file TEXT, source TEXT, import_batch TEXT,
 enrichment_status TEXT NOT NULL DEFAULT 'pending', crm_status TEXT NOT NULL DEFAULT 'new',
 outreach_status TEXT, first_contacted_at TEXT, last_contacted_at TEXT, channel TEXT,
 campaign TEXT, reply_status TEXT, demo_status TEXT, subscription_status TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS dentist_state_status ON dentists(source_state,enrichment_status);
CREATE TABLE IF NOT EXISTS prospects (
 dentist_id TEXT PRIMARY KEY REFERENCES dentists(dentist_id), clinic_name TEXT, clinic_type TEXT,
 clinic_address TEXT, city TEXT, district TEXT, state TEXT, pincode TEXT, website TEXT,
 public_phone TEXT, public_email TEXT, instagram_url TEXT, facebook_url TEXT, linkedin_url TEXT,
 google_maps_url TEXT, google_business_presence TEXT, google_business_confidence REAL,
 practice_owner_likelihood TEXT, online_booking_url TEXT, other_directory_urls TEXT,
 identity_confidence TEXT, exa_confidence REAL, prospect_score INTEGER, prospect_segment TEXT,
 tags TEXT, source_urls TEXT, exa_run_id TEXT, enriched_at TEXT, last_checked_at TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS evidence (id INTEGER PRIMARY KEY, dentist_id TEXT REFERENCES dentists,
 field TEXT, value TEXT, source_url TEXT, source_title TEXT, confidence REAL, raw_json TEXT);
CREATE TABLE IF NOT EXISTS clinics (clinic_id TEXT PRIMARY KEY, clinic_name TEXT, normalized_address TEXT,
 city TEXT, state TEXT, website TEXT, phone TEXT, instagram_url TEXT, google_business_presence TEXT, clinic_score INTEGER);
CREATE TABLE IF NOT EXISTS dentist_clinic_relationships (dentist_id TEXT REFERENCES dentists,
 clinic_id TEXT REFERENCES clinics, relationship_type TEXT, confidence REAL, PRIMARY KEY(dentist_id,clinic_id));
CREATE TABLE IF NOT EXISTS exa_runs (run_id TEXT PRIMARY KEY, dentists_in_batch INTEGER, effort TEXT,
 started_at TEXT, completed_at TEXT, status TEXT, cost_dollars REAL DEFAULT 0, error TEXT);
"""

class Store:
 def __init__(self,path):
  self.path=path; path.parent.mkdir(parents=True,exist_ok=True)
  with self.connect() as c: c.executescript(SCHEMA); self.recover(c)
 @contextmanager
 def connect(self):
  c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row
  try: yield c; c.commit()
  finally: c.close()
 def recover(self,c): c.execute("UPDATE dentists SET enrichment_status='pending' WHERE enrichment_status='processing'")
 def import_records(self, records):
  inserted=0
  with self.connect() as c:
   for d in records:
    vals=d.asdict(); stamp=now()
    cur=c.execute("""INSERT OR IGNORE INTO dentists
     (dentist_id,registration_number,original_name,normalized_name,source_state,source_city,source_address,source_file,source,import_batch,created_at,updated_at)
     VALUES(:dentist_id,:registration_number,:original_name,:normalized_name,:source_state,:source_city,:source_address,:source_file,:source,:import_batch,:stamp,:stamp)""",{**vals,"stamp":stamp})
    inserted += cur.rowcount
  return inserted
 def pending(self,state,limit=None,force=False):
  where="source_state=?" if force else "source_state=? AND enrichment_status IN ('pending','failed')"
  sql=f"SELECT * FROM dentists WHERE {where} ORDER BY dentist_id"+(" LIMIT ?" if limit else "")
  with self.connect() as c: return [dict(x) for x in c.execute(sql,(state,limit) if limit else (state,))]
 def mark_processing(self,ids):
  with self.connect() as c: c.executemany("UPDATE dentists SET enrichment_status='processing',updated_at=? WHERE dentist_id=?",[(now(),x) for x in ids])
 def save_run(self,run_id,count,effort,status,cost=0,error=None,started=None):
  with self.connect() as c: c.execute("""INSERT INTO exa_runs VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET
   completed_at=excluded.completed_at,status=excluded.status,cost_dollars=excluded.cost_dollars,error=excluded.error""",
   (run_id,count,effort,started or now(),now() if status in {'completed','failed','canceled'} else None,status,cost,error))
 def save_enrichment(self,dentist,p,run_id,identity,score,segment,tags,status,evidence):
  fields=['clinic_name','clinic_type','clinic_address','city','district','state','pincode','website','public_phone','public_email','instagram_url','facebook_url','linkedin_url','google_maps_url','google_business_presence','google_business_confidence','practice_owner_likelihood','online_booking_url']
  data={k:p.get(k) for k in fields}; stamp=now()
  data.update(dentist_id=dentist['dentist_id'],other_directory_urls=json.dumps(p.get('other_directory_urls') or []),identity_confidence=identity,exa_confidence=p.get('confidence',0),prospect_score=score,prospect_segment=segment,tags=json.dumps(tags),source_urls=json.dumps(p.get('source_urls') or []),exa_run_id=run_id,enriched_at=stamp,last_checked_at=stamp,notes=p.get('notes'))
  columns=','.join(data); binds=','.join(':'+x for x in data)
  with self.connect() as c:
   c.execute(f"INSERT OR REPLACE INTO prospects({columns}) VALUES({binds})",data)
   c.execute("UPDATE dentists SET enrichment_status=?,updated_at=? WHERE dentist_id=?",(status,stamp,dentist['dentist_id']))
   c.execute("DELETE FROM evidence WHERE dentist_id=?",(dentist['dentist_id'],))
   c.executemany("INSERT INTO evidence(dentist_id,field,value,source_url,source_title,confidence,raw_json) VALUES(?,?,?,?,?,?,?)",[(dentist['dentist_id'],e.get('field'),str(e.get('value','')),e.get('source_url'),e.get('source_title'),e.get('confidence'),json.dumps(e)) for e in evidence])
   if p.get('clinic_name'):
    import hashlib
    clinic_seed='|'.join(str(p.get(x) or '').strip().upper() for x in ('clinic_name','clinic_address','city','state'))
    clinic_id='clinic_'+hashlib.sha256(clinic_seed.encode()).hexdigest()[:20]
    c.execute("""INSERT INTO clinics(clinic_id,clinic_name,normalized_address,city,state,website,phone,instagram_url,google_business_presence,clinic_score)
     VALUES(?,?,?,?,?,?,?,?,?,0) ON CONFLICT(clinic_id) DO UPDATE SET website=COALESCE(excluded.website,website),phone=COALESCE(excluded.phone,phone)""",
     (clinic_id,p.get('clinic_name'),p.get('clinic_address'),p.get('city'),p.get('state'),p.get('website'),p.get('public_phone'),p.get('instagram_url'),p.get('google_business_presence')))
    c.execute("INSERT OR REPLACE INTO dentist_clinic_relationships VALUES(?,?,?,?)",(dentist['dentist_id'],clinic_id,'owner' if p.get('practice_owner_likelihood')=='high' else 'practitioner',p.get('confidence',0)))
    count=c.execute("SELECT COUNT(*) FROM dentist_clinic_relationships WHERE clinic_id=?",(clinic_id,)).fetchone()[0]
    clinic_score=min(100,score + min(20,max(0,count-1)*5))
    c.execute("UPDATE clinics SET clinic_score=? WHERE clinic_id=?",(clinic_score,clinic_id))
 def mark_failed(self,ids):
  with self.connect() as c: c.executemany("UPDATE dentists SET enrichment_status='failed',updated_at=? WHERE dentist_id=?",[(now(),x) for x in ids])
 def cost(self):
  with self.connect() as c: return float(c.execute("SELECT COALESCE(SUM(cost_dollars),0) FROM exa_runs WHERE status='completed'").fetchone()[0])
 def one(self,id):
  with self.connect() as c:
   row=c.execute("SELECT d.*,p.* FROM dentists d LEFT JOIN prospects p USING(dentist_id) WHERE dentist_id=?",(id,)).fetchone(); return dict(row) if row else None
 def stats(self,state=None):
  clause=" WHERE source_state=?" if state else ""; args=(state,) if state else ()
  with self.connect() as c:
   rows=c.execute("SELECT enrichment_status,COUNT(*) n FROM dentists"+clause+" GROUP BY enrichment_status",args).fetchall()
   return {"total":sum(r['n'] for r in rows),"statuses":{r['enrichment_status']:r['n'] for r in rows},"exa_cost_dollars":self.cost()}

