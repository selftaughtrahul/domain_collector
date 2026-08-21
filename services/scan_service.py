from datetime import datetime
from models import Website, Company, Contact, SocialProfile, Technology, SEOData, DNSRecord, SecurityData, Scan
from collectors.website import collect_website, company, contacts, social, technologies, seo, security, dns_records
from utils.logger import logger

def replace_one(db,model,domain_id,data):
 item=db.query(model).filter_by(domain_id=domain_id).first()
 if not item: item=model(domain_id=domain_id); db.add(item)
 for key,value in data.items(): setattr(item,key,value)
async def scan_domain(db,domain):
 domain.scan_status="scanning"; domain.error_message=None; scan=Scan(domain_id=domain.id,status="scanning"); db.add(scan); db.commit(); errors=[]
 try:
  web,ctx=await collect_website(domain.domain); replace_one(db,Website,domain.id,web); db.commit()
 except Exception as exc:
  domain.scan_status="failed"; domain.error_message="website: "+type(exc).__name__; scan.status="failed"; scan.errors=domain.error_message; scan.completed_at=datetime.utcnow(); db.commit(); return scan
 for name,model,fn,many in [("company",Company,company,False),("contacts",Contact,contacts,True),("social",SocialProfile,social,True),("technologies",Technology,technologies,True),("seo",SEOData,seo,False),("dns",DNSRecord,lambda x:dns_records(domain.domain),True),("security",SecurityData,security,False)]:
  try:
   data=fn(ctx)
   if many:
    db.query(model).filter_by(domain_id=domain.id).delete()
    for row in data: db.add(model(domain_id=domain.id,**row))
   else: replace_one(db,model,domain.id,data)
   db.commit()
  except Exception as exc:
   db.rollback(); errors.append(name+": "+type(exc).__name__); logger.exception("collector failed: %s",name)
 domain.scan_status="partial" if errors else "completed"; domain.error_message="; ".join(errors) or None; domain.last_scanned_at=datetime.utcnow(); scan.status=domain.scan_status; scan.errors=domain.error_message; scan.completed_at=datetime.utcnow(); db.commit(); return scan
