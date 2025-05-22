# nerv/magi/melchior/management/commands/process_documents.py

import os
from django.core.management.base import BaseCommand, CommandError
from melchior.models import Documento, Chunk
import re
import unicodedata # Já deve estar importado

class Command(BaseCommand):
    help = 'Processa os documentos importados, divide-os em chunks e preenche o conteudo_original.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando o processamento de documentos para chunking...'))

        documentos = Documento.objects.all()
        if not documentos.exists():
            self.stdout.write(self.style.WARNING('Nenhum documento encontrado no banco de dados para processar.'))
            return

        for doc in documentos:
            self.stdout.write(self.style.NOTICE(f'Processando documento: {doc.nome_arquivo}'))
            
            if not doc.texto_completo_extraido:
                self.stdout.write(self.style.WARNING(f'Documento "{doc.nome_arquivo}" não possui texto extraído. Ignorando chunking.'))
                continue

            text = doc.texto_completo_extraido
            
            # Limpar chunks existentes para este documento antes de criar novos
            # Isso é útil se você rodar o comando várias vezes durante o desenvolvimento
            Chunk.objects.filter(documento=doc).delete()
            
            chunks = self._chunk_text_by_legal_articles(text)

            if not chunks: # Se a função de chunking não retornou nada, crie um único chunk
                if text.strip():
                    chunks.append(text.strip())
                    self.stdout.write(self.style.WARNING(f"Nenhum 'Art. Xº' encontrado para {doc.nome_arquivo}. Tratando o documento como um único chunk."))
                else:
                    self.stdout.write(self.style.WARNING(f"Documento '{doc.nome_arquivo}' não possui texto válido para chunking."))
                    continue # Pula para o próximo documento se o texto estiver vazio

            for i, chunk_content in enumerate(chunks):
                Chunk.objects.create(
                    documento=doc,
                    conteudo_original=chunk_content,
                    conteudo_tratado=chunk_content, # Por enquanto, tratado é igual ao original
                    ordem_no_documento=i,
                )
            self.stdout.write(self.style.SUCCESS(f'Criados {len(chunks)} chunks para "{doc.nome_arquivo}".'))
        
        self.stdout.write(self.style.SUCCESS('Processamento de documentos concluído.'))

    def _chunk_text_by_legal_articles(self, text):
        """
        Divide o texto de uma norma legal em chunks, usando "Art." como delimitador.
        Considera parágrafos únicos e incisos como parte do artigo.
        """
        chunks = []
        
        # Regex mais robusta:
        # - Captura "Art." ou "ART."
        # - Permite um ou mais espaços/quebras de linha (incluindo &nbsp; que vira espaço)
        # - Captura o número do artigo (pode ter ponto depois)
        # - Opcionalmente captura o símbolo de grau (º)
        # - (?:(?! ... ).)*? é o lookahead negativo para parar antes do próximo artigo
        # - Usamos re.DOTALL para '.' casar com nova linha
        # - Usamos re.IGNORECASE para "Art."
        article_pattern = re.compile(
            r'(Art\.\s*\d+[\ºo]?\s*(?:(?!\s*Art\.\s*\d+[\ºo]?\s*).)*)',
            re.DOTALL | re.IGNORECASE
        )

        matches = list(article_pattern.finditer(text))

        if matches:
            for match in matches:
                chunk_content = match.group(0).strip()
                if chunk_content:
                    chunks.append(chunk_content)
        
        # O bloco de fallback para único chunk se não houver matches é movido para handle()
        # para que o WARNING seja exibido de forma mais centralizada.

        return chunks