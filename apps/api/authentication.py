"""
JWT Authentication for Stock Management System API.
"""
import jwt
from datetime import datetime, timedelta
from typing import Optional, Tuple
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from rest_framework import authentication, exceptions


class JWTAuthentication(authentication.BaseAuthentication):
    """
    JWT Authentication class for DRF.
    """
    
    def authenticate(self, request) -> Optional[Tuple[User, dict]]:
        """
        Authenticate user using JWT token.
        
        Returns:
            Tuple of (user, token_payload) or None if authentication fails
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if not auth_header:
            return None
        
        try:
            auth_method, token = auth_header.split(' ', 1)
        except ValueError:
            return None
        
        if auth_method.lower() != 'bearer':
            return None
        
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed(_('Token has expired'))
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed(_('Invalid token'))
        
        try:
            user = User.objects.get(id=payload['user_id'])
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('User not found'))
        
        if not user.is_active:
            raise exceptions.AuthenticationFailed(_('User account is disabled'))
        
        return (user, payload)
    
    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response.
        """
        return 'Bearer'


class JWTService:
    """Service for JWT token management."""
    
    @staticmethod
    def generate_tokens(user: User) -> dict:
        """
        Generate access and refresh tokens for a user.
        
        Args:
            user: User to generate tokens for
        
        Returns:
            Dictionary with access_token and refresh_token
        """
        now = datetime.utcnow()
        
        # Access token payload (expires in 1 hour)
        access_payload = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff,
            'iat': now,
            'exp': now + timedelta(hours=1),
            'type': 'access'
        }
        
        # Refresh token payload (expires in 7 days)
        refresh_payload = {
            'user_id': user.id,
            'iat': now,
            'exp': now + timedelta(days=7),
            'type': 'refresh'
        }
        
        access_token = jwt.encode(
            access_payload,
            settings.SECRET_KEY,
            algorithm='HS256'
        )
        
        refresh_token = jwt.encode(
            refresh_payload,
            settings.SECRET_KEY,
            algorithm='HS256'
        )
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': 3600,  # 1 hour in seconds
        }
    
    @staticmethod
    def refresh_access_token(refresh_token: str) -> dict:
        """
        Generate a new access token using a refresh token.
        
        Args:
            refresh_token: Valid refresh token
        
        Returns:
            Dictionary with new access_token
        
        Raises:
            jwt.InvalidTokenError: If refresh token is invalid or expired
        """
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            raise jwt.InvalidTokenError("Refresh token has expired")
        except jwt.InvalidTokenError:
            raise jwt.InvalidTokenError("Invalid refresh token")
        
        if payload.get('type') != 'refresh':
            raise jwt.InvalidTokenError("Token is not a refresh token")
        
        try:
            user = User.objects.get(id=payload['user_id'])
        except User.DoesNotExist:
            raise jwt.InvalidTokenError("User not found")
        
        if not user.is_active:
            raise jwt.InvalidTokenError("User account is disabled")
        
        # Generate new access token
        now = datetime.utcnow()
        access_payload = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff,
            'iat': now,
            'exp': now + timedelta(hours=1),
            'type': 'access'
        }
        
        access_token = jwt.encode(
            access_payload,
            settings.SECRET_KEY,
            algorithm='HS256'
        )
        
        return {
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': 3600,  # 1 hour in seconds
        }
    
    @staticmethod
    def validate_token(token: str) -> Optional[dict]:
        """
        Validate a JWT token and return its payload.
        
        Args:
            token: JWT token to validate
        
        Returns:
            Token payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256']
            )
            return payload
        except jwt.InvalidTokenError:
            return None
