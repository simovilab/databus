"""
JWT authentication views and custom token claims.
"""
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer to include user role and additional claims."""
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add custom claims
        user = self.user
        
        # Get operator role if exists
        role = 'user'
        operator_id = None
        companies = []
        
        if hasattr(user, 'operator'):
            operator = user.operator
            role = operator.role
            operator_id = operator.id
            companies = [comp.id for comp in operator.company.all()]
        elif user.is_staff or user.is_superuser:
            role = 'admin'
        
        # Add user info to response
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': role,
            'operator_id': operator_id,
            'companies': companies,
            'is_staff': user.is_staff,
        }
        
        return data
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims to token
        token['username'] = user.username
        token['email'] = user.email
        
        # Add role
        if hasattr(user, 'operator'):
            token['role'] = user.operator.role
            token['operator_id'] = user.operator.id
        elif user.is_staff or user.is_superuser:
            token['role'] = 'admin'
        else:
            token['role'] = 'user'
        
        return token


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    JWT token obtain view with custom claims.
    
    POST /api/auth/token/
    Request:
    {
        "username": "operator01",
        "password": "password123"
    }
    
    Response:
    {
        "access": "eyJ0eXAiOiJKV1QiLCJhbG...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbG...",
        "user": {
            "id": 1,
            "username": "operator01",
            "role": "operator",
            "operator_id": "OP001",
            "companies": ["company001"]
        }
    }
    """
    serializer_class = CustomTokenObtainPairSerializer


class CustomTokenRefreshView(TokenRefreshView):
    """
    JWT token refresh view with token rotation.
    
    POST /api/auth/token/refresh/
    Request:
    {
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbG..."
    }
    
    Response:
    {
        "access": "eyJ0eXAiOiJKV1QiLCJhbG...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbG..."  # New refresh token (rotation)
    }
    """
    pass


class TokenVerifyView(APIView):
    """
    Verify JWT token and return user info.
    
    GET /api/auth/verify/
    Headers:
        Authorization: Bearer <access_token>
    
    Response:
    {
        "valid": true,
        "user": {
            "id": 1,
            "username": "operator01",
            "role": "operator",
            ...
        }
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get operator info
        role = 'user'
        operator_id = None
        companies = []
        
        if hasattr(user, 'operator'):
            operator = user.operator
            role = operator.role
            operator_id = operator.id
            companies = [comp.id for comp in operator.company.all()]
        elif user.is_staff or user.is_superuser:
            role = 'admin'
        
        return Response({
            'valid': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': role,
                'operator_id': operator_id,
                'companies': companies,
                'is_staff': user.is_staff,
            }
        })


class LogoutView(APIView):
    """
    Logout view that blacklists the refresh token.
    
    POST /api/auth/logout/
    Request:
    {
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbG..."
    }
    
    Response:
    {
        "message": "Successfully logged out"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {"message": "Successfully logged out"},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
