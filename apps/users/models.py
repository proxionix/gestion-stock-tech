"""
User models for Stock Management System.
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimestampedModel


class UserRole(models.TextChoices):
    """User role choices."""
    ADMIN = 'ADMIN', _('Administrator')
    TECH = 'TECH', _('Technician')


class LanguageChoice(models.TextChoices):
    """Language preference choices."""
    FR_BE = 'fr-be', _('French (Belgium)')
    NL_BE = 'nl-be', _('Dutch (Belgium)')
    EN = 'en', _('English')


class Profile(TimestampedModel):
    """
    User profile extending Django User model.
    Contains role and language preferences.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('User')
    )
    
    role = models.CharField(
        max_length=10,
        choices=UserRole.choices,
        default=UserRole.TECH,
        verbose_name=_('Role')
    )
    
    language_pref = models.CharField(
        max_length=10,
        choices=LanguageChoice.choices,
        default=LanguageChoice.FR_BE,
        verbose_name=_('Language preference')
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active')
    )
    
    employee_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_('Employee ID')
    )
    
    department = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Department')
    )
    
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Phone number')
    )
    
    class Meta:
        verbose_name = _('Profile')
        verbose_name_plural = _('Profiles')
        db_table = 'users_profile'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['employee_id']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"
    
    @property
    def is_admin(self):
        """Check if user is an administrator."""
        return self.role == UserRole.ADMIN
    
    @property
    def is_technician(self):
        """Check if user is a technician."""
        return self.role == UserRole.TECH
    
    @property
    def display_name(self):
        """Get user's display name."""
        return self.user.get_full_name() or self.user.username


class PINCode(TimestampedModel):
    """
    Temporary PIN codes for handover confirmation.
    Auto-expire after configured time.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pin_codes',
        verbose_name=_('User')
    )
    
    pin_hash = models.CharField(
        max_length=128,
        verbose_name=_('PIN hash')
    )
    
    demande_id = models.UUIDField(
        verbose_name=_('Related demand ID')
    )
    
    expires_at = models.DateTimeField(
        verbose_name=_('Expires at')
    )
    
    is_used = models.BooleanField(
        default=False,
        verbose_name=_('Used')
    )
    
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Used at')
    )
    
    class Meta:
        verbose_name = _('PIN Code')
        verbose_name_plural = _('PIN Codes')
        db_table = 'users_pincode'
        indexes = [
            models.Index(fields=['user', 'demande_id']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['is_used']),
        ]
    
    def __str__(self):
        return f"PIN for {self.user.username} - Demand {self.demande_id}"
    
    @property
    def is_expired(self):
        """Check if PIN is expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        """Check if PIN is valid (not used and not expired)."""
        return not self.is_used and not self.is_expired
