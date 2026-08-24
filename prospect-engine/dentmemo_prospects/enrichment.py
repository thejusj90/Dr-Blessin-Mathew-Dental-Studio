import json, time

FIELDS=["clinic_name","clinic_type","clinic_address","city","district","state","pincode","website","public_phone","public_email","instagram_url","facebook_url","linkedin_url","google_maps_url","google_business_presence","google_business_confidence","practice_owner_likelihood","online_booking_url","other_directory_urls","source_urls","evidence","confidence","notes"]
DENTIST_ENRICHMENT_SCHEMA={"type":"object","additionalProperties":False,"properties":{"dentists":{"type":"array","items":{"type":"object","additionalProperties":False,"properties":{
 "input_dentist_id":{"type":"string"},"dentist_name":{"type":"string"},
 **{x:{"type":["string","null"]} for x in FIELDS[:14]},
 "google_business_presence":{"type":"string","enum":["confirmed","probable","not_found","unknown"]},
 "google_business_confidence":{"type":"number","minimum":0,"maximum":1},
 "practice_owner_likelihood":{"type":"string","enum":["high","medium","low","unknown"]},
 "online_booking_url":{"type":["string","null"]},"other_directory_urls":{"type":"array","items":{"type":"string"}},"source_urls":{"type":"array","items":{"type":"string"}},
 "evidence":{"type":"array","items":{"type":"object","additionalProperties":False,"properties":{"field":{"type":"string"},"value":{"type":"string"},"source_url":{"type":"string"},"source_title":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}},"required":["field","value","source_url","source_title","confidence"]}},
 "confidence":{"type":"number","minimum":0,"maximum":1},"notes":{"type":["string","null"]}},
 "required":["input_dentist_id","dentist_name","google_business_presence","google_business_confidence","practice_owner_likelihood","other_directory_urls","source_urls","evidence","confidence","notes"]}},},"required":["dentists"]}

PROMPT="""Enrich registered Indian dentists for internal B2B research. For each input row identify the current dental clinic using name, geography, profession, registration, and clinic affiliation. Return only public professional/business information and evidence URLs. Never guess; distinguish names using geographic evidence and return null with low confidence when ambiguous. Do not fabricate contacts or URLs. A Google listing is confirmed only with a credible Google Maps URL or equivalent direct evidence; never scrape Google Maps. Assess ownership conservatively. Preserve field-level grounding."""

class ExaClient:
 def __init__(self,client=None,sleep=time.sleep,max_retries=4):
  if client is None:
   from exa_py import Exa
   client=Exa()
  self.client=client; self.sleep=sleep; self.max_retries=max_retries
 def run(self,data,effort="medium",poll_seconds=2):
  run=self._retry(lambda:self.client.agent.runs.create(instructions=PROMPT,input={"data":data},output={"schema":DENTIST_ENRICHMENT_SCHEMA},effort=effort))
  run_id=self._get(run,"id")
  while self._get(run,"status") not in {"completed","failed","canceled"}:
   self.sleep(poll_seconds); run=self._retry(lambda:self.client.agent.runs.get(run_id))
  status=self._get(run,"status")
  if status != "completed": raise RuntimeError(f"Exa run {run_id} ended with {status}")
  output=self._get(run,"output")
  if isinstance(output,str): output=json.loads(output)
  return run_id, output, float(self._get(run,"cost_dollars",self._get(run,"cost",0)) or 0)
 @staticmethod
 def _get(obj,key,default=None): return obj.get(key,default) if isinstance(obj,dict) else getattr(obj,key,default)
 def _retry(self,fn):
  for attempt in range(self.max_retries+1):
   try: return fn()
   except Exception as exc:
    status=getattr(exc,"status_code",None)
    temporary=status in {429,500,502,503,504} or isinstance(exc,(TimeoutError,ConnectionError))
    if not temporary or attempt==self.max_retries: raise
    self.sleep(2**(attempt+1))

def parse_output(output,expected_ids):
 if not isinstance(output,dict) or not isinstance(output.get("dentists"),list): raise ValueError("Invalid Exa structured output")
 result={}
 for row in output["dentists"]:
  did=row.get("input_dentist_id")
  if did not in expected_ids or did in result: raise ValueError("Unexpected or duplicate dentist ID")
  if row.get("google_business_presence") not in {"confirmed","probable","not_found","unknown"}: raise ValueError("Invalid Google presence")
  confidence=float(row.get("confidence",0))
  if not 0<=confidence<=1: raise ValueError("Invalid confidence")
  result[did]=row
 if set(result) != set(expected_ids): raise ValueError("Exa output omitted an input dentist ID")
 return result
