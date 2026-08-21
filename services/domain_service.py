from uuid import UUID

from sqlalchemy.orm import Session

from models.domain import Domain
from utils.domain_utils import normalize_domain


def create_domain(
    db: Session,
    domain_name: str,
) -> Domain:
    """
    Create a new domain.

    If the domain already exists, return the existing record.
    """

    normalized_domain = normalize_domain(domain_name)

    existing_domain = (
        db.query(Domain)
        .filter(Domain.domain == normalized_domain)
        .first()
    )

    if existing_domain:
        return existing_domain

    domain = Domain(
        domain=normalized_domain,
        is_active=True,
        scan_status="pending",
    )

    db.add(domain)
    db.commit()
    db.refresh(domain)

    return domain


def get_domain(
    db: Session,
    domain_id: UUID,
) -> Domain | None:
    """
    Get a domain by UUID.
    """

    return (
        db.query(Domain)
        .filter(Domain.id == domain_id)
        .first()
    )


def get_domain_by_name(
    db: Session,
    domain_name: str,
) -> Domain | None:
    """
    Get a domain by domain name.
    """

    normalized_domain = normalize_domain(domain_name)

    return (
        db.query(Domain)
        .filter(Domain.domain == normalized_domain)
        .first()
    )


def get_all_domains(
    db: Session,
) -> list[Domain]:
    """
    Get all domains.
    """

    return db.query(Domain).all()


def update_scan_status(
    db: Session,
    domain: Domain,
    status: str,
    error_message: str | None = None,
) -> Domain:
    """
    Update domain scan status.
    """

    domain.scan_status = status
    domain.error_message = error_message

    db.commit()
    db.refresh(domain)

    return domain