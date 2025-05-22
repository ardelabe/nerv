# nerv/magi/melchior/management/commands/import_documents.py

import os
import csv
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from melchior.models import Documento
from bs4 import BeautifulSoup
import re
from django.core.files import File
import unicodedata

class Command(BaseCommand):
    help = 'Importa documentos HTML e seus metadados de um arquivo CSV.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file_path', type=str, help='Caminho para o arquivo CSV de metadados.')
        parser.add_argument('documents_dir', type=str, help='Caminho para o diretório raiz contendo os arquivos de documentos (e.g., a pasta que contém "htmls/").')
        parser.add_argument('--error-log', type=str, help='Caminho para o arquivo de log de erros de importação.', default='import_errors.log') # Novo argumento

    def handle(self, *args, **options):
        csv_file_path = options['csv_file_path']
        documents_dir = options['documents_dir']
        error_log_path = options['error_log'] # Captura o caminho do log

        # Lista para armazenar os erros durante a execução
        import_errors = []

        if not os.path.exists(csv_file_path):
            raise CommandError(f'O arquivo CSV não foi encontrado: {csv_file_path}')
        if not os.path.isdir(documents_dir):
            raise CommandError(f'O diretório de documentos não foi encontrado: {documents_dir}')

        self.stdout.write(self.style.SUCCESS(f'Iniciando importação de documentos de {csv_file_path}'))

        HIERARCHY_MAP = {
            'LE': 'LEI_MUNICIPAL',
            'DL': 'DECRETO_MUNICIPAL',
            'RE': 'RESOLUCAO',
        }

        try:
            with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                reader.fieldnames = [f for f in reader.fieldnames if f is not None and f.strip() != '']
                
                required_csv_columns = ['arquivo', 'data_publicacao', 'lei_cod', 'revogada']
                if not all(col in reader.fieldnames for col in required_csv_columns):
                    missing = [col for col in required_csv_columns if col not in reader.fieldnames]
                    raise CommandError(f"Erro: As seguintes colunas obrigatórias não foram encontradas no CSV: {', '.join(missing)}. Verifique o arquivo CSV.")

                for row in reader:
                    file_relative_path = row.get('arquivo')
                    data_publicacao_str = row.get('data_publicacao')
                    lei_cod_full = row.get('lei_cod', '')
                    revogada_status_str = row.get('revogada', '').strip().lower()

                    if not file_relative_path:
                        msg = 'Linha ignorada: "arquivo" ausente no CSV.'
                        self.stdout.write(self.style.WARNING(msg))
                        import_errors.append(f'{datetime.now().isoformat()} - WARNING: {msg} - Row: {row}')
                        continue

                    file_path_after_htmls = re.sub(r'^/?htmls/', '', file_relative_path)
                    full_file_path = os.path.join(documents_dir, file_path_after_htmls)

                    if not os.path.exists(full_file_path):
                        msg = f'Arquivo não encontrado, ignorando: {full_file_path}'
                        self.stdout.write(self.style.WARNING(msg))
                        import_errors.append(f'{datetime.now().isoformat()} - WARNING: {msg} - CSV Row: {row}')
                        continue

                    file_extension = os.path.splitext(file_relative_path)[1].lower()
                    doc_type = 'HTML' if file_extension == '.html' else 'OUTRO'

                    hierarquia_model = 'NAO_APLICAVEL'
                    if lei_cod_full:
                        prefix_match = re.match(r'([A-Z]+)', lei_cod_full)
                        if prefix_match:
                            hierarquia_model = HIERARCHY_MAP.get(prefix_match.group(1).upper(), 'NAO_APLICAVEL')
                    
                    status_documento = 'PENDENTE_ANALISE'
                    if revogada_status_str == 'sim' or revogada_status_str == 'true' or revogada_status_str == '1':
                        status_documento = 'REVOGADO'
                    elif revogada_status_str == 'não' or revogada_status_str == 'false' or revogada_status_str == '0':
                         status_documento = 'VIGENTE'

                    data_publicacao = None
                    if data_publicacao_str and data_publicacao_str.upper() != 'NULL' and data_publicacao_str.lower() != 'não data de publicação':
                        try:
                            data_publicacao = datetime.strptime(data_publicacao_str, '%Y-%m-%d').date()
                        except ValueError:
                            msg = f'Formato de data inválido para {file_relative_path}: "{data_publicacao_str}". Ignorando data_publicacao.'
                            self.stdout.write(self.style.WARNING(msg))
                            import_errors.append(f'{datetime.now().isoformat()} - WARNING: {msg} - CSV Row: {row}')

                    text = ""
                    try:
                        if doc_type == 'HTML':
                            with open(full_file_path, 'r', encoding='utf-8', errors='replace') as f:
                                html_content = f.read()
                            soup = BeautifulSoup(html_content, 'html.parser')
                            for script in soup(["script", "style"]):
                                script.extract()
                            text = soup.get_text()
                            text = re.sub(r'\s+', ' ', text).strip()
                            text = unicodedata.normalize('NFKC', text)
                        elif doc_type == 'PDF':
                            msg = f'Processamento de PDF não implementado para {file_relative_path}. Ignorando extração de texto.'
                            self.stdout.write(self.style.WARNING(msg))
                            import_errors.append(f'{datetime.now().isoformat()} - WARNING: {msg} - CSV Row: {row}')
                            text = ""

                    except Exception as e:
                        msg = f'Erro ao extrair texto de {file_relative_path}: {e}'
                        self.stdout.write(self.style.ERROR(msg))
                        import_errors.append(f'{datetime.now().isoformat()} - ERROR: {msg} - CSV Row: {row}')
                        continue

                    try:
                        documento, created = Documento.objects.get_or_create(
                            nome_arquivo=file_relative_path,
                            defaults={
                                'tipo_documento': doc_type,
                                'data_publicacao': data_publicacao,
                                'hierarquia': hierarquia_model,
                                'status': status_documento,
                                'texto_completo_extraido': text
                            }
                        )

                        if created:
                            with open(full_file_path, 'rb') as doc_data:
                                django_file = File(doc_data, name=os.path.basename(file_relative_path))
                                documento.arquivo.save(django_file.name, django_file, save=True)
                            self.stdout.write(self.style.SUCCESS(f'Documento "{file_relative_path}" importado com sucesso.'))
                        else:
                            documento.tipo_documento = doc_type
                            documento.data_publicacao = data_publicacao
                            documento.hierarquia = hierarquia_model
                            documento.status = status_documento
                            documento.texto_completo_extraido = text
                            documento.save()
                            self.stdout.write(self.style.NOTICE(f'Documento "{file_relative_path}" atualizado.'))

                    except Exception as e:
                        msg = f'Erro ao salvar/atualizar documento {file_relative_path} no banco de dados: {e}'
                        self.stdout.write(self.style.ERROR(msg))
                        import_errors.append(f'{datetime.now().isoformat()} - ERROR: {msg} - CSV Row: {row}')

        except FileNotFoundError:
            raise CommandError(f'Erro: O arquivo CSV não foi encontrado em {csv_file_path}')
        except Exception as e:
            raise CommandError(f'Ocorreu um erro inesperado: {e}')
        finally:
            # Garante que o log seja salvo mesmo se ocorrer um erro geral
            if import_errors:
                with open(error_log_path, 'w', encoding='utf-8') as f:
                    for error_msg in import_errors:
                        f.write(error_msg + '\n')
                self.stdout.write(self.style.WARNING(f'Foram encontrados erros/avisos durante a importação. Veja o log em: {error_log_path}'))

        self.stdout.write(self.style.SUCCESS('Importação de documentos concluída.'))