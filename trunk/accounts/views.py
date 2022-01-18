import hashlib
from django.views.generic.edit import FormView, DeleteView
from accounts.forms import CharacterForm, InviteForm, PasswordForm
from django.shortcuts import redirect, render
from accounts.models import Character, UserProfile, Invite
from django.views.generic.list import ListView
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.views.generic.base import TemplateView
from django.core.mail import mail_admins
from django.template.loader import get_template
from django.template.context import Context
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from henet.models import Host
from django.contrib.auth.decorators import login_required
from registration.backends.default.views import RegistrationView
from registration.forms import RegistrationFormUniqueEmail
from django.http.response import Http404, HttpResponse, HttpResponseRedirect
from django.conf import settings
import random, pyotp, urllib, datetime, urllib2, json, pickle
from django.contrib.auth import logout

class Register(RegistrationView):
    form_class = RegistrationFormUniqueEmail

class NewCharacter(FormView):
    form_class = CharacterForm
    template_name = 'xml/create_character.xml'
    content_type = 'text/xml'
    def dispatch(self, request, *args, **kwargs):
        try:
            profile = UserProfile.objects.get(user=request.user)
            ga = profile.game_access
        except:
            ga = False
        if not ga:
            raise PermissionDenied
        if request.user.character_set.filter(deleted=False).count() >= profile.character_limit:
            messages.error(request, 'You can only create %s character players at this time.' % profile.character_limit)
            return redirect('character_list')
        return super(NewCharacter, self).dispatch(request, *args, **kwargs)
    def get_form(self, form_class):
        form = super(NewCharacter, self).get_form(form_class)
        qs = form.fields['network'].queryset
        if not self.request.user.is_staff:
            qs = qs.filter(staff_only=False)
        form.fields['network'].queryset = qs
        return form
    def form_valid(self, form):
        username = form.cleaned_data['username']
        password = hashlib.md5(form.cleaned_data['password']).hexdigest()
        pool = form.cleaned_data['network']
        mtype = form.cleaned_data['machine_type']
        ip_addr = '%s%s' % (pool.network[:-1], pool.counter)
        pool.counter +=1
        pool.save()
        user = self.request.user
        data = {'new':True, 'online':False, 'dns':pool.dns,
                'vm':mtype.connector.addr, 'template': mtype.template.slug}
        Character.objects.create(user=user, username=username, password=password, ip_addr=ip_addr, mailhost=pool.mailhost, bank=pool.bank)
        Host.objects.create(ip_addr=ip_addr, data=pickle.dumps(data))
        if not settings.DEBUG:
            try:
                req = urllib2.Request('https://discordapp.com/api/webhooks/XXXX')
                req.add_header('User-Agent', 'Hackers-Edge/1.0')
                req.add_header('Content-Type', 'application/json')
                req.add_data(json.dumps({'content':"Let's all welcome %s to Hacker's Edge, who is running a %s!" % (username, mtype)}))
                urllib2.urlopen(req)
            except:
                pass
        return HttpResponse(b'{"st":"xlink", "xml":"accounts/Characters/", "id":"ctx"}', content_type='application/json')
        #return redirect('character_list')

class CharacterList(ListView):
    model = Character
    template_name = 'xml/character_list.xml'
    content_type = 'text/xml'
    def get_queryset(self):
        return super(CharacterList, self).get_queryset().filter(user=self.request.user, deleted=False)

class DeleteCharacter(DeleteView):
    model = Character
    def get_queryset(self):
        return super(DeleteCharacter, self).get_queryset().filter(user=self.request.user)
    def get_success_url(self):
        host = Host.objects.get(ip_addr=self.object.ip_addr)
        host.delete()
        return reverse('character_list')
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.deleted = True
        self.object.save()
        return HttpResponseRedirect(success_url)

class Terminal(TemplateView):
    template_name = 'terminal.html'
    banner = False
    ws_url = ''
    telnet_port = '1337'
    title = 'Play Game'
    def get_context_data(self, **kwargs):
        ctx = super(Terminal, self).get_context_data(**kwargs)
        ctx.update({'banner':self.banner, 'ws_url':self.ws_url,
                    'telnet_port':self.telnet_port, 'title':self.title})
        return ctx

class VT100(TemplateView):
    template_name = 'xml/vt100.xml'
    content_type = 'text/xml'
    ws_url = ''
    telnet_port = '1337'
    title = 'Play Game'
    def get_context_data(self, **kwargs):
        ctx = super(VT100, self).get_context_data(**kwargs)
        ctx.update({'ws_url':self.ws_url,
                    'telnet_port':self.telnet_port, 'title':self.title})
        return ctx

class RedeemInvite(FormView):
    form_class = InviteForm
    template_name = 'accounts/character_list.html'
    def form_valid(self, form):
        user = self.request.user
        code = form.cleaned_data['invite_code']
        invite = Invite.objects.get(code=code)
        invite.user = user
        invite.save()
        mail_admins('Beta Invite code redeemed!', get_template('notifications/invite_redeem.txt').render(Context({'invite':invite})))
        beta_grp = Group.objects.get(name='Beta Testers')
        UserProfile.objects.create(user=user, game_access=True)
        user.groups.add(beta_grp)
        user.save()
        cache.set('game_access_%s' % user.pk, True)
        messages.success(self.request, "Welcome to Hacker's Edge closed Beta!")
        return redirect('character_list')

class CharacterPassword(FormView):
    form_class = PasswordForm
    template_name = 'accounts/character_password.html'
    def get_context_data(self, **kwargs):
        ctx = super(CharacterPassword, self).get_context_data(**kwargs)
        ctx.update({'pk': self.kwargs['pk']})
        return ctx
    def form_valid(self, form):
        password = hashlib.md5(form.cleaned_data['password']).hexdigest()
        try:
            character = Character.objects.get(user=self.request.user, pk=int(self.kwargs['pk']))
        except Character.DoesNotExist:
            messages.error(self.request, 'Error changing password!')
            return redirect('character_list')
        character.password = password
        character.save()
        messages.success(self.request, 'The password for "%s" has been updated.' % character.username)
        return redirect('character_list')

class InviteList(ListView):
    model = Invite
    def get_queryset(self):
        return super(InviteList, self).get_queryset().filter(created_by=self.request.user)
    def dispatch(self, request, *args, **kwargs):
        try:
            profile = UserProfile.objects.get(user=request.user)
            ga = profile.game_access
        except:
            ga = False
        if not ga:
            raise PermissionDenied
        return super(InviteList, self).dispatch(request, *args, **kwargs)

@login_required
def create_invite(req):
    try:
        profile = UserProfile.objects.get(user=req.user)
        ga = profile.game_access
    except:
        ga = False
    if not ga:
        raise PermissionDenied
    slug = ''.join(random.choice('ABCDEFGHIJKLMNPQRSTUVWXY13456789') for _ in range(5))
    Invite.objects.create(code=slug, placed_on=9, created_by=req.user)
    messages.success(req, 'Invite successfully created.')
    return redirect('invite_list')

@login_required
def qr_code(req):
    try:
        profile = UserProfile.objects.get(user=req.user)
    except:
        raise Http404
    if not profile.otp_token:
        profile.otp_token = pyotp.random_base32()
        profile.save()
    uri = 'otpauth://totp/Hacker%%27s%%20Edge:%s?secret=%s&issuer=Hacker%%27s%%20Edge' % (req.user.username,profile.otp_token)
    o=urllib.urlopen('https://chart.googleapis.com/chart?cht=qr&chs=200x200&chl=%s' % urllib.quote(uri))
    resp = HttpResponse(o.read(), 'image/png')
    return resp

@login_required
def google_auth(req):
    try:
        profile = UserProfile.objects.get(user=req.user)
    except:
        raise Http404
    if profile.otp_token or req.GET.has_key('continue'):
        return render(req, 'accounts/google_authenticator.html')
    return render(req, 'accounts/otp_confirm.html')

@login_required
def statistics(req):
    if not req.user.is_superuser:
        raise Http404
    now = datetime.datetime.now()
    day30 = now-datetime.timedelta(days=30)
    day1 = now-datetime.timedelta(days=365)
    ctx = {}
    ctx['active30'] = User.objects.filter(last_login__gt=day30).count()
    ctx['active1'] = User.objects.filter(last_login__gt=day1).count()
    ctx['signup30'] = User.objects.filter(date_joined__gt=day30).count()
    ctx['signup1'] = User.objects.filter(date_joined__gt=day1).count()
    ctx['played30'] = Character.objects.filter(last_login__gt=day30).count()
    ctx['played1'] = Character.objects.filter(last_login__gt=day1).count()
    ctx['gauth'] = UserProfile.objects.filter(otp_token__isnull=False).count()
    if req.GET.has_key('discord'):
        dreq = urllib2.Request('https://discordapp.com/api/webhooks/XXXX')
        dreq.add_header('User-Agent', 'Hackers-Edge/1.0')
        dreq.add_header('Content-Type', 'application/json')
        dreq.add_data(json.dumps({'content':'Up to date statistics -- Sign-ups in the past 30 days: %s' % ctx['signup30']}))
        r = urllib2.urlopen(dreq)
        if r.code != 204:
            messages.error(req, 'Unable to post statistics to Discord.')
    return render(req, 'accounts/statistics.html', ctx)

@login_required
def remove_account(req):
    if req.method == 'GET':
        return render(req, 'accounts/remove_confirm.html')
    user = req.user
    user.delete()
    logout(req)
    return render(req, 'accounts/account_removed.html')
