# nerv/magi/melchior/management/commands/resolve_antinomias.py

import os
from django.core.management.base import BaseCommand, CommandError
from melchior.models import Documento, Chunk
import re
from datetime import date # Para comparar datas

class Command(BaseCommand):
    help = 'Resolve antinomias em chunks de documentos legais, marcando a validade.'

    # Mapeamento de hierarquia para valores numéricos (quanto maior, mais hierárquico)
    HIERARCHY_RANK = {
        'CONSTITUICAO': 5,
        'LEI_FEDERAL': 3,
        'DECRETO_FEDERAL': 2.5,
        'LEI_ESTADUAL': 3,
        'DECRETO_ESTADUAL': 2.5,
        'LEI_MUNICIPAL': 3,
        'RESOLUCAO': 3, # Pouco abaixo da lei municipal
        'DECRETO_MUNICIPAL': 2.5,
        'PORTARIA': 1,
        'NORMA_TECNICA': 0.5,
        'OUTRO': 0,
        'NAO_APLICAVEL': -1,
    }

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando a resolução de antinomias...'))

        documentos = Documento.objects.all()
        if not documentos.exists():
            self.stdout.write(self.style.WARNING('Nenhum documento encontrado para resolver antinomias.'))
            return

        # Listas para armazenar as regras aplicadas e chunks modificados
        resolved_antinomies_log = []
        
        # --- Passo 1: Marcar chunks com base no status do Documento principal ---
        # Se o Documento.status for 'REVOGADO', todos os seus chunks são inválidos.
        # Se for 'VIGENTE', a princípio, seus chunks são válidos.
        # 'PARCIALMENTE_REVOGADO' e 'PENDENTE_ANALISE' exigem análise mais profunda.
        self.stdout.write(self.style.NOTICE('Aplicando regras baseadas no status do Documento...'))
        for doc in documentos:
            if doc.status == 'REVOGADO':
                chunks_to_update = doc.chunks.filter(is_valido_apos_antinomia=True)
                count = chunks_to_update.update(is_valido_apos_antinomia=False)
                if count > 0:
                    self.stdout.write(self.style.WARNING(f'Marcado {count} chunks de "{doc.nome_arquivo}" como inválidos (Documento Revogado).'))
                    resolved_antinomies_log.append(f'Documento {doc.nome_arquivo} (Status: REVOGADO) -> {count} chunks marcados como inválidos.')
            elif doc.status == 'VIGENTE':
                chunks_to_update = doc.chunks.filter(is_valido_apos_antinomia=False)
                count = chunks_to_update.update(is_valido_apos_antinomia=True)
                if count > 0:
                    self.stdout.write(self.style.NOTICE(f'Marcado {count} chunks de "{doc.nome_arquivo}" como válidos (Documento Vigente).'))
                    resolved_antinomies_log.append(f'Documento {doc.nome_arquivo} (Status: VIGENTE) -> {count} chunks marcados como válidos.')
            
            # Reset conteudo_tratado para conteudo_original para garantir uma base limpa antes de aplicar as regras
            # Futuramente, o conteudo_tratado poderá ser alterado para incluir notas de revogação.
            # doc.chunks.all().update(conteudo_tratado=models.F('conteudo_original')) # Não funciona diretamente para textfield
            # Melhor iterar ou fazer um update mais inteligente se for mudar o texto.
            # Por agora, vamos manter conteudo_tratado = conteudo_original, e apenas mudar is_valido_apos_antinomia

        # --- Passo 2: Identificação de Revogações Explícitas no Conteúdo do Chunk ---
        # Padrões para buscar por revogações explícitas dentro do texto do chunk
        # Exemplos: "revoga o art. X", "fica revogado o inciso Y", "revogadas as disposições em contrário"
        # Isso é uma simplificação. Identificar qual lei ou artigo é revogado é mais complexo.
        # Por enquanto, se um chunk *menciona* uma revogação genérica, ele não invalida outros,
        # mas se um chunk *se declara* revogado (ex: "Art. X. (Revogado)"), ele é invalidado.
        
        self.stdout.write(self.style.NOTICE('Buscando por termos de revogação explícita nos chunks...'))
        
        # Regex para identificar se o próprio chunk se declara revogado
        # Ex: "Art. 5º (Revogado pela Lei XYZ)" ou "Parágrafo único. (Revogado)"
        self_revoked_pattern = re.compile(
            r'\b(?:revogado|revogada|revogados|revogadas)\b' # palavras "revogado"
            r'[\s\S]*?(?:\(.*?revogad[ao]s?.*?\))?' # opcionalmente, entre parênteses
            , re.IGNORECASE | re.DOTALL
        )

        # Regex para identificar texto tachado (ex: [texto tachado]) - **Extremamente difícil de capturar em texto puro extraído de HTML sem a formatação.**
        # A detecção de texto tachado geralmente requer análise do HTML/PDF original (tags <del>, estilos CSS).
        # Para texto puro, é quase impossível sem um padrão de marcador específico.
        # Por exemplo, se o texto tachado sempre for exportado como [TACHADO: Conteúdo], poderíamos usar.
        # Sem isso, vamos ignorar a detecção de "tachado" por agora no nível do texto puro.

        chunks_count = Chunk.objects.filter(is_valido_apos_antinomia=True).count()
        self.stdout.write(self.style.NOTICE(f'Analisando {chunks_count} chunks válidos para revogações explícitas...'))

        for chunk in Chunk.objects.filter(is_valido_apos_antinomia=True):
            # Se o texto do chunk se declara revogado
            if self_revoked_pattern.search(chunk.conteudo_original):
                chunk.is_valido_apos_antinomia = False
                chunk.save()
                msg = f'Chunk {chunk.id} de "{chunk.documento.nome_arquivo}" marcado como inválido (contém termo de auto-revogação).'
                self.stdout.write(self.style.WARNING(msg))
                resolved_antinomies_log.append(msg)
            # else:
            #     # Poderíamos aqui implementar lógica para identificar revogação de *outros* chunks
            #     # Ex: "Esta Lei revoga o Art. 5º da Lei Y". Isso exigiria:
            #     # 1. Extração do número do artigo e da lei revogada.
            #     # 2. Busca no DB por essa Lei Y e seu Art. 5º.
            #     # 3. Marcar o Art. 5º da Lei Y como is_valido_apos_antinomia = False.
            #     # Isso é bem mais complexo e podemos deixar para uma versão futura.


        # --- Passo 3: Aplicação de Regras de Prevalência (Hierárquica e Cronológica) ---
        # Esta é a parte mais complexa e que exige identificação de CONFLITOS de CONTEÚDO.
        # Para um protótipo, não é viável fazer isso sem um sistema de PNL que:
        # a) Identifique o "assunto" de cada chunk.
        # b) Compare chunks de diferentes documentos que tratam do MESMO assunto.
        # c) A partir dessa comparação, aplique a hierarquia e cronologia para ver qual prevalece.

        # POR ENQUANTO, vamos apenas usar o status inicial do documento e a auto-revogação.
        # A resolução de antinomias por hierarquia/cronologia será acionada quando o usuário fizer uma pergunta
        # e o sistema recuperar chunks conflitantes, ou em um pipeline de processamento posterior.
        
        self.stdout.write(self.style.NOTICE('Finalizando análise básica de antinomias. Regras de hierarquia/cronologia exigem PNL mais avançada.'))


        self.stdout.write(self.style.SUCCESS('Resolução de antinomias concluída.'))
        
        if resolved_antinomies_log:
            self.stdout.write(self.style.SUCCESS('\nResumo das Antinomias Resolvidas/Marcadas:'))
            for entry in resolved_antinomies_log:
                self.stdout.write(self.style.SUCCESS(f'- {entry}'))
        else:
            self.stdout.write(self.style.SUCCESS('Nenhuma antinomia explícita encontrada ou marcada nesta execução.'))