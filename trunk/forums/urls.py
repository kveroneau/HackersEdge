from django.conf.urls import patterns, url
from django.views.generic.list import ListView
from forums.models import Topic
from forums.views import post, new_thread, lock_thread, ThreadList, PostList
from forums.xmlrpc import rpc_service

urlpatterns = patterns('',
    url(r'^$', ListView.as_view(model=Topic), name='forum-index'),
    url(r'^RPC$', rpc_service),
    url(r'^Thread(?P<pk>\d+)$', PostList.as_view(), name='forum-thread'),
    url(r'^Thread(?P<pk>\d+)/Post$', post, name='forum-post'),
    url(r'^Thread(?P<pk>\d+)/Lock$', lock_thread, name='forum-lockthread'),
    url(r'^(?P<slug>[\w-]+)$', ThreadList.as_view(), name='forum-topic'),
    url(r'^(?P<slug>[\w-]+)/NewThread$', new_thread, name='forum-newthread'),
)
