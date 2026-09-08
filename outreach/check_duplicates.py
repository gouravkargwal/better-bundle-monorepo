#!/usr/bin/env python3
"""Check for duplicate prospects before adding to CSV.

Usage:
    python check_duplicates.py <company> <domain> <email>
    
Returns:
    EXIT 0 - not a duplicate (safe to add)
    EXIT 1 - duplicate found (skip this prospect)
"""
import csv
import sys
import os

PROCESSED_LOG = os.path.join(os.path.dirname(__file__), "processed_log.csv")
CSV_FILE = os.path.join(os.path.dirname(__file__), "prospects.csv")
DB_PATH = os.path.join(os.path.dirname(__file__), "outreach.db")


def check_duplicate(company: str, domain: str, email: str) -> dict:
    """Check if a prospect is already processed. Returns dict with match info."""
    company_lower = company.lower().strip()
    domain_lower = domain.lower().strip()
    email_lower = email.lower().strip()
    
    # Check processed log
    if os.path.exists(PROCESSED_LOG):
        with open(PROCESSED_LOG, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row["company"].lower().strip() == company_lower or
                    row["domain"].lower().strip() == domain_lower or
                    row["email"].lower().strip() == email_lower):
                    return {
                        "is_duplicate": True,
                        "match_type": "processed_log",
                        "matched_on": row["company"],
                        "status": row.get("status", "unknown"),
                        "batch": row.get("batch", "unknown"),
                        "reason": row.get("reason", ""),
                    }
    
    # Check CSV
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row.get("company", "").lower().strip() == company_lower or
                    row.get("domain", "").lower().strip() == domain_lower or
                    row.get("email", "").lower().strip() == email_lower):
                    return {
                        "is_duplicate": True,
                        "match_type": "csv",
                        "matched_on": row.get("company", ""),
                    }
    
    # Check database
    if os.path.exists(DB_PATH):
        import sqlite3
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        
        # Check by email
        row = con.execute(
            "SELECT company, status FROM prospects WHERE LOWER(email) = ?",
            (email_lower,)
        ).fetchone()
        if row:
            con.close()
            return {
                "is_duplicate": True,
                "match_type": "database_email",
                "matched_on": row["company"],
                "status": row["status"],
            }
        
        # Check by domain
        row = con.execute(
            "SELECT company, status FROM prospects WHERE LOWER(domain) = ?",
            (domain_lower,)
        ).fetchone()
        if row:
            con.close()
            return {
                "is_duplicate": True,
                "match_type": "database_domain",
                "matched_on": row["company"],
                "status": row["status"],
            }
        
        # Check by company name
        row = con.execute(
            "SELECT company, status FROM prospects WHERE LOWER(company) = ?",
            (company_lower,)
        ).fetchone()
        if row:
            con.close()
            return {
                "is_duplicate": True,
                "match_type": "database_company",
                "matched_on": row["company"],
                "status": row["status"],
            }
        
        con.close()
    
    return {"is_duplicate": False}


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python check_duplicates.py <company> <domain> <email>")
        sys.exit(2)
    
    company = sys.argv[1]
    domain = sys.argv[2]
    email = sys.argv[3]
    
    result = check_duplicate(company, domain, email)
    
    if result["is_duplicate"]:
        print(f"DUPLICATE: {result['match_type']} - {result['matched_on']}")
        if "status" in result:
            print(f"  Status: {result['status']}")
        if "batch" in result:
            print(f"  Batch: {result['batch']}")
        if result.get("reason"):
            print(f"  Reason: {result['reason']}")
        sys.exit(1)
    else:
        print("OK: Not a duplicate")
        sys.exit(0)
