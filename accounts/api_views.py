from django.contrib.auth.signals import user_logged_in
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.forms import LoginForm, RegisterForm
from accounts.serializers import UserSerializer
from accounts.views import form_errors

NOT_AN_OBJECT = {'errors': {'__all__': ['Send the fields as a JSON object or form data.']}}


# Register and login take no credentials, so a stale token or a browser session
# never blocks them, and session CSRF checks do not apply.
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def register_api(request):
    # A JSON list or string has no fields for the form to read
    if not isinstance(request.data, dict):
        return Response(NOT_AN_OBJECT, status=status.HTTP_400_BAD_REQUEST)

    # Same rules and messages as the website's sign-up form
    form = RegisterForm(data=request.data)
    if not form.is_valid():
        return Response({'errors': form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)

    user = form.save()
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_api(request):
    if not isinstance(request.data, dict):
        return Response(NOT_AN_OBJECT, status=status.HTTP_400_BAD_REQUEST)

    # LoginForm checks the password and rejects inactive accounts
    form = LoginForm(request, data=request.data)
    if not form.is_valid():
        return Response({'errors': form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)

    user = form.get_user()
    # Updates user.last_login, as a website login does
    user_logged_in.send(sender=user.__class__, request=request, user=user)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, **UserSerializer(user).data})


# Logout and me accept only a token, so a missing or bad one gives 401
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def logout_api(request):
    request.auth.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def me_api(request):
    return Response(UserSerializer(request.user).data)
