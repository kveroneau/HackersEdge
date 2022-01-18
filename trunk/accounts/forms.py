from django import forms
from django.core.validators import RegexValidator
from accounts.models import Character, HostPool, Invite
from henet.models import MachineType
import datetime

valid_username = RegexValidator(r'^([a-z]+[a-z0-9\_]*)$', 'Username must start with a letter and contain only lowercase alphanumeric characters.')
valid_code = RegexValidator(r'^([a-zA-Z0-9]*)$', 'Invalid invite code, please confirm and try again.')

INVALID_USERNAMES = ('root',
                     'admin',
                     'administrator',
                     'help',
                     'new',
                     'create',
                     'guest',
                     'kveroneau',
                     'fuck',
                     'fag',
                     'fagget',
                     'sex',)

class CharacterForm(forms.Form):
    username = forms.CharField(max_length=20, validators=[valid_username])
    password = forms.CharField(widget=forms.PasswordInput)
    network = forms.ModelChoiceField(queryset=HostPool.objects.filter(is_active=True))
    machine_type = forms.ModelChoiceField(queryset=MachineType.objects.filter(is_active=True))
    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if username in INVALID_USERNAMES:
            raise forms.ValidationError('This username cannot be used, please choose another.')
        try:
            Character.objects.get(username=username)
            exists = True
        except Character.DoesNotExist:
            exists = False
        if exists:
            raise forms.ValidationError('This username is already in use, please choose another.')
        return username

class InviteForm(forms.Form):
    invite_code = forms.CharField(max_length=5, validators=[valid_code])
    def clean_invite_code(self):
        code = self.cleaned_data['invite_code'].upper()
        try:
            invite = Invite.objects.get(code=code)
        except Invite.DoesNotExist:
            raise forms.ValidationError('Invalid invite code, please confirm and try again.')
        if invite.taken_on:
            raise forms.ValidationError('This invite code was already redeemed by another player.')
        invite.taken_on = datetime.date.today()
        invite.save()
        return code

class PasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput)
