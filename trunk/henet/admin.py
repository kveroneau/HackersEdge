from django.contrib import admin
from henet.models import HostTemplate, HostFile, MailMessage, MachineConnector,\
    MachineType

class HostTemplateAdmin(admin.ModelAdmin):
    pass

class HostFileAdmin(admin.ModelAdmin):
    pass

class MailMessageAdmin(admin.ModelAdmin):
    pass

class MachineConnectorAdmin(admin.ModelAdmin):
    pass

class MachineTypeAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'template', 'is_active',)
    list_filter = ('is_active',)

admin.site.register(HostTemplate, HostTemplateAdmin)
admin.site.register(HostFile, HostFileAdmin)
admin.site.register(MailMessage, MailMessageAdmin)
admin.site.register(MachineConnector, MachineConnectorAdmin)
admin.site.register(MachineType, MachineTypeAdmin)
