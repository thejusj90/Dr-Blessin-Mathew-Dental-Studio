import argparse, json, logging, math, os, sys
from pathlib import Path
from .config import Settings, ROOT
from .enrichment import ExaClient, parse_output
from .exporters import export_state
from .ingestion import load_csv, deduplicate
from .scoring import identity_score, prospect_score, segment, tags, load_weights
from .storage import Store, now

def batches(items,size):
 for i in range(0,len(items),size): yield items[i:i+size]

def enrich(store,args,settings,client=None):
 size=args.batch_size or settings.batch_size; effort=args.effort or settings.effort
 max_cost=settings.max_cost if args.max_cost is None else args.max_cost
 rows=store.pending(args.state,args.limit,args.force); weights=load_weights(ROOT/'config/scoring.yaml')
 print(f"Dentists to process: {len(rows)}\nBatch size: {size}\nEstimated requests: {math.ceil(len(rows)/size) if rows else 0}")
 if args.dry_run:
  for i,b in enumerate(batches(rows,size),1): print(f"Batch {i}: {len(b)} dentists ({', '.join(x['dentist_id'] for x in b)})")
  return
 client=client or ExaClient()
 total_batches=math.ceil(len(rows)/size)
 for index,batch in enumerate(batches(rows,size),1):
  if store.cost() >= max_cost: print(f"Maximum cost ${max_cost:.2f} reached; stopping."); break
  ids=[x['dentist_id'] for x in batch]; store.mark_processing(ids); started=now()
  print(f"Batch {index}/{total_batches} | Dentists: {len(batch)}")
  payload=[{"dentist_id":x['dentist_id'],"dentist_name":x['original_name'],"registration_number":x['registration_number'] or None,"city":x['source_city'] or None,"state":x['source_state'],"profession":"dentist"} for x in batch]
  try:
   run_id,output,cost=client.run(payload,effort,settings.poll_seconds); parsed=parse_output(output,set(ids))
   store.save_run(run_id,len(batch),effort,'completed',cost,started=started)
   for d in batch:
    p=parsed.get(d['dentist_id'])
    if not p: store.mark_failed([d['dentist_id']]); continue
    evidence=p.get('evidence') or []; signals={"exact_name":d['normalized_name'] in p.get('dentist_name','').upper(),"same_city":bool(d['source_city'] and (p.get('city') or '').casefold()==d['source_city'].casefold()),"same_state":(p.get('state') or '').casefold()==d['source_state'].casefold(),"dentist_profession":True,"two_clinic_sources":len(evidence)>=2,"registration_match":bool(d['registration_number'] and d['registration_number'].casefold() in json.dumps(p).casefold())}
    identity,_=identity_score(signals,weights['identity']); manual=p['confidence']<.55 or identity=='low'; status='manual_review' if manual else 'low_confidence' if p['confidence']<.75 else 'enriched'
    score=prospect_score(p,identity,weights['prospect']); store.save_enrichment(d,p,run_id,identity,score,segment(score),tags(p,identity,manual),status,evidence)
   print(f"Exa run: {run_id} | Status: completed | Cost: ${cost:.4f} | Processed: {min(index*size,len(rows))}/{len(rows)}")
  except Exception as exc:
   store.mark_failed(ids); store.save_run(f"failed-{started}",len(batch),effort,'failed',error=str(exc),started=started); logging.error("Batch failed: %s",exc)

def parser():
 p=argparse.ArgumentParser(prog='dentmemo-prospects'); sub=p.add_subparsers(dest='command',required=True)
 imp=sub.add_parser('import'); imp.add_argument('csv'); imp.add_argument('--state',required=True); imp.add_argument('--import-batch',default='')
 en=sub.add_parser('enrich'); en.add_argument('--state',required=True); en.add_argument('--limit',type=int); en.add_argument('--batch-size',type=int); en.add_argument('--effort',choices=['low','medium','high','auto']); en.add_argument('--max-cost',type=float); en.add_argument('--dry-run',action='store_true'); en.add_argument('--force',action='store_true')
 st=sub.add_parser('stats'); st.add_argument('--state'); ex=sub.add_parser('export'); ex.add_argument('--state',required=True); ex.add_argument('--output',default=str(ROOT/'data/output'))
 sh=sub.add_parser('show'); sh.add_argument('dentist_id')
 rf=sub.add_parser('refresh'); rf.add_argument('--older-than',type=int,required=True,help='Reserved freshness selector; does not call Exa')
 return p

def main(argv=None):
 try:
  from dotenv import load_dotenv; load_dotenv(ROOT/'.env')
 except ImportError: pass
 args=parser().parse_args(argv); settings=Settings.load(); store=Store(settings.database_path)
 if args.command=='import':
  records=load_csv(args.csv,args.state,args.import_batch); unique,dupes=deduplicate(records); inserted=store.import_records(unique); print(f"Input records: {len(records)}\nNormalized records: {len(unique)}\nDuplicates detected: {len(dupes)}\nImported: {inserted}")
 elif args.command=='enrich': enrich(store,args,settings)
 elif args.command=='stats': print(json.dumps(store.stats(args.state),indent=2))
 elif args.command=='show':
  row=store.one(args.dentist_id)
  if not row: raise SystemExit('Dentist not found')
  print(json.dumps(row,indent=2,default=str))
 elif args.command=='export':
  paths,summary=export_state(store,args.state,args.output); print("DentMemo Prospect Engine\n"+json.dumps(summary,indent=2)); print('\n'.join(str(x) for x in paths.values()))
 else: print(f"Refresh candidate selection for records older than {args.older_than} days is reserved; no enrichment was started.")

if __name__=='__main__': main()
