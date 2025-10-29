"""
Core models for BetterBundle Admin Dashboard
"""

from django.db import models
from django.contrib.auth.models import User


class TimeStampedModel(models.Model):
    """
    Abstract base class that provides self-updating
    'created' and 'modified' fields.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """
    Base model with common fields
    """

    id = models.CharField(max_length=255, primary_key=True)

    class Meta:
        abstract = True
