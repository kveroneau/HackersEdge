from django.http import HttpResponse, Http404
from django.shortcuts import render
import pysvn, datetime
from django.core.exceptions import PermissionDenied
from django.conf import settings

node_kind = pysvn.__dict__['node_kind']
opt_revision_kind = pysvn.__dict__['opt_revision_kind']
ClientError = pysvn.__dict__['ClientError']
Revision = pysvn.__dict__['Revision']

SVN_URL = settings.SVN_URL

def admin_required(func):
    def wrapped_view(req, *args, **kwargs):
        if not req.user.is_superuser:
            raise PermissionDenied
        return func(req, *args, **kwargs)
    return wrapped_view

def get_revision(req):
    rev = None
    if 'rev' in req.GET:
        try:
            rev = int(req.GET['rev'])
        except ValueError:
            rev = None
    if rev:
        return Revision(opt_revision_kind.number, rev)
    return Revision(opt_revision_kind.head)

@admin_required
def svn_ls(req, filename):
    svn_url = SVN_URL
    if filename:
        svn_url += '/%s' % filename
    svn = pysvn.Client()
    rev = get_revision(req)
    svn_list = []
    try:
        for obj in svn.ls(svn_url, revision=rev):
            svn_file = {'filename':obj.data['name'].replace(SVN_URL, '')[1:], 'display_name':obj.data['name'].split('/')[-1], 'filesize':obj.data['size']}
            if obj.data['kind'] == node_kind.dir:
                svn_file['is_dir'] = True
            svn_list.append(svn_file)
    except ClientError:
        raise Http404
    return render(req,"svnclient/svn-ls.html",{'filename':filename,'rev':rev.number,'svn_list':svn_list})

@admin_required
def svn_cat(req, filename):
    svn = pysvn.Client()
    rev = get_revision(req)
    formatter = None
    if filename.split('.')[-1] == 'py':
        formatter = 'python'
    elif filename.split('.')[-1] == 'html':
        formatter = 'html+django'
    elif filename.split('.')[-1] == 'js':
        formatter = 'js+django'
    elif filename.split('.')[-1] == 'txt':
        formatter = 'django'
    elif filename.split('.')[-1] == 'css':
        formatter = 'css+django'
    elif filename.split('.')[-1] == 'json':
        formatter = 'json'
    elif filename.split('.')[-1] == 'png':
        return HttpResponse(svn.cat('%s/%s' % (SVN_URL, filename), revision=rev), mimetype="image/png")
    elif filename.split('.')[-1] == 'jpg':
        return HttpResponse(svn.cat('%s/%s' % (SVN_URL, filename), revision=rev), mimetype="image/jpeg")
    elif filename.split('.')[-1] == 'gif':
        return HttpResponse(svn.cat('%s/%s' % (SVN_URL, filename), revision=rev), mimetype="image/gif")
    context = {'filename':filename,'rev':rev.number,'formatter':formatter,'svn_data':svn.cat('%s/%s' % (SVN_URL, filename), revision=rev)}
    return render(req, "svnclient/svn-cat.html",context)

@admin_required
def svn_text(req, filename):
    svn = pysvn.Client()
    rev = get_revision(req)
    return HttpResponse(svn.cat('%s/%s' % (SVN_URL, filename), revision=rev), mimetype="text/plain")

@admin_required
def svn_log(req, filename):
    svn_url = SVN_URL
    if filename:
        svn_url += '/%s' % filename
    svn = pysvn.Client()
    rev = get_revision(req)
    log = ""
    for entry in svn.log(svn_url, revision_start=rev, peg_revision=rev):
        log += "%s (%d)\n\n" % (filename,int(entry['revision'].number))
        log += "  * %s\n\n" % str(entry['message'])
        revdate = datetime.datetime.fromtimestamp(entry['date']).strftime("%a, %d %b %Y %H:%M:%S %z")
        log += " -- %s <%s@node1>  %s\n\n" % (str(entry['author']),str(entry['author']),str(revdate))
    context = {'title':filename,'svn_data':log}
    return render(req,"svnclient/svn-log.html",context)

@admin_required
def svn_diff(req, filename):
    svn = pysvn.Client()
    rev = get_revision(req)
    if rev.kind == opt_revision_kind.head:
        try:
            rev = svn.log('%s/%s' % (SVN_URL, filename))[1]['revision']
        except:
            pass
    data = svn.diff('/tmp','%s/%s' % (SVN_URL, filename), revision1=rev, revision2=Revision(opt_revision_kind.head))
    context = {'filename':filename,'rev':rev.number,'formatter':'diff','svn_data':data}
    return render(req, "svnclient/svn-cat.html",context)

@admin_required
def svn_history(req, filename):
    svn = pysvn.Client()
    rev = get_revision(req)
    history_list = []
    for entry in svn.log('%s/%s' % (SVN_URL, filename), revision_start=rev, peg_revision=rev):
        history_list.append({'revision':int(entry['revision'].number),
                             'message':str(entry['message']),
                             'date':datetime.datetime.fromtimestamp(entry['date']).strftime("%a, %d %b %Y %H:%M:%S %z"),
                             'author':str(entry['author'])})
    context = {'filename':filename,'history_list':history_list}
    return render(req, "svnclient/svn-history.html", context)
