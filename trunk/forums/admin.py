from django.contrib import admin
from forums.models import Topic, Post, Thread

class TopicAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'valid_group',)
    list_filter = ('valid_group',)

class ThreadAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'started_by', 'started_on', 'last_updated', 'topic', 'is_locked', 'valid_group',)
    list_filter = ('started_by', 'topic', 'is_locked', 'valid_group',)
    #date_hierarchy = 'last_updated'

class PostAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'user', 'posted', 'thread',)
    list_filter = ('user', 'thread',)
    #date_hierarchy = 'posted'

admin.site.register(Topic, TopicAdmin)
admin.site.register(Thread, ThreadAdmin)
admin.site.register(Post, PostAdmin)
