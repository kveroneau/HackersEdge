from django.contrib import admin
from pm.models import Category, Snippet, TodoItem

class SnippetAdmin(admin.ModelAdmin):
    list_filter = ('category',)
    list_display = ('title', 'category', 'added_on', 'edited_on',)

admin.site.register(Category)
admin.site.register(Snippet, SnippetAdmin)
admin.site.register(TodoItem)
