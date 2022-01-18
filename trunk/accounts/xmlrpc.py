from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http.response import HttpResponse
from accounts.models import HostPool, Character, UserProfile
from django.core.exceptions import PermissionDenied
import datetime, pyotp, hashlib

class AccountService:
    def ping(self):
        return True
    def get_user(self, username):
        try:
            user = Character.objects.get(username=username, deleted=False)
        except:
            return False
        try:
            profile = UserProfile.objects.get(user=user.user)
        except:
            return False
        if profile.otp_token:
            totp = pyotp.TOTP(profile.otp_token)
            password = hashlib.md5(totp.now()).hexdigest()
        else:
            password = user.password
        return {'username':user.user.username,
                'password':password,
                'ip_addr':user.ip_addr,
                'mailhost':user.mailhost,
                'bank':user.bank,
                'admin':user.user.is_superuser,
                'staff':user.user.is_staff,
                'designer':user.user.has_perm('henet.change_hosttemplate')}
    def get_last_login(self, username):
        try:
            user = Character.objects.get(username=username)
        except:
            return False
        last_login = user.last_login
        user.last_login = datetime.datetime.now()
        user.times_played +=1
        user.save()
        profile = user.user.userprofile
        profile.total_games +=1
        profile.save()
        return 'Never' if not last_login else '%s' % last_login
    def add_pool(self, token, pool_name, network, mailhost, dns, counter=10):
        try:
            HostPool.objects.get(network=network)
            return False
        except HostPool.DoesNotExist:
            pass
        pool = HostPool.objects.create(pool_name=pool_name, network=network, counter=counter, mailhost=mailhost, dns=dns)
        return pool.pk
    def get_counter(self, token, network):
        try:
            pool = HostPool.objects.get(network=network)
            return pool.counter
        except:
            return False
    def set_counter(self, token, network, counter):
        try:
            pool = HostPool.objects.get(network=network)
            pool.counter = counter
            pool.save()
            return True
        except:
            return False
    def superusers(self):
        users = []
        for char in Character.objects.filter(user__username='kveroneau'):
            users.append(char.username)
        return users
