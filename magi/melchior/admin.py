# nerv/magi/melchior/admin.py

from django.contrib import admin
from .models import Documento, Chunk # Importe seus modelos

# Registrar o modelo Documento para que ele apareça no Django Admin
@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('nome_arquivo', 'tipo_documento', 'data_publicacao', 'hierarquia', 'status', 'data_upload')
    list_filter = ('tipo_documento', 'hierarquia', 'status', 'data_publicacao')
    search_fields = ('nome_arquivo', 'texto_completo_extraido')
    date_hierarchy = 'data_publicacao' # Permite navegar por data
    
    # Adicionar uma ação customizada para marcar como revogado (próximo passo)
    actions = ['mark_as_revoked']

    # Ação customizada para marcar documentos selecionados como revogados
    @admin.action(description='Marcar documentos selecionados como REVOGADOS')
    def mark_as_revoked(self, request, queryset):
        # Para cada documento selecionado, atualiza o status
        updated_count = queryset.update(status='REVOGADO')
        
        # Opcional: Acionar reprocessamento de chunks para atualizar is_valido_apos_antinomia
        # Isso pode ser custoso se muitos documentos forem selecionados.
        # Uma alternativa é ter um comando Django que você roda periodicamente
        # para revalidar todos os chunks.
        
        # Para simplificar no admin, vamos apenas atualizar o status do Documento.
        # O comando 'resolve_antinomias' que você roda (ou rodará periodicamente)
        # se encarregará de atualizar os chunks automaticamente quando rodar.

        self.message_user(request, f'{updated_count} documento(s) marcado(s) como REVOGADO(S) com sucesso.', level='success')

# Você também pode registrar o Chunk se quiser inspecioná-los no admin
# @admin.register(Chunk)
# class ChunkAdmin(admin.ModelAdmin):
#     list_display = ('documento', 'ordem_no_documento', 'is_valido_apos_antinomia', 'relevancia_antinomia')
#     list_filter = ('is_valido_apos_antinomia', 'documento__hierarquia', 'documento__status')
#     search_fields = ('conteudo_original', 'conteudo_tratado')
#     raw_id_fields = ('documento', 'revogado_por_chunk') # Para relacionamentos ForeignKey