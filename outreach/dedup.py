"""Deduplication utility for lead-gen prospects."""
import csv
import os
from datetime import datetime

PROCESSED_LOG = os.path.join(os.path.dirname(__file__), "processed_log.csv")
CSV_FILE = os.path.join(os.path.dirname(__file__), "prospects.csv")

FIELDNAMES = ["company", "domain", "email", "status", "added_at", "batch"]


def load_processed_log() -> list:
    """Load the processed log CSV."""
    if not os.path.exists(PROCESSED_LOG):
        return []
    with open(PROCESSED_LOG, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def get_processed_domains() -> set:
    """Get set of already-processed domains."""
    log = load_processed_log()
    return {row["domain"].lower().strip() for row in log}


def get_processed_emails() -> set:
    """Get set of already-processed emails."""
    log = load_processed_log()
    return {row["email"].lower().strip() for row in log}


def get_processed_companies() -> set:
    """Get set of already-processed company names."""
    log = load_processed_log()
    return {row["company"].lower().strip() for row in log}


def is_duplicate(company: str, domain: str, email: str) -> bool:
    """Check if a prospect is already in the processed log."""
    log = load_processed_log()
    company_lower = company.lower().strip()
    domain_lower = domain.lower().strip()
    email_lower = email.lower().strip()
    
    for row in log:
        if (row["company"].lower().strip() == company_lower or
            row["domain"].lower().strip() == domain_lower or
            row["email"].lower().strip() == email_lower):
            return True
    return False


def filter_duplicates(prospects: list) -> list:
    """Filter out prospects that are already in the processed log."""
    log = load_processed_log()
    processed_companies = {row["company"].lower().strip() for row in log}
    processed_domains = {row["domain"].lower().strip() for row in log}
    processed_emails = {row["email"].lower().strip() for row in log}
    
    unique = []
    skipped = []
    for p in prospects:
        company = p.get("company", "").lower().strip()
        domain = p.get("domain", "").lower().strip()
        email = p.get("email", "").lower().strip()
        
        if (company in processed_companies or
            domain in processed_domains or
            email in processed_emails):
            skipped.append(p)
        else:
            unique.append(p)
    
    return unique, skipped


def log_prospects(prospects: list, batch: str, status: str = "new"):
    """Append prospects to the processed log."""
    existing = load_processed_log()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for p in prospects:
        row = {
            "company": p.get("company", ""),
            "domain": p.get("domain", ""),
            "email": p.get("email", ""),
            "status": status,
            "added_at": now,
            "batch": batch,
        }
        existing.append(row)
    
    with open(PROCESSED_LOG, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in existing:
            writer.writerow(row)


def deduplicate_csv():
    """Remove duplicate rows from prospects.csv based on email/domain."""
    if not os.path.exists(CSV_FILE):
        return
    
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    seen_emails = set()
    seen_domains = set()
    unique_rows = []
    duplicates = []
    
    for row in rows:
        email = row.get("email", "").lower().strip()
        domain = row.get("domain", "").lower().strip()
        
        if email in seen_emails or domain in seen_domains:
            duplicates.append(row)
        else:
            seen_emails.add(email)
            seen_domains.add(domain)
            unique_rows.append(row)
    
    if duplicates:
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in unique_rows:
                writer.writerow(row)
        print(f"Removed {len(duplicates)} duplicates from prospects.csv")
    
    return len(duplicates)


def get_stats() -> dict:
    """Get deduplication stats."""
    log = load_processed_log()
    companies = {row["company"].lower().strip() for row in log}
    domains = {row["domain"].lower().strip() for row in log}
    emails = {row["email"].lower().strip() for row in log}
    
    batches = {}
    for row in log:
        batch = row.get("batch", "unknown")
        batches[batch] = batches.get(batch, 0) + 1
    
    return {
        "total_processed": len(log),
        "unique_companies": len(companies),
        "unique_domains": len(domains),
        "unique_emails": len(emails),
        "batches": batches,
    }
