from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    title = models.CharField(max_length=40)
    def __unicode__(self):
        return u"%s" % self.title
    class Meta:
        verbose_name_plural = 'Categories'

class Snippet(models.Model):
    title = models.CharField(max_length=80)
    added_on = models.DateTimeField(auto_now_add=True)
    edited_on = models.DateTimeField(auto_now=True)
    content = models.TextField()
    category = models.ForeignKey(Category)
    def __unicode__(self):
        return u"%s" % self.title
    class Meta:
        ordering = ['-edited_on']

class TodoItem(models.Model):
    title = models.CharField(max_length=80)
    added_on = models.DateField(auto_now_add=True)
    added_by = models.ForeignKey(User)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, null=True)
    completed = models.BooleanField(default=False)
    staff_only = models.BooleanField(default=False)
    def __unicode__(self):
        return u'%s' % self.title
    @models.permalink
    def get_absolute_url(self):
        return ('pmtodo-detail', [self.pk])
    class Meta:
        ordering = ['-added_on']
