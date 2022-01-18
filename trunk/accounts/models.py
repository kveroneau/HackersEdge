from django.db import models
from django.contrib.auth.models import User
import urllib2, json

def post2discord(message):
    try:
        req = urllib2.Request('https://discordapp.com/api/webhooks/XXXX')
        req.add_header('User-Agent', 'Hackers-Edge/1.0')
        req.add_header('Content-Type', 'application/json')
        req.add_data(json.dumps({'content':"%s" % message}))
        urllib2.urlopen(req)
    except:
        pass

class UserProfile(models.Model):
    user = models.OneToOneField(User)
    game_access = models.BooleanField(default=False)
    character_limit = models.PositiveSmallIntegerField(default=3)
    total_games = models.PositiveIntegerField(default=0)
    otp_token = models.CharField(max_length=16, null=True, blank=True)
    notifications = models.BooleanField(default=True)
    def __unicode__(self):
        return u"%s's Profile" % self.user

class Character(models.Model):
    user = models.ForeignKey(User)
    username = models.CharField(max_length=20)
    password = models.CharField(max_length=32)
    ip_addr = models.IPAddressField()
    mailhost = models.IPAddressField()
    bank = models.IPAddressField()
    created_on = models.DateTimeField(auto_now_add=True)
    last_login = models.DateField(blank=True, null=True)
    times_played = models.PositiveIntegerField(default=0)
    deleted = models.BooleanField(default=False)
    def __unicode__(self):
        return u'%s' % self.username
    def save(self, *args, **kwargs):
        self.username = self.username.lower()
        super(Character, self).save(*args, **kwargs)

class HostPool(models.Model):
    pool_name = models.CharField(max_length=60)
    network = models.IPAddressField(db_index=True)
    counter = models.PositiveSmallIntegerField(default=10)
    mailhost = models.IPAddressField()
    dns = models.IPAddressField()
    bank = models.IPAddressField()
    is_active = models.BooleanField(default=True)
    staff_only = models.BooleanField(default=False)
    def __unicode__(self):
        return u'%s' % self.pool_name
    def save(self, *args, **kwargs):
        if self.counter > 254:
            self.is_active = False
            post2discord('Network pool %s has been depleted.' % self.pool_name)
        super(HostPool, self).save(*args, **kwargs)

class Invite(models.Model):
    PLACED_ON_TYPES = (
        (0, 'Directly'),
        (1, 'Twitter'),
        (2, 'Google+'),
        (3, 'Python Diary'),
        (4, 'SDF Board'),
        (5, '8bit MUSH'),
        (6, 'SlimeSalad'),
        (7, 'Python IRC'),
        (8, 'Gopher list'),
        (9, 'Player Invite'),
        (10, 'Facebook Group'),
        (11, 'Discord'),
        (100, 'Other'),
    )
    code = models.SlugField()
    user = models.ForeignKey(User, blank=True, null=True)
    created_on = models.DateField(auto_now_add=True)
    taken_on = models.DateField(blank=True, null=True)
    placed_on = models.SmallIntegerField(choices=PLACED_ON_TYPES, null=True)
    created_by = models.ForeignKey(User, blank=True, null=True, related_name='sent_invites')
    def __unicode__(self):
        return u'%s placed on %s' % (self.code.upper(), self.get_placed_on_display())
