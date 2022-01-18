from django.db import models
from django.conf import settings
import urllib2, json, twitter

def post2discord(message):
    if settings.DEBUG:
        return
    req = urllib2.Request('https://discordapp.com/api/webhooks/XXXX')
    req.add_header('User-Agent', 'Hackers-Edge/1.0')
    req.add_header('Content-Type', 'application/json')
    req.add_data(json.dumps({'content':message}))
    try:
        r = urllib2.urlopen(req)
    except:
        return False
    if r.code != 204:
        return False
    return True

class Topic(models.Model):
    title = models.CharField(max_length=80)
    slug = models.SlugField()
    description = models.TextField()
    last_update = models.DateField(null=True, blank=True)
    ordering = models.IntegerField(default=100)
    is_active = models.BooleanField(default=True)
    def __unicode__(self):
        return u"%s" % self.title
    class Meta:
        ordering = ['ordering']
    @models.permalink
    def get_absolute_url(self):
        return ('help-topic', [self.slug])

class Guide(models.Model):
    title = models.CharField(max_length=80)
    slug = models.SlugField()
    topic = models.ForeignKey(Topic)
    created_on = models.DateField(auto_now_add=True)
    modified_on = models.DateField(auto_now=True)
    draft = models.BooleanField(default=False)
    content = models.TextField()
    def __unicode__(self):
        return u"%s" % self.title
    class Meta:
        ordering = ['-modified_on']
    def save(self, *args, **kwargs):
        super(Guide, self).save(*args, **kwargs)
        topic = self.topic
        topic.last_update = self.modified_on
        topic.save()
        if not self.draft:
            t = twitter.Twitter(auth=twitter.OAuth(settings.TOKEN, settings.TOKEN_KEY, settings.CONSUMER_KEY, settings.CONSUMER_SECRET))
            t.statuses.update(status='Game Guide updated -- %s: %s -- http://www.hackers-edge.com%s #hackersedge' % (topic.title, self.title, self.get_absolute_url()))
            post2discord('Game Guide updated -- %s: %s -- http://www.hackers-edge.com%s' % (topic.title, self.title, self.get_absolute_url()))
    @models.permalink
    def get_absolute_url(self):
        return ('help-guide', [self.topic.slug, self.slug])
