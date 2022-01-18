from django.contrib import admin
from accounts.models import Character, HostPool, UserProfile, Invite
from django.contrib.auth.admin import UserAdmin
from django.template.loader import get_template
from django.template.context import Context
from django.contrib.auth.models import Group, User
from django.core.mail.message import EmailMultiAlternatives
from django.core.cache import cache
from django.conf.urls import patterns
from django.shortcuts import redirect
import random

class CharacterAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'user', 'ip_addr', 'created_on',)
    list_filter = ('deleted',)

class HostPoolAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'network', 'counter', 'is_active',)

class MyUserAdmin(UserAdmin):
    def send_invite(self, request, queryset):
        beta_grp = Group.objects.get(name='Beta Testers')
        for user in queryset:
            UserProfile.objects.create(user=user, game_access=True)
            user.groups.add(beta_grp)
            user.save()
            cache.set('game_access_%s' % user.pk, True)
            ctx = Context({'user':user})
            message = get_template('notifications/beta_invitation.txt').render(ctx)
            html = get_template('email/beta_invitation.html').render(ctx)
            msg = EmailMultiAlternatives("You've been invited to Hacker's Edge closed beta!", message, to=[user.email])
            msg.attach_alternative(html, "text/html")
            msg.send()
    actions = [send_invite]

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'game_access', 'character_limit', 'last_login',)
    def last_login(self, obj):
        return obj.user.last_login

class InviteAdmin(admin.ModelAdmin):
    list_display = ('code', 'user', 'created_on', 'taken_on', 'placed_on',)
    def get_urls(self):
        urls = super(InviteAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^generate/$', self.admin_site.admin_view(self.generate_invite)),
        )
        return my_urls + urls
    def generate_invite(self, req):
        slug = ''.join(random.choice('ABCDEFGHIJKLMNPQRSTUVWXY13456789') for _ in range(5))
        i = Invite.objects.create(code=slug)
        return redirect('admin:accounts_invite_change', i.pk)

admin.site.unregister(User)
admin.site.register(User, MyUserAdmin)
admin.site.register(Character, CharacterAdmin)
admin.site.register(HostPool, HostPoolAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Invite, InviteAdmin)
