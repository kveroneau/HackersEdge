from django.db import models
import cPickle as pickle
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils.text import slugify

valid_filename = RegexValidator(r'^([\w]+\.[\w]{3})$', 'Filename must no contain spaces, and must contain 1 dot followed by a 3 character extension.')

class Host(models.Model):
    ip_addr = models.IPAddressField(db_index=True)
    data = models.TextField()
    designer = models.ForeignKey(User, blank=True, null=True)
    available = models.BooleanField(default=False)
    def __unicode__(self):
        return u'%s' % self.ip_addr
    def get_data(self):
        return pickle.loads(str(self.data))
    def get_hostname(self):
        data = self.get_data()
        return data.get('hostname', 'None set.')
    def get_filecount(self):
        data = self.get_data()
        return len(data.get('files', []))
    def get_dns(self):
        data = self.get_data()
        return data.get('dns', 'None set.')
    def get_mailboxes(self):
        data = self.get_data()
        return len(data.get('mailboxes', []))
    def get_online(self):
        data = self.get_data()
        return 'Yes' if data['online'] else 'No'
    def get_vm(self):
        data = self.get_data()
        return data.get('vm', 'Old code host')
    def get_template(self):
        data = self.get_data()
        return data.get('template', 'Custom Host')
    def save(self, pickled=True, *args, **kwargs):
        if not pickled:
            try:
                self.data = pickle.dumps(self.data)
            except:
                pass
        super(Host, self).save(*args, **kwargs)

class HostTemplate(models.Model):
    title = models.CharField(max_length=40, unique=True)
    slug = models.SlugField()
    ini = models.TextField()
    created_by = models.ForeignKey(User)
    def __unicode__(self):
        return u'%s' % self.title
    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super(HostTemplate, self).save(*args, **kwargs)
    @models.permalink
    def get_absolute_url(self):
        return ('update-template', [self.slug])

class HostFile(models.Model):
    filename = models.CharField(max_length=20, unique=True, validators=[valid_filename])
    content = models.TextField()
    created_by = models.ForeignKey(User)
    class Meta:
        ordering = ['filename', 'created_by__username']
    def __unicode__(self):
        return u'%s' % self.filename
    @models.permalink
    def get_absolute_url(self):
        return ('update-file', [self.filename])    

class MailMessage(models.Model):
    slug = models.SlugField()
    from_who = models.EmailField()
    to = models.EmailField(blank=True, null=True)
    subject = models.CharField(max_length=40)
    sent = models.DateTimeField(blank=True, null=True)
    content = models.TextField()
    created_by = models.ForeignKey(User)
    def __unicode__(self):
        return u'%s' % self.subject

class MachineConnector(models.Model):
    name = models.CharField(max_length=30)
    addr = models.CharField(max_length=30)
    def __unicode__(self):
        return u'%s' % self.name

class MachineType(models.Model):
    name = models.CharField(max_length=60)
    connector = models.ForeignKey(MachineConnector)
    template = models.ForeignKey(HostTemplate)
    is_active = models.BooleanField(default=False)
    def __unicode__(self):
        return u'%s' % self.name
