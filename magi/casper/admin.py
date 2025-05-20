from django.contrib import admin
from .models import InputData, PromptDefinition # Importe PromptDefinition

# Register your models here.

admin.site.register(InputData)
admin.site.register(PromptDefinition) # Registre o novo modelo