from django.conf.urls import patterns, url, include
from pm.views import SnippetViewer, TodoList, AddTodo, TodoDetail, AddGuide
from django.contrib.auth.decorators import login_required

svnfile_urls = patterns('pm.svnclient',
  url(r'^ls$', 'svn_ls', name='svnclient-ls'),
  url(r'^cat$', 'svn_cat', name='svnclient-cat'),
  url(r'^diff$', 'svn_diff', name='svnclient-diff'),
  url(r'^text$', 'svn_text', name='svnclient-text'),
  url(r'^history$', 'svn_history', name='svnclient-history'),
  url(r'^changelog$', 'svn_log', name='svnclient-log'),
)

svn_urls = patterns('pm.svnclient',
  url(r'^$', 'svn_ls', {'filename':None}, name='svnclient-index'),
  url(r'^ls', 'svn_ls', {'filename':None}, name='svnclient-root'),
  url(r'^changelog', 'svn_log', {'filename':None}, name='svnclient-rlog'),
  url(r'^(?P<filename>[a-zA-Z0-9-./_]+)/', include(svnfile_urls)),
)

todo_urls = patterns('pm.views',
    url(r'^$', login_required(TodoList.as_view()), name='pmtodo-list'),
    url(r'^(?P<pk>[0-9]+)/$', login_required(TodoDetail.as_view()), name='pmtodo-detail'),
    url(r'^(?P<pk>[0-9]+)/Complete.py$', 'mark_complete', name='pmtodo-complete'),
    url(r'^Add.py$', login_required(AddTodo.as_view()), name='pmtodo-add'),
)

urlpatterns = patterns('',
    url(r'^Todo/', include(todo_urls)),
    url(r'^Source/', include(svn_urls)),
    url(r'^SnippetViewer$', SnippetViewer.as_view(), name='snippet-viewer'),
    url(r'^AddGuide$', AddGuide.as_view(), name='pmguide-add'),
)
