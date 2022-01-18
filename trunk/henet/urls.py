from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required
from henet.views import TemplateList, FileList, EditTemplate, CreateTemplate,\
    CreateFile, EditFile, HostList

urlpatterns = patterns('',
    url(r'HostTemplates/$', login_required(TemplateList.as_view()), name='template-list'),
    url(r'HostTemplates/Create$', login_required(CreateTemplate.as_view()), name='create-template'),
    url(r'HostFiles/$', login_required(FileList.as_view()), name='file-list'),
    url(r'HostFiles/Create$', login_required(CreateFile.as_view()), name='create-file'),
    url(r'HostTempates/(?P<slug>[\w-]+)$', login_required(EditTemplate.as_view()), name='update-template'),
    url(r'HostFiles/(?P<filename>[\w]+\.[\w]{3})$', login_required(EditFile.as_view()), name='update-file'),
    url(r'Hosts/$', login_required(HostList.as_view()), name='host-list'),
)
