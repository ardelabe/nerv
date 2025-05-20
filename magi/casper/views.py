import os
import io
import google.generativeai as genai
from dotenv import load_dotenv

from django.shortcuts import render, redirect
from .forms import InputDataForm
from .models import InputData, PromptDefinition # Mude PROMPT_DEFINITIONS para PromptDefinition
from PyPDF2 import PdfReader
from docx import Document
from django.core.files.uploadedfile import InMemoryUploadedFile

load_dotenv() 

try:
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
except Exception as e:
    print(f"Erro ao configurar a API do Google AI Studio: {e}")

# (Remova a função list_available_models se já não for mais necessária para depuração)
# def list_available_models():
#    ...


def read_file(request):
    """
    View to read files and text provided by the user.
    """
    if request.method == 'POST':
        form = InputDataForm(request.POST, request.FILES)
        if form.is_valid():
            input_data = form.save(commit=False)
            user_question = form.cleaned_data.get('user_question', '') # Pegue a pergunta do usuário

            file_content = ""
            if input_data.file:
                file_name = input_data.file.name
                input_data.file_name = file_name
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
                        df = pd.read_csv(input_data.file)
                        file_content = df.to_string()
                    except Exception as e:
                        print(f"Erro ao ler CSV, tentando como texto: {e}")
                        input_data.file.seek(0)
                        file_content = input_data.file.read().decode('utf-8')
                
                input_data.text = file_content
            
            # Aqui, o prompt_type é um objeto PromptDefinition, não uma string
            # Salve a pergunta do usuário em algum lugar se precisar mantê-la associada
            # Por enquanto, apenas a passaremos adiante para send_to_ai_studio
            request.session['user_question'] = user_question # Armazene na sessão temporariamente
            
            input_data.save()
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
    # Agora, prompt_type é um objeto PromptDefinition, então acesse seu 'prompt_type' (o identificador)
    # ou seu 'prompt_text' se quiser exibir o texto completo do prompt aqui.
    prompt_type_identifier = input_data.prompt_type.prompt_type if input_data.prompt_type else "N/A"
    file_name = input_data.file_name

    context = {
        'text': text,
        'prompt_type': prompt_type_identifier, # Mostra o identificador (e.g., 'summary')
        'file_name': file_name,
        'input_data': input_data,
    }
    return render(request, 'casper/display_text.html', context)


def send_to_ai_studio(request):
    """
    View to send the processed text and prompt to Google AI Studio.
    """
    if request.method == 'POST':
        input_data_id = request.POST.get('input_data_id')
        user_question = request.session.pop('user_question', '') # Recupera e remove da sessão

        try:
            input_data = InputData.objects.get(pk=input_data_id)
        except InputData.DoesNotExist:
            return render(request, 'casper/ai_studio_result.html', {'error_message': 'Dados de entrada não encontrados.'})

        content_to_send = input_data.text
        
        # Obter o texto do prompt do objeto PromptDefinition
        if input_data.prompt_type:
            pre_configured_prompt_text = input_data.prompt_type.prompt_text
            prompt_type_identifier = input_data.prompt_type.prompt_type
        else:
            pre_configured_prompt_text = "Analise o seguinte conteúdo: " # Prompt fallback
            prompt_type_identifier = "other" # Identificador fallback


        # Constrói o prompt final para o AI Studio
        # Se o prompt_type for 'question', adiciona a pergunta do usuário
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
            'prompt_type': prompt_type_identifier, # Mostra o identificador do prompt
            'file_name': input_data.file_name,
        }
        return render(request, 'casper/ai_studio_result.html', context)
    else:
        return redirect('casper:read_file')