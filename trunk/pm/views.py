from django.views.generic.base import TemplateView
from django.core.exceptions import PermissionDenied
from django.views.generic.list import ListView
from pm.models import TodoItem
from django.views.generic.edit import CreateView
from pm.forms import TodoForm, GuideForm
from django.shortcuts import redirect, get_object_or_404
from django.views.generic.detail import DetailView
from django.contrib.auth.decorators import permission_required
from help_center.models import Guide
from django.utils.text import slugify
from django.contrib import messages

class SnippetViewer(TemplateView):
    template_name = 'pm/snippets.html'
    def dispatch(self, req, *args, **kwargs):
        if not req.user.has_perm('pm.change_snippet'):
            raise PermissionDenied
        return super(SnippetViewer, self).dispatch(req, *args, **kwargs)

class TodoMixin(object):
    def dispatch(self, req, *args, **kwargs):
        if not req.user.has_perm('pm.change_todoitem'):
            raise PermissionDenied
        return super(TodoMixin, self).dispatch(req, *args, **kwargs)

class TodoList(TodoMixin, ListView):
    model = TodoItem
    template_name = 'pm/todo_list.html'
    def get_queryset(self):
        if self.request.user.is_staff:
            return super(TodoList, self).get_queryset().filter(completed=False)
        else:
            return super(TodoList, self).get_queryset().filter(completed=False, staff_only=False)

class AddTodo(TodoMixin, CreateView):
    model = TodoItem
    form_class = TodoForm
    template_name = 'pm/todo_form.html'
    def form_valid(self, form):
        todo = form.save(commit=False)
        todo.added_by = self.request.user
        todo.save()
        return redirect('pmtodo-list')

class TodoDetail(TodoMixin, DetailView):
    model = TodoItem
    template_name = 'pm/todo_detail.html'

class AddGuide(CreateView):
    model = Guide
    form_class = GuideForm
    template_name = 'pm/guide_form.html'
    def dispatch(self, req, *args, **kwargs):
        if not req.user.has_perm('help_center.add_guide'):
            raise PermissionDenied
        return super(AddGuide, self).dispatch(req, *args, **kwargs)
    def form_valid(self, form):
        guide = form.save(commit=False)
        guide.slug = slugify(guide.title)
        guide.draft = True
        guide.save()
        messages.success(self.request, 'Your guide has been submitted for review.')
        return redirect('pmtodo-list')

@permission_required('pm.change_todoitem')
def mark_complete(req, pk):
    todo = get_object_or_404(TodoItem, pk=pk)
    todo.completed = True
    todo.save()
    return redirect('pmtodo-list')
