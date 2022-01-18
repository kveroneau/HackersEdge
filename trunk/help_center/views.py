from help_center.models import Topic, Guide
from django.shortcuts import get_object_or_404, render
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

class TopicList(ListView):
    model = Topic
    def get_queryset(self):
        return super(TopicList, self).get_queryset().filter(is_active=True)

class GuideList(ListView):
    model = Guide
    def get_queryset(self):
        return super(GuideList, self).get_queryset().filter(topic__slug=self.kwargs['slug'], draft=False)
    def get_context_data(self, **kwargs):
        ctx = super(GuideList, self).get_context_data(**kwargs)
        topic = get_object_or_404(Topic, slug=self.kwargs['slug'])
        ctx.update({'topic':topic.title})
        return ctx

class GuideById(DetailView):
    model = Guide
    def get_queryset(self):
        return super(GuideById, self).get_queryset().filter(draft=False)

def view_guide(req, slug1, slug2):
    topic = get_object_or_404(Topic, slug=slug1)
    if req.user.is_staff:
        guide = get_object_or_404(Guide, topic=topic, slug=slug2)
    else:
        guide = get_object_or_404(Guide, topic=topic, slug=slug2, draft=False)
    return render(req, "help_center/guide_detail.html", {'object': guide})
