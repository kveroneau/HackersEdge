from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http.response import HttpResponse
from help_center.models import Topic, Guide
from html2text import html2text

dispatcher = SimpleXMLRPCDispatcher()

class GuideService:
    def topics(self):
        topic_list = []
        for topic in Topic.objects.all():
            topic_list.append({'slug':topic.slug, 'title':topic.title, 'description':topic.description})
        return topic_list
    def guides(self, topic):
        try:
            topic = Topic.objects.get(slug=topic)
        except:
            return []
        guide_list = []
        for guide in topic.guide_set.all():
            guide_list.append({'slug':guide.slug, 'title':guide.title, 'created_on':'%s' % guide.created_on, 'updated_on':'%s' % guide.modified_on})
        return guide_list
    def guide(self, guide):
        try:
            guide = Guide.objects.get(slug=guide)
        except:
            return 'Guide not found!'
        return html2text(guide.content.replace('/s/', 'http://www.hackers-edge.com/s/'))

dispatcher.register_instance(GuideService())

@csrf_exempt
@require_POST
def rpc_service(req):
    response = HttpResponse(mimetype='application/xml')
    response.write(dispatcher._marshaled_dispatch(req.body))
    response['Content-length'] = str(len(response.content))
    return response
