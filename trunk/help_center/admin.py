from django.contrib import admin
from help_center.models import Topic, Guide

class PopulateSlug(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}

class TopicAdmin(PopulateSlug):
    list_display = ('title', 'is_active',)

class GuideAdmin(PopulateSlug):
    list_display = ('title', 'topic', 'modified_on', 'draft',)
    list_filter = ('topic', 'draft',)
    date_hierarchy = 'modified_on'

admin.site.register(Topic, TopicAdmin)
admin.site.register(Guide, GuideAdmin)
