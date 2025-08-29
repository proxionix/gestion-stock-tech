"""
Audit service for Stock Management System.
Handles immutable audit logging with hash chaining.
"""
import json
from typing import Any, Dict, Optional
from django.contrib.auth.models import User
from django.db import transaction
from apps.audit.models import EventLog, StockMovement, ThresholdAlert


class AuditService:
    """Service class for audit trail management."""
    
    @staticmethod
    @transaction.atomic
    def log_event(
        actor_user: User,
        entity_type: str,
        entity_id: str,
        action: str,
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> EventLog:
        """
        Log an audit event with hash chaining.
        
        Args:
            actor_user: User who performed the action
            entity_type: Type of entity affected (model name)
            entity_id: ID of the affected entity
            action: Action performed
            before_data: Entity state before change
            after_data: Entity state after change
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request correlation ID
        
        Returns:
            Created EventLog instance
        """
        # Sanitize data for JSON serialization
        if before_data:
            before_data = AuditService._sanitize_data(before_data)
        if after_data:
            after_data = AuditService._sanitize_data(after_data)
        
        # Create audit event
        event = EventLog(
            actor_user=actor_user,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_data=before_data,
            after_data=after_data,
            ip_address=ip_address,
            user_agent=user_agent[:200] if user_agent else '',  # Truncate long user agents
            request_id=request_id or ''
        )
        event.save()
        
        return event
    
    @staticmethod
    def _sanitize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize data for JSON serialization.
        Converts non-serializable objects to strings.
        """
        if not isinstance(data, dict):
            return str(data) if data is not None else None
        
        sanitized = {}
        for key, value in data.items():
            if value is None:
                sanitized[key] = None
            elif isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[key] = AuditService._sanitize_data(value)
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [AuditService._sanitize_data(item) if isinstance(item, dict) else str(item) for item in value]
            else:
                sanitized[key] = str(value)
        
        return sanitized
    
    @staticmethod
    def verify_audit_chain(start_id: Optional[str] = None, end_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify the integrity of the audit chain.
        
        Args:
            start_id: Start verification from this record ID (optional)
            end_id: End verification at this record ID (optional)
        
        Returns:
            Dictionary with verification results
        """
        query = EventLog.objects.order_by('timestamp')
        
        if start_id:
            query = query.filter(id__gte=start_id)
        if end_id:
            query = query.filter(id__lte=end_id)
        
        events = list(query)
        if not events:
            return {
                'valid': True,
                'total_records': 0,
                'verified_records': 0,
                'errors': []
            }
        
        errors = []
        verified_count = 0
        
        # Verify each record's hash
        for event in events:
            if not event.verify_hash():
                errors.append(f"Hash mismatch for record {event.id}")
            else:
                verified_count += 1
        
        # Verify chain integrity
        for i, event in enumerate(events):
            if i == 0:
                # First record should have empty prev_hash
                if event.prev_hash and event.prev_hash != '':
                    errors.append(f"First record {event.id} has non-empty prev_hash")
            else:
                # Check if prev_hash matches previous record's hash
                prev_event = events[i - 1]
                if event.prev_hash != prev_event.record_hash:
                    errors.append(f"Chain break at record {event.id}: prev_hash doesn't match previous record")
        
        return {
            'valid': len(errors) == 0,
            'total_records': len(events),
            'verified_records': verified_count,
            'errors': errors
        }
    
    @staticmethod
    def get_entity_history(entity_type: str, entity_id: str) -> list:
        """
        Get audit history for a specific entity.
        
        Args:
            entity_type: Type of entity
            entity_id: ID of entity
        
        Returns:
            List of audit events for the entity
        """
        events = EventLog.objects.filter(
            entity_type=entity_type,
            entity_id=entity_id
        ).order_by('-timestamp')
        
        history = []
        for event in events:
            history.append({
                'id': str(event.id),
                'actor': {
                    'id': event.actor_user.id,
                    'username': event.actor_user.username,
                    'full_name': event.actor_user.get_full_name(),
                },
                'action': event.action,
                'timestamp': event.timestamp.isoformat(),
                'before_data': event.before_data,
                'after_data': event.after_data,
                'ip_address': event.ip_address,
                'request_id': event.request_id,
            })
        
        return history
    
    @staticmethod
    def get_user_activity(user: User, limit: int = 100) -> list:
        """
        Get recent activity for a user.
        
        Args:
            user: User to get activity for
            limit: Maximum number of events to return
        
        Returns:
            List of recent audit events for the user
        """
        events = EventLog.objects.filter(
            actor_user=user
        ).order_by('-timestamp')[:limit]
        
        activity = []
        for event in events:
            activity.append({
                'id': str(event.id),
                'entity_type': event.entity_type,
                'entity_id': event.entity_id,
                'action': event.action,
                'timestamp': event.timestamp.isoformat(),
                'after_data': event.after_data,
            })
        
        return activity
    
    @staticmethod
    def export_audit_data(
        start_date=None,
        end_date=None,
        user_id: Optional[int] = None,
        entity_type: Optional[str] = None
    ) -> list:
        """
        Export audit data for GDPR compliance.
        
        Args:
            start_date: Start date for export
            end_date: End date for export
            user_id: Filter by specific user
            entity_type: Filter by entity type
        
        Returns:
            List of audit records for export
        """
        query = EventLog.objects.all()
        
        if start_date:
            query = query.filter(timestamp__gte=start_date)
        if end_date:
            query = query.filter(timestamp__lte=end_date)
        if user_id:
            query = query.filter(actor_user_id=user_id)
        if entity_type:
            query = query.filter(entity_type=entity_type)
        
        query = query.order_by('timestamp')
        
        export_data = []
        for event in query:
            export_data.append({
                'id': str(event.id),
                'timestamp': event.timestamp.isoformat(),
                'actor_user_id': event.actor_user.id,
                'actor_username': event.actor_user.username,
                'entity_type': event.entity_type,
                'entity_id': event.entity_id,
                'action': event.action,
                'before_data': event.before_data,
                'after_data': event.after_data,
                'ip_address': event.ip_address,
                'user_agent': event.user_agent,
                'request_id': event.request_id,
                'record_hash': event.record_hash,
            })
        
        return export_data
