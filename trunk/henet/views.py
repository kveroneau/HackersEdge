from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http.response import HttpResponse, Http404
from django.core.exceptions import PermissionDenied
from henet.models import Host, HostTemplate, HostFile
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView
from henet.forms import HostTemplateForm, HostFileForm
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
import pickle
from django.contrib.auth.models import User

class HENetService:
    def set_host(self, ip_addr, data):
        try:
            host = Host.objects.get(ip_addr=ip_addr)
            host.data = data
            host.save(pickled=True)
        except Host.DoesNotExist:
            Host.objects.create(ip_addr=ip_addr, data=data)
        except:
            return 'ERR'
        return 'OK'
    def get_host(self, ip_addr):
        try:
            host = Host.objects.get(ip_addr=ip_addr)
        except Host.DoesNotExist:
            return 'ERR'
        return str(host.data)
    def get_vm(self, ip_addr):
        try:
            host = Host.objects.get(ip_addr=ip_addr)
        except Host.DoesNotExist:
            return 'ERR'
        return str(host.get_vm())
    def make_host(self, ip_addr, vm):
        try:
            Host.objects.get(ip_addr=ip_addr)
            return 'ERR'
        except Host.DoesNotExist:
            Host.objects.create(ip_addr=ip_addr, data=pickle.dumps({'online':False, 'vm':vm}))
            return 'OK'
    def get_template(self, slug):
        try:
            tmpl = HostTemplate.objects.get(slug=slug)
        except HostTemplate.DoesNotExist:
            return 'ERR'
        return tmpl.ini
    def get_file(self, filename):
        try:
            f = HostFile.objects.get(filename=filename)
        except HostFile.DoesNotExist:
            return 'ERR'
        if filename.endswith('.asm'):
            try:
                lines = f.content.split('\r\n')
                inc = []
                for l in range(0,len(lines)-1):
                    if lines[l].upper().startswith('.INC'):
                        inc.append(l)
                offset = 1
                for i in inc:
                    offset-=1
                    fname = lines[i+offset][5:]
                    if fname == filename:
                        return 'ERR'
                    inc_lines = self.get_file(fname).split('\r\n')
                    del lines[i+offset]
                    for line in inc_lines:
                        lines.insert(i+offset,line)
                        offset+=1
                return '\r\n'.join(lines)
            except:
                return 'ERR'
        return f.content
    def host_list(self):
        return [host.ip_addr for host in Host.objects.all()]
    def make_available(self, ip_addr):
        try:
            host = Host.objects.get(ip_addr=ip_addr)
        except Host.DoesNotExist:
            return 'ERR'
        host.available = True
        host.save()
        return 'OK'
    def set_designer(self, ip_addr, designer):
        try:
            host = Host.objects.get(ip_addr=ip_addr)
            u = User.objects.get(username=designer)
        except Host.DoesNotExist:
            return 'ERR'
        host.designer = u
        host.available = False
        host.save()
        return 'OK'
    def host_pool(self):
        return '|'.join([host.ip_addr for host in Host.objects.filter(available=True)])

henet_service = HENetService()

@csrf_exempt
@require_POST
def service(req):
    if req.META['REMOTE_ADDR'] not in ('127.0.0.1', '10.128.35.142',):
        raise PermissionDenied
    response = HttpResponse(mimetype='application/hackers-edge')
    if 'HTTP_X_HACKER_TOKEN' not in req.META.keys():
        raise PermissionDenied
    if req.META['HTTP_X_HACKER_TOKEN'] != settings.HACKER_TOKEN:
        raise PermissionDenied
    request = req.body.split(chr(0))
    handler = getattr(henet_service, request[0], None)
    if handler:
        data = request[0]+chr(0)+handler(*request[1:])
    else:
        data = 'ERR'
    response.write(str(data)+chr(255))
    return response

class DesignerMixin(object):
    def dispatch(self, req, *args, **kwargs):
        if not req.user.has_perm('henet.change_hosttemplate'):
            raise PermissionDenied
        return super(DesignerMixin, self).dispatch(req, *args, **kwargs)

class TemplateList(DesignerMixin, ListView):
    model = HostTemplate

class FileList(DesignerMixin, ListView):
    model = HostFile
    paginate_by = 20
    def get_queryset(self):
        qs = super(FileList, self).get_queryset()
        if self.request.GET.get('all','n') == 'y':
            return qs
        return qs.filter(created_by=self.request.user)
    def get_context_data(self, **kwargs):
        ctx = super(FileList, self).get_context_data(**kwargs)
        ctx.update({'all':self.request.GET.get('all','n')})
        return ctx

class CreateTemplate(DesignerMixin, CreateView):
    model = HostTemplate
    form_class = HostTemplateForm
    def form_valid(self, form):
        tmpl = form.save(commit=False)
        tmpl.created_by = self.request.user
        tmpl.save()
        messages.success(self.request, 'The template has been created.')
        return redirect('template-list')

class EditTemplate(DesignerMixin, UpdateView):
    model = HostTemplate
    form_class = HostTemplateForm
    def form_valid(self, form):
        if self.object.created_by != self.request.user:
            messages.error(self.request, 'You can only edit templates you have created.')
            return redirect('template-list')
        form.save()
        messages.success(self.request, 'The template has been saved.')
        return redirect('template-list')

class CreateFile(DesignerMixin, CreateView):
    model = HostFile
    form_class = HostFileForm
    def form_valid(self, form):
        f = form.save(commit=False)
        f.created_by = self.request.user
        f.save()
        messages.success(self.request, 'The file has been created.')
        return redirect('file-list')

class EditFile(DesignerMixin, UpdateView):
    model = HostFile
    form_class = HostFileForm
    def get_object(self):
        qs = self.get_queryset()
        filename = self.kwargs.get('filename', None)
        qs = qs.filter(filename=filename)
        try:
            f = qs.get()
        except HostFile.DoesNotExist:
            raise Http404
        return f
    def form_valid(self, form):
        if self.object.created_by != self.request.user:
            messages.error(self.request, 'You can only edit files you have created.')
            return redirect('file-list')
        form.save()
        messages.success(self.request, 'The file has been saved.')
        return redirect('file-list')

class HostList(ListView):
    model = Host
    paginate_by = 20
    def dispatch(self, req, *args, **kwargs):
        if not req.user.is_staff:
            raise PermissionDenied
        return super(HostList, self).dispatch(req, *args, **kwargs)
