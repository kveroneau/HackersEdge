from django import forms
from henet.models import HostTemplate, HostFile, MailMessage
from cStringIO import StringIO
import ConfigParser

REQUIRED_ITEMS = {
    'machine': ('bios', 'bootaddr',),
}

class HostTemplateForm(forms.ModelForm):
    class Meta:
        model = HostTemplate
        fields = ('title', 'ini',)
    def clean_ini(self):
        ini = self.cleaned_data['ini']
        try:
            fp = StringIO(ini.encode())
            cfg = ConfigParser.SafeConfigParser()
            cfg.readfp(fp, 'host.ini')
            fp.close()
        except ConfigParser.Error, e:
            raise forms.ValidationError(str(e))
            raise forms.ValidationError('Please check your INI configuration and try again.')
        sections = cfg.sections()
        for section,items in REQUIRED_ITEMS.items():
            if section not in sections:
                raise forms.ValidationError('Missing required section: %s' % section)
            for itm in items:
                if itm not in cfg.options(section):
                    raise forms.ValidationError('Missing required item "%s" in section "%s"' % (itm, section))
        return ini

class HostFileForm(forms.ModelForm):
    class Meta:
        model = HostFile
        fields = ('filename', 'content',)

class MailMessageForm(forms.ModelForm):
    class Meta:
        model = MailMessage
        fields = ('slug', 'from_who', 'to', 'subject', 'sent', 'content',)
