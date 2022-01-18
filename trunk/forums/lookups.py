from selectable.base import ModelLookup
from forums.models import Post
from selectable.registry import registry

class ForumLookup(ModelLookup):
    model = Post
    search_fields = ('subject__contains', 'body__contains', 'username__startswith',)
    def get_item_id(self, item):
        return item.pk

registry.register(ForumLookup)
