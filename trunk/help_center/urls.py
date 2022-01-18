from django.conf.urls import patterns, url
from help_center.xmlrpc import rpc_service
from help_center.views import GuideList, GuideById, TopicList

urlpatterns = patterns('help_center.views',
    url(r'^$', TopicList.as_view(), name='help-index'),
    url(r'^RPC$', rpc_service),
    url(r'^Guide(?P<pk>\d+)$', GuideById.as_view(), name='help-guide-byid'),
    url(r'^(?P<slug>[\w-]+)$', GuideList.as_view(), name='help-topic'),
    url(r'^(?P<slug1>[\w-]+)/(?P<slug2>[\w-]+).html$', 'view_guide', name='help-guide'),
)
