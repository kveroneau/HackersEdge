from django.contrib.auth.backends import ModelBackend
from accounts.models import UserProfile
from django.contrib.auth.models import User
import pyotp

class OTPAuth(ModelBackend):
    def authenticate(self, username=None, password=None):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None
        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            if user.check_password(password):
                return user
            return None
        if profile.otp_token:
            totp = pyotp.TOTP(profile.otp_token)
            if totp.verify(password):
                return user
        else:
            if user.check_password(password):
                return user
        return None
