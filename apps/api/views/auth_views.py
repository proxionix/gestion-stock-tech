"""
Authentication API views for Stock Management System.
"""
import jwt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import authenticate
from apps.api.authentication import JWTService
from apps.api.serializers import LoginSerializer, TokenRefreshSerializer, ProfileSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    User login endpoint.
    Returns JWT tokens on successful authentication.
    """
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        tokens = JWTService.generate_tokens(user)
        
        return Response({
            'tokens': tokens,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'profile': ProfileSerializer(user.profile).data if hasattr(user, 'profile') else None
            }
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """
    Refresh access token using refresh token.
    """
    serializer = TokenRefreshSerializer(data=request.data)
    if serializer.is_valid():
        try:
            refresh_token = serializer.validated_data['refresh_token']
            tokens = JWTService.refresh_access_token(refresh_token)
            return Response(tokens)
        except jwt.InvalidTokenError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """
    Get current user information.
    """
    user = request.user
    data = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_staff': user.is_staff,
        'is_active': user.is_active,
        'date_joined': user.date_joined,
        'profile': None
    }
    
    if hasattr(user, 'profile'):
        data['profile'] = ProfileSerializer(user.profile).data
    
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    User logout endpoint.
    Note: JWT tokens are stateless, so this is mainly for client-side cleanup.
    In a production system, you might maintain a blacklist of revoked tokens.
    """
    return Response({'message': 'Successfully logged out'})
