from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema

from rest_framework import generics, status
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .models import *
from .serializers import *
from .tokens import check_token, make_token


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def _auth_response(user):
    return Response(
        TokenResponseSerializer((user, _tokens_for(user))).data,
        status=status.HTTP_200_OK,
    )


# ─── Регистрация ───────────────────────────────────────────────────────────────

class RegisterBuyerAPIView(APIView):
    permission_classes = []
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return _auth_response(user)


class RegisterSellerAPIView(APIView):
    permission_classes = []
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.is_seller = True
        user.save(update_fields=["is_seller"])
        return _auth_response(user)


class LoginAPIView(APIView):
    permission_classes = []
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @swagger_auto_schema(request_body=LoginSerializer)
    def post(self, request):
        email = request.data.get("email", "").lower().strip()
        password = request.data.get("password", "")
        user = authenticate(request, username=email, password=password)
        if not user:
            return Response({"error": "Неверный email или пароль"}, status=status.HTTP_401_UNAUTHORIZED)
        return _auth_response(user)


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh")).blacklist()
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Профиль ──────────────────────────────────────────────────────────────────

class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user, context={"request": request}).data)

    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PasswordChangeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.check_password(request.data.get("old_password", "")):
            return Response({"error": "Старый пароль неверен"}, status=status.HTTP_400_BAD_REQUEST)
        new_password = request.data.get("new_password", "")
        if len(new_password) < 8:
            return Response({"error": "Пароль слишком короткий"}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        return _auth_response(user)


# ─── Восстановление пароля (забыли пароль; покупатель и продавец) ─────────────

class PasswordResetAPIView(APIView):
    """Шаг 1: запрос сброса — шлём письмо со ссылкой. Всегда 200 (без раскрытия email)."""

    permission_classes = []
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @swagger_auto_schema(request_body=PasswordResetSerializer)
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"detail": "Если email зарегистрирован, письмо отправлено"}, status=status.HTTP_200_OK)

        token = make_token(user)
        url = f"{settings.PASSWORD_RESET_URL}?email={email}&token={token}"
        send_mail(
            subject="Сброс пароля — Beauty Market",
            message=(
                "Здравствуйте!\n\n"
                "Вы запросили сброс пароля. Перейдите по ссылке, чтобы задать новый пароль "
                f"(действительна 1 час):\n{url}\n\n"
                "Если вы не запрашивали сброс — проигнорируйте это письмо."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        data = {"detail": "Если email зарегистрирован, письмо отправлено"}
        if settings.DEBUG:
            # В разработке почта не уходит наружу — даём прямую ссылку для QA
            data["dev_reset_url"] = url
        return Response(data, status=status.HTTP_200_OK)


class PasswordResetConfirmAPIView(APIView):
    """Шаг 2: по ссылке из письма — установить новый пароль."""

    permission_classes = []

    @swagger_auto_schema(request_body=PasswordResetConfirmSerializer)
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = check_token(data["email"], data["token"])
        if not user:
            return Response({"detail": "Ссылка недействительна или истекла"}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(data["new_password"])
        user.save()
        return Response({"detail": "Пароль изменён"}, status=status.HTTP_200_OK)


# ─── Адреса ────────────────────────────────────────────────────────────────────

class AddressListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        if serializer.validated_data.get("is_default"):
            Address.objects.filter(user=self.request.user).update(is_default=False)
        serializer.save(user=self.request.user)


class AddressRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.validated_data.get("is_default"):
            Address.objects.filter(user=self.request.user).exclude(pk=self.get_object().pk).update(is_default=False)
        serializer.save()
