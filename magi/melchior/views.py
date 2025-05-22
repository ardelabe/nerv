# nerv/magi/melchior/views.py

import os
import google.generativeai as genai
import chromadb
from chromadb.utils import embedding_functions
from django.shortcuts import render
from django.conf import settings
from .models import Chunk 

# --- Configuração da API do Google AI Studio ---
API_KEY = os.getenv('GOOGLE_API_KEY')

if not API_KEY:
    raise Exception("Erro: A chave da API do Google AI Studio (GOOGLE_API_KEY) não foi encontrada nas variáveis de ambiente. "
                    "Certifique-se de que seu arquivo .env está configurado corretamente e é carregado no settings.py.")

genai.configure(api_key=API_KEY)

# --- Configuração do ChromaDB ---
CHROMA_DB_PATH = os.path.join(settings.BASE_DIR, 'chroma_db')
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

COLLECTION_NAME = "melchior_chunks"
gemini_embedding_function = embedding_functions.GoogleGenerativeAiEmbeddingFunction(api_key=API_KEY, model_name="embedding-001")

try:
    collection = client.get_collection(name=COLLECTION_NAME, embedding_function=gemini_embedding_function)
except Exception as e:
    raise Exception(f"Erro: Coleção ChromaDB '{COLLECTION_NAME}' não encontrada ou erro na inicialização. "
                    f"Certifique-se de que 'generate_embeddings' foi executado com sucesso e o caminho do ChromaDB ({CHROMA_DB_PATH}) está correto. Erro: {e}")


def melchior_search_view(request):
    query = request.GET.get('q', '').strip()
    results = []
    generated_answer = ""
    error_message = ""

    if query:
        try:
            query_embedding_response = genai.embed_content(
                model="models/embedding-001",
                content=query,
                task_type="RETRIEVAL_QUERY"
            )
            query_embedding = query_embedding_response['embedding']

            chroma_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=7,
            )
            
            relevant_chunk_ids = []
            if chroma_results and chroma_results['ids'] and chroma_results['ids'][0]:
                for result_id in chroma_results['ids'][0]:
                    django_chunk_id = int(result_id.split('_')[1])
                    relevant_chunk_ids.append(django_chunk_id)

            relevant_chunks_from_db = Chunk.objects.filter(id__in=relevant_chunk_ids, is_valido_apos_antinomia=True) \
                                                    .order_by('documento__data_publicacao', 'ordem_no_documento')
            
            context_chunks_for_llm = []
            ordered_chunks_map = {chunk.id: chunk for chunk in relevant_chunks_from_db}

            for result_id in chroma_results['ids'][0]:
                django_chunk_id = int(result_id.split('_')[1])
                if django_chunk_id in ordered_chunks_map:
                    chunk_obj = ordered_chunks_map[django_chunk_id]
                    context_chunks_for_llm.append(
                        f"Documento: {chunk_obj.documento.nome_arquivo}\n"
                        f"Artigo/Trecho: {chunk_obj.conteudo_tratado}\n"
                        f"---"
                    )
                    results.append({
                        'ordem_no_documento': chunk_obj.ordem_no_documento,
                        'documento_nome': chunk_obj.documento.nome_arquivo,
                        'conteudo_tratado': chunk_obj.conteudo_tratado,
                        'documento_data_publicacao': chunk_obj.documento.data_publicacao,
                        'documento_hierarquia': chunk_obj.documento.hierarquia,
                    })
            
            if context_chunks_for_llm:
                context_str = "\n".join(context_chunks_for_llm)
                
                # --- PROMPT REFINADO AQUI ---
                final_prompt = (
                    f"Você é um assistente especializado em legislação do Brasil. "
                    f"Sua tarefa é responder à 'Pergunta' de forma **direta e concisa**, "
                    f"utilizando **APENAS** as 'Fontes' fornecidas. "
                    f"Não invente informações. Se a resposta não estiver explicitamente nas fontes, "
                    f"diga 'Não consigo responder com as informações fornecidas.' "
                    f"Sua resposta deve ser um parágrafo claro e curto, sem iniciar com 'Com base nas fontes...' ou similar. "
                    f"Após sua resposta direta, **obrigatóriamente** inclua uma seção 'Fontes Relevantes:' "
                    f"listando cada fonte utilizada com a anotação: "
                    f"'Fonte: Documento: [Nome do Documento], Artigo/Trecho: [Primeiras ~50 palavras do trecho relevante]'. "
                    f"Priorize informações de leis mais recentes e de hierarquia superior se houver informações conflitantes nas fontes.\n\n"
                    f"Fontes:\n{context_str}\n\n"
                    f"Pergunta: {query}"
                )
                # --- FIM DO PROMPT REFINADO ---
                
                model = genai.GenerativeModel('gemini-1.5-flash') 
                
                response = model.generate_content(final_prompt)
                generated_answer = response.text
                
                generated_answer = generated_answer.strip()

            else:
                generated_answer = "Não foram encontrados documentos relevantes para a sua pergunta no momento."

        except Exception as e:
            error_message = f"Ocorreu um erro ao processar sua solicitação: {e}. Por favor, tente novamente."
            print(f"ERRO: Erro na melchior_search_view: {e}")

    context = {
        'query': query,
        'results': results,
        'generated_answer': generated_answer,
        'error_message': error_message,
    }
    return render(request, 'melchior/search.html', context)