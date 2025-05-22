# nerv/magi/casper/views.py

import os
import io
import google.generativeai as genai

from django.shortcuts import render, redirect, get_object_or_404
from .forms import InputDataForm
from .models import InputData, PromptDefinition
from PyPDF2 import PdfReader
from docx import Document
import pandas as pd

# A configuração da API Key deve ser feita uma única vez, preferencialmente em settings.py
try:
    if os.getenv("GOOGLE_API_KEY"):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    else:
        print("AVISO: Chave da API do Google AI Studio não encontrada. Funções de IA podem falhar.")
except Exception as e:
    print(f"Erro ao configurar a API do Google AI Studio: {e}")

def casper_home_view(request):
    """
    View para a página inicial do Casper, que agora lida com upload de arquivos e texto.
    """
    if request.method == 'POST':
        form = InputDataForm(request.POST, request.FILES)
        if form.is_valid():
            input_data = form.save(commit=False)
            user_question = form.cleaned_data.get('user_question', '')
            
            file_content = ""
            if input_data.file:
                file_name = input_data.file.name
                input_data.file_name = file_name
                input_data.file.seek(0) # Volta o ponteiro do arquivo para o início
                
                try:
                    if file_name.lower().endswith('.pdf'):
                        pdf_reader = PdfReader(input_data.file)
                        for page in pdf_reader.pages:
                            file_content += page.extract_text() + "\n"
                    elif file_name.lower().endswith('.docx'):
                        doc = Document(io.BytesIO(input_data.file.read()))
                        for paragraph in doc.paragraphs:
                            file_content += paragraph.text + "\n"
                    elif file_name.lower().endswith('.txt'):
                        file_content = input_data.file.read().decode('utf-8')
                    elif file_name.lower().endswith('.csv'):
                        df = pd.read_csv(io.StringIO(input_data.file.read().decode('utf-8')))
                        file_content = df.to_string()
                    else:
                        file_content = "Tipo de arquivo não suportado para leitura direta."
                        # Opcional: mostrar mensagem de erro ao usuário no template
                except Exception as e:
                    print(f"Erro ao ler o arquivo {file_name}: {e}")
                    file_content = f"Erro ao ler o arquivo: {e}"

                input_data.text = file_content
            
            request.session['user_question'] = user_question
            
            input_data.save()
            return redirect('casper:process_text', id=input_data.id)
    else: # GET request
        form = InputDataForm()
    
    context = {
        'form': form,
    }
    return render(request, 'casper/home.html', context)


# A função 'read_file' NÃO DEVE MAIS EXISTIR AQUI. Ela foi movida para casper_home_view.
# Se você tiver outras views (process_text, send_to_ai_studio), elas devem vir abaixo.

def process_text(request, id):
    """
    View para processar o texto extraído e exibir o conteúdo.
    """
    input_data = get_object_or_404(InputData, pk=id)
    text = input_data.text
    
    prompt_type_identifier = input_data.prompt_type.prompt_type if input_data.prompt_type else "N/A"
    file_name = input_data.file_name

    context = {
        'text': text,
        'prompt_type': prompt_type_identifier,
        'file_name': file_name,
        'input_data': input_data,
    }
    return render(request, 'casper/display_text.html', context)


def send_to_ai_studio(request):
    """
    View para enviar o texto processado e o prompt para o Google AI Studio.
    """
    if request.method == 'POST':
        input_data_id = request.POST.get('input_data_id')
        user_question = request.session.pop('user_question', '')

        input_data = get_object_or_404(InputData, pk=input_data_id)

        content_to_send = input_data.text
        
        if input_data.prompt_type:
            pre_configured_prompt_text = input_data.prompt_type.prompt_text
            prompt_type_identifier = input_data.prompt_type.prompt_type
        else:
            pre_configured_prompt_text = "Analise o seguinte conteúdo: "
            prompt_type_identifier = "other"

        if prompt_type_identifier == 'question' and user_question:
            final_prompt = f"{pre_configured_prompt_text} {user_question}\n\n{content_to_send}"
        else:
            final_prompt = f"{pre_configured_prompt_text}\n\n{content_to_send}"


        ai_response = "Não foi possível obter resposta da IA."

        try:
            model = genai.GenerativeModel('gemini-2.0-flash') # Confirme o nome do modelo que funciona para você
            response = model.generate_content(final_prompt)
            ai_response = response.text
        except Exception as e:
            print(f"Erro ao chamar a API do Google AI Studio: {e}")
            ai_response = f"Erro ao processar sua solicitação pela IA: {e}. Verifique sua chave de API, conexão e se o modelo está disponível."
        
        context = {
            'ai_response': ai_response,
            'original_text': content_to_send,
            'prompt_type': prompt_type_identifier,
            'file_name': input_data.file_name,
        }
        return render(request, 'casper/ai_studio_result.html', context)
    else:
        # Se for um GET para send_to_ai_studio, redireciona para a home do Casper.
        return redirect('casper:casper_home')
    