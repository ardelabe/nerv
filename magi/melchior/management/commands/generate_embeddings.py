# nerv/magi/melchior/management/commands/generate_embeddings.py

import os
from django.core.management.base import BaseCommand, CommandError
from melchior.models import Chunk, Documento
import google.generativeai as genai
import chromadb
from chromadb.utils import embedding_functions
from django.conf import settings
import time # Importar para usar time.sleep

# --- Configuração da API do Google AI Studio ---
API_KEY = os.getenv('GOOGLE_API_KEY')

if not API_KEY:
    raise CommandError("Erro: A chave da API do Google AI Studio (GOOGLE_API_KEY) não foi encontrada nas variáveis de ambiente. "
                       "Certifique-se de que seu arquivo .env está configurado corretamente e é carregado no settings.py.")

genai.configure(api_key=API_KEY)

# --- Configuração do ChromaDB ---
CHROMA_DB_PATH = os.path.join(settings.BASE_DIR, 'chroma_db')
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

COLLECTION_NAME = "melchior_chunks"
gemini_embedding_function = embedding_functions.GoogleGenerativeAiEmbeddingFunction(api_key=API_KEY, model_name="embedding-001")

class Command(BaseCommand):
    help = 'Gera e armazena embeddings para chunks válidos usando o Google AI Studio e ChromaDB.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando a geração e armazenamento de embeddings...'))

        try:
            client.delete_collection(name=COLLECTION_NAME)
            self.stdout.write(self.style.NOTICE(f'Coleção "{COLLECTION_NAME}" do ChromaDB deletada para recomeço limpo.'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Não foi possível deletar a coleção "{COLLECTION_NAME}" do ChromaDB (provavelmente não existia ou outro erro). Erro: {e}'))
        
        try:
            collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=gemini_embedding_function)
        except Exception as e:
            raise CommandError(f"Erro fatal ao inicializar/criar ChromaDB collection: {e}. Verifique sua chave API, conexão ou se há conflito na função de embedding.")


        valid_chunks = Chunk.objects.filter(is_valido_apos_antinomia=True).iterator()
        
        chunks_processed = 0
        chunks_skipped = 0
        
        documents_batch = []
        metadatas_batch = []
        ids_batch = []
        # Reduzindo o tamanho do lote para evitar timeouts
        # Tente 100, 50 ou até 20 se o problema persistir.
        BATCH_SIZE = 100 
        MAX_RETRIES = 3 # Número máximo de tentativas para cada batch
        RETRY_DELAY = 10 # Atraso em segundos antes de re-tentar

        for chunk in valid_chunks:
            if not chunk.conteudo_tratado:
                self.stdout.write(self.style.WARNING(f'Chunk {chunk.id} não possui conteúdo tratado. Ignorando embedding.'))
                chunks_skipped += 1
                continue

            chroma_id = f"chunk_{chunk.id}"
            documents_batch.append(chunk.conteudo_tratado)
            
            metadatas_batch.append({
                "chunk_id": chunk.id,
                "documento_nome": chunk.documento.nome_arquivo if chunk.documento.nome_arquivo is not None else "",
                "documento_id": chunk.documento.id,
                "documento_hierarquia": chunk.documento.hierarquia if chunk.documento.hierarquia is not None else "NAO_APLICAVEL",
                "documento_data_publicacao": str(chunk.documento.data_publicacao) if chunk.documento.data_publicacao is not None else "",
                "ordem_no_documento": chunk.ordem_no_documento,
            })
            ids_batch.append(chroma_id)

            if len(documents_batch) >= BATCH_SIZE:
                for attempt in range(MAX_RETRIES):
                    try:
                        collection.add(
                            documents=documents_batch,
                            metadatas=metadatas_batch,
                            ids=ids_batch
                        )
                        chunks_processed += len(documents_batch)
                        self.stdout.write(self.style.NOTICE(f'Processados {chunks_processed} chunks...'))
                        break # Sai do loop de retries se for bem-sucedido
                    except Exception as e:
                        if "504 Deadline Exceeded" in str(e) or "timeout" in str(e).lower():
                            self.stdout.write(self.style.WARNING(f'Erro de timeout no batch (tentativa {attempt + 1}/{MAX_RETRIES}): {e}'))
                            self.stdout.write(self.style.NOTICE(f'Aguardando {RETRY_DELAY} segundos antes de re-tentar...'))
                            time.sleep(RETRY_DELAY)
                        else:
                            # Outros erros, não tentar novamente
                            self.stdout.write(self.style.ERROR(f'Erro não-timeout ao adicionar batch de chunks ao ChromaDB: {e}'))
                            chunks_skipped += len(documents_batch)
                            break # Sai do loop de retries para outros erros
                else: # Este else é executado se o loop de retries não foi quebrado (ou seja, todas as tentativas falharam)
                    self.stdout.write(self.style.ERROR(f'Todas as {MAX_RETRIES} tentativas para o batch falharam. Ignorando este batch.'))
                    chunks_skipped += len(documents_batch)
                
                # Limpar os batches, mesmo que as tentativas falhem, para não acumular
                documents_batch = []
                metadatas_batch = []
                ids_batch = []
        
        # Processar qualquer chunk restante no último batch
        if documents_batch:
            for attempt in range(MAX_RETRIES):
                try:
                    collection.add(
                        documents=documents_batch,
                        metadatas=metadatas_batch,
                        ids=ids_batch
                    )
                    chunks_processed += len(documents_batch)
                    self.stdout.write(self.style.NOTICE(f'Processados os últimos {len(documents_batch)} chunks restantes.'))
                    break
                except Exception as e:
                    if "504 Deadline Exceeded" in str(e) or "timeout" in str(e).lower():
                        self.stdout.write(self.style.WARNING(f'Erro de timeout no último batch (tentativa {attempt + 1}/{MAX_RETRIES}): {e}'))
                        self.stdout.write(self.style.NOTICE(f'Aguardando {RETRY_DELAY} segundos antes de re-tentar...'))
                        time.sleep(RETRY_DELAY)
                    else:
                        self.stdout.write(self.style.ERROR(f'Erro não-timeout ao adicionar último batch de chunks ao ChromaDB: {e}'))
                        chunks_skipped += len(documents_batch)
                        break
            else:
                self.stdout.write(self.style.ERROR(f'Todas as {MAX_RETRIES} tentativas para o último batch falharam. Ignorando este batch.'))
                chunks_skipped += len(documents_batch)


        self.stdout.write(self.style.SUCCESS(f'Geração e armazenamento de embeddings concluída.'))
        self.stdout.write(self.style.SUCCESS(f'Total de chunks processados e armazenados: {chunks_processed}'))
        self.stdout.write(self.style.WARNING(f'Total de chunks ignorados (sem conteúdo ou erro no processamento): {chunks_skipped}'))
        self.stdout.write(self.style.SUCCESS(f'Embeddings armazenados no ChromaDB em: {CHROMA_DB_PATH}'))