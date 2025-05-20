import os
import io
import google.generativeai as genai # Importe a biblioteca do Google AI Studio
from dotenv import load_dotenv # Importe para carregar variáveis de ambiente

from django.shortcuts import render, redirect
from .forms import InputDataForm
from .models import InputData, PROMPT_DEFINITIONS
from PyPDF2 import PdfReader
from docx import Document
from django.core.files.uploadedfile import InMemoryUploadedFile

# Carregar variáveis de ambiente do arquivo .env
load_dotenv() 

# Configure sua chave de API do Google AI Studio
# É crucial que sua chave de API esteja segura e não seja exposta publicamente.
# Recomendado: use variáveis de ambiente.
try:
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
except Exception as e:
    # Tratar caso a chave de API não seja encontrada
    print(f"Erro ao configurar a API do Google AI Studio: {e}")
    # Você pode querer adicionar um logger ou uma forma mais robusta de lidar com isso em produção.


def read_file(request): 
    """
    View to read files and text provided by the user.
    """
    if request.method == 'POST':
        form = InputDataForm(request.POST, request.FILES)
        if form.is_valid():
            input_data = form.save(commit=False) # Não salve ainda, precisamos do nome do arquivo
            
            file_content = ""
            if input_data.file:
                file_name = input_data.file.name
                input_data.file_name = file_name # Salva o nome do arquivo no modelo
                # Garante que o ponteiro do arquivo esteja no início
                input_data.file.seek(0) 
                
                if file_name.endswith('.pdf'):
                    pdf_reader = PdfReader(input_data.file)
                    for page in pdf_reader.pages:
                        file_content += page.extract_text() + "\n"
                elif file_name.endswith('.docx'):
                    doc = Document(input_data.file)
                    for paragraph in doc.paragraphs:
                        file_content += paragraph.text + "\n"
                elif file_name.endswith('.txt'):
                    file_content = input_data.file.read().decode('utf-8')
                elif file_name.endswith('.csv'):
                    import pandas as pd
                    try:
                        # Tenta ler como CSV
                        df = pd.read_csv(input_data.file)
                        file_content = df.to_string()
                    except Exception as e:
                        # Se falhar, tenta ler como texto simples
                        print(f"Erro ao ler CSV, tentando como texto: {e}")
                        input_data.file.seek(0) # Volta ao início do arquivo
                        file_content = input_data.file.read().decode('utf-8')

                
                input_data.text = file_content # Salva o conteúdo do arquivo no campo de texto
            
            input_data.save() # Agora sim, salve o objeto
            return redirect('casper:process_text', id=input_data.id)
    else:
        form = InputDataForm()
    return render(request, 'casper/read_file.html', {'form': form})

def process_text(request, id):
    """
    View to process the extracted text and display the content.
    """
    input_data = InputData.objects.get(pk=id)
    text = input_data.text
    prompt_type = input_data.get_prompt_type_display() # Pega o display do choice para melhor leitura
    file_name = input_data.file_name

    context = {
        'text': text,
        'prompt_type': prompt_type,
        'file_name': file_name,
        'input_data': input_data, # Passe o objeto input_data completo
    }
    return render(request, 'casper/display_text.html', context)


def send_to_ai_studio(request):
    """
    View to send the processed text and prompt to Google AI Studio.
    """
    if request.method == 'POST':
        input_data_id = request.POST.get('input_data_id')
        
        try:
            input_data = InputData.objects.get(pk=input_data_id)
        except InputData.DoesNotExist:
            return render(request, 'casper/ai_studio_result.html', {'error_message': 'Dados de entrada não encontrados.'})

        # Recupera o conteúdo do texto (do input do usuário ou do arquivo processado)
        content_to_send = input_data.text

        # Obtém o prompt pré-configurado com base no prompt_type
        pre_configured_prompt = PROMPT_DEFINITIONS.get(input_data.prompt_type, PROMPT_DEFINITIONS['other'])

        # Constrói o prompt final para o AI Studio
        final_prompt = f"{pre_configured_prompt}\n\n{content_to_send}"

        ai_response = "Não foi possível obter resposta da IA." # Valor padrão para caso de erro

        # --- CHAMADA REAL À API DO GOOGLE AI STUDIO ---
        try:
            model = genai.GenerativeModel('gemini-2.0-flash') # Ou outro modelo que você deseje usar
            response = model.generate_content(final_prompt)
            ai_response = response.text
        except Exception as e:
            # Tratar erros da API (ex: chave inválida, limite de cota, erro de rede)
            print(f"Erro ao chamar a API do Google AI Studio: {e}")
            ai_response = f"Erro ao processar sua solicitação pela IA: {e}. Verifique sua chave de API e conexão."
        
        context = {
            'ai_response': ai_response,
            'original_text': content_to_send,
            'prompt_type': input_data.get_prompt_type_display(),
            'file_name': input_data.file_name,
        }
        return render(request, 'casper/ai_studio_result.html', context)
    else:
        return redirect('casper:read_file') # Redireciona se não for um POST