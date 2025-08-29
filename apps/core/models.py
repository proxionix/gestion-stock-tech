"""
Core models for Stock Management System.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class TimestampedModel(models.Model):
    """Abstract base model with timestamp fields."""
    created_at = models.DateTimeField(_('Created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)
    
    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Abstract base model with UUID primary key."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class Meta:
        abstract = True


class BaseModel(TimestampedModel, UUIDModel):
    """Base model combining timestamps and UUID."""
    
    class Meta:
        abstract = True
