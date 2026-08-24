import csv, json
from pathlib import Path

def _write(path, rows):
 rows=list(rows); path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',encoding='utf-8',newline='') as f:
  if rows:
   writer=csv.DictWriter(f,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
  else: f.write('dentist_id\n')

def export_state(store,state,output):
 slug=state.lower().replace(' ','_'); output=Path(output)
 with store.connect() as c:
  rows=[dict(x) for x in c.execute("SELECT d.*,p.* FROM dentists d LEFT JOIN prospects p USING(dentist_id) WHERE source_state=? ORDER BY COALESCE(prospect_score,-1) DESC",(state,))]
  clinics=[dict(x) for x in c.execute("""SELECT c.*,COUNT(r.dentist_id) number_of_dentists,GROUP_CONCAT(d.original_name,'; ') dentists
   FROM clinics c JOIN dentist_clinic_relationships r USING(clinic_id) JOIN dentists d USING(dentist_id)
   WHERE d.source_state=? GROUP BY c.clinic_id ORDER BY clinic_score DESC""",(state,))]
  cost=float(c.execute("SELECT COALESCE(SUM(cost_dollars),0) FROM exa_runs WHERE status='completed'").fetchone()[0])
 paths={"all":output/f"{slug}_all_prospects.csv","segment_a":output/f"{slug}_segment_a.csv","segment_b":output/f"{slug}_segment_b.csv","manual_review":output/f"{slug}_manual_review.csv","clinics":output/f"{slug}_clinics.csv","summary":output/f"{slug}_summary.json"}
 _write(paths['all'],rows); _write(paths['segment_a'],(x for x in rows if x.get('prospect_segment')=='A')); _write(paths['segment_b'],(x for x in rows if x.get('prospect_segment')=='B'))
 _write(paths['manual_review'],(x for x in rows if x.get('enrichment_status')=='manual_review')); _write(paths['clinics'],clinics)
 status=lambda *s:sum(x.get('enrichment_status') in s for x in rows)
 summary={"total_registry_records":len(rows),"processed":status('enriched','low_confidence','manual_review'),"successfully_enriched":status('enriched'),"high_confidence_matches":sum(x.get('identity_confidence')=='high' for x in rows),"google_business_confirmed":sum(x.get('google_business_presence')=='confirmed' for x in rows),"google_business_probable":sum(x.get('google_business_presence')=='probable' for x in rows),"clinic_owners_found":sum(x.get('practice_owner_likelihood')=='high' for x in rows),**{f"segment_{s.lower()}":sum(x.get('prospect_segment')==s for x in rows) for s in 'ABCD'},"manual_review":status('manual_review'),"exa_cost_dollars":round(cost,4)}
 paths['summary'].write_text(json.dumps(summary,indent=2),encoding='utf-8')
 return paths,summary

