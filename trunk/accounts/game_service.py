from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.http.response import HttpResponse
from xmlrpc import AccountService
import cPickle as pickle
from django.conf import settings

userdb = AccountService()

@csrf_exempt
@require_POST
def service(req):
    if req.META['REMOTE_ADDR'] not in ('127.0.0.1',):
        raise PermissionDenied
    response = HttpResponse(mimetype='application/hackers-edge')
    if 'HTTP_X_HACKER_TOKEN' not in req.META.keys():
        raise PermissionDenied
    if req.META['HTTP_X_HACKER_TOKEN'] != settings.HACKER_TOKEN:
        raise PermissionDenied
    request = req.body.split(chr(0))
    if request[0] == 'ping':
        data = 'pong'
    elif request[0] == 'user':
        udata = userdb.get_user(request[1])
        data = 'udata'+chr(0)+pickle.dumps(udata)
    elif request[0] == 'last_login':
        data = 'last_login'+chr(0)+pickle.dumps(userdb.get_last_login(request[1]))
    else:
        data = 'ERR'
    response.write(data+chr(255))
    return response
