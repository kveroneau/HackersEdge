from django.db import models
from django.contrib.auth.models import User, Group

class Topic(models.Model):
    title = models.CharField(max_length=40)
    slug = models.SlugField()
    description = models.TextField()
    valid_group = models.ForeignKey(Group, blank=True, null=True)
    ordering = models.IntegerField(default=100)
    def __unicode__(self):
        return u"%s" % self.title
    class Meta:
        ordering = ['ordering']
    @models.permalink
    def get_absolute_url(self):
        return ('forum-topic', [self.slug])

class Thread(models.Model):
    subject = models.CharField(max_length=80)
    started_by = models.CharField(max_length=40)
    started_on = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    topic = models.ForeignKey(Topic)
    is_locked = models.BooleanField(default=False)
    valid_group = models.ForeignKey(Group, blank=True, null=True)
    class Meta:
        ordering = ['-last_updated']
    def __unicode__(self):
        return u"%s" % self.subject
    @models.permalink
    def get_absolute_url(self):
        return ('forum-thread', [str(self.pk)])

class Post(models.Model):
    subject = models.CharField(max_length=80)
    body = models.TextField()
    user = models.ForeignKey(User)
    username = models.CharField(max_length=40)
    posted = models.DateTimeField(auto_now_add=True)
    thread = models.ForeignKey(Thread)
    class Meta:
        ordering = ['posted']
    def __unicode__(self):
        return u"%s" % self.subject
    @models.permalink
    def get_absolute_url(self):
        return ('forum-post', [self.pk])
