import csv
from pathlib import Path
from types import SimpleNamespace
import pytest
from dentmemo_prospects.ingestion import normalize_name, dentist_id, map_columns, load_csv, deduplicate
from dentmemo_prospects.scoring import identity_score, prospect_score, segment
from dentmemo_prospects.storage import Store
from dentmemo_prospects.enrichment import ExaClient, parse_output

def test_name_normalization():
 assert normalize_name('Dr. John Mathew BDS') == 'JOHN MATHEW'
 assert normalize_name('DOCTOR JOHN MATHEW') == 'JOHN MATHEW'

def test_mapping_and_ids():
 assert map_columns(['Doctor Name','Reg No','Town'])['registration_number']=='Reg No'
 assert dentist_id('G-1','A','Panjim','Goa') == dentist_id('g 1','Other','X','Goa')
 assert dentist_id('','Dr A BDS','Panjim','Goa') == dentist_id('','A','Panjim','Goa')

def test_csv_and_dedup(tmp_path):
 p=tmp_path/'in.csv'; p.write_text('doctor_name,registration_no,city\nDr A,G1,Panaji\nA,G1,Panaji\n')
 rows=load_csv(p,'Goa'); unique,dupes=deduplicate(rows)
 assert len(rows)==2 and len(unique)==1 and len(dupes)==1

def test_identity_scoring_and_segments():
 assert identity_score({'registration_match':True,'exact_name':True})[0]=='high'
 assert [segment(x) for x in (75,55,35,34)] == list('ABCD')

def test_prospect_score_separate_from_identity():
 p={'google_business_presence':'confirmed','practice_owner_likelihood':'high','clinic_name':'Clinic','website':'x','public_phone':'x','public_email':'x','instagram_url':'x','facebook_url':'x','linkedin_url':'x','source_urls':['a','b']}
 assert prospect_score(p,'high')==90
 assert prospect_score({},'low')==0

def test_checkpoint_recovery_and_resume(tmp_path):
 p=tmp_path/'in.csv'; p.write_text('name,registration_number\nDr A,G1\n')
 s=Store(tmp_path/'x.db'); s.import_records(load_csv(p,'Goa')); row=s.pending('Goa')[0]; s.mark_processing([row['dentist_id']])
 assert Store(tmp_path/'x.db').pending('Goa')[0]['enrichment_status']=='pending'

def valid_output(did):
 return {'dentists':[{'input_dentist_id':did,'dentist_name':'A','google_business_presence':'unknown','google_business_confidence':0,'practice_owner_likelihood':'unknown','other_directory_urls':[],'source_urls':[],'evidence':[],'confidence':.2,'notes':None}]}

def test_output_parsing():
 assert parse_output(valid_output('d'),{'d'})['d']['confidence']==.2
 with pytest.raises(ValueError): parse_output({'dentists':[]}, {'d'})['d']

class Runs:
 def __init__(self): self.calls=0
 def create(self,**kwargs): self.calls+=1; return {'id':'r1','status':'completed','output':valid_output('d'),'cost':.1}
 def get(self,id): raise AssertionError('no polling needed')

def test_exa_client_and_no_paid_call():
 runs=Runs(); fake=SimpleNamespace(agent=SimpleNamespace(runs=runs))
 rid,out,cost=ExaClient(fake,sleep=lambda _:None).run([{'dentist_id':'d'}])
 assert (rid,cost,runs.calls)==('r1',.1,1) and out['dentists']

def test_exa_temporary_failure_retries():
 class Temporary(Exception): status_code=429
 class RetryRuns(Runs):
  def create(self,**kwargs):
   self.calls+=1
   if self.calls<2: raise Temporary()
   return {'id':'r1','status':'completed','output':valid_output('d'),'cost':0}
 runs=RetryRuns(); fake=SimpleNamespace(agent=SimpleNamespace(runs=runs))
 ExaClient(fake,sleep=lambda _:None).run([]); assert runs.calls==2
