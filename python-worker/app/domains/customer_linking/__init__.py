"""
Customer Linking Domain

This module handles the linking of anonymous user sessions (clientId)
with authenticated customers (customerId) and provides backfilling
functionality for historical events.
"""

from .scheduler import CustomerLinkingScheduler, customer_linking_scheduler

__all__ = ["CustomerLinkingScheduler", "customer_linking_scheduler"]
