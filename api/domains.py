from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database.connection import get_db
from models.company import Company
from models.domain import Domain
from schemas.domain import DomainCreate, DomainRead

router = APIRouter(
    tags=["Domains"],
)

@router.post("/companies/{company_id}/domains", response_model=DomainRead, status_code=status.HTTP_201_CREATED)
def create_domain_under_company(company_id: str, domain_in: DomainCreate, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    existing = db.query(Domain).filter(Domain.domain == domain_in.domain).first()
    if existing:
        raise HTTPException(status_code=409, detail="Domain already exists")
        
    domain = Domain(company_id=company_id, **domain_in.model_dump())
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain

@router.get("/companies/{company_id}/domains", response_model=List[DomainRead])
def get_company_domains(company_id: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company.domains

@router.get("/domains/{domain_id}", response_model=DomainRead)
def get_domain(domain_id: str, db: Session = Depends(get_db)):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return domain

@router.put("/domains/{domain_id}", response_model=DomainRead)
def update_domain(domain_id: str, domain_in: DomainCreate, db: Session = Depends(get_db)):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
        
    domain.domain = domain_in.domain
    domain.domain_type = domain_in.domain_type
    domain.is_primary = domain_in.is_primary
    db.commit()
    db.refresh(domain)
    return domain

@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain(domain_id: str, db: Session = Depends(get_db)):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    db.delete(domain)
    db.commit()
    return None

@router.post("/domains/{domain_id}/set-primary", response_model=DomainRead)
def set_primary_domain(domain_id: str, db: Session = Depends(get_db)):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
        
    # unset others in the same company
    db.query(Domain).filter(Domain.company_id == domain.company_id).update({"is_primary": False})
    domain.is_primary = True
    db.commit()
    db.refresh(domain)
    return domain
