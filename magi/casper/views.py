from django.shortcuts import render
import io
from django.shortcuts import render, redirect
from .forms import InputDataForm # Importação corrigida
from .models import InputData
from PyPDF2 import PdfReader
from docx import Document  # Import the library for DOCX files
from django.core.files.uploadedfile import InMemoryUploadedFile

def read_file(request):
    """
    View to read files and text provided by the user.
    """
    if request.method == 'POST':
        form = InputDataForm(request.POST, request.FILES)
        if form.is_valid():
            input_data = form.save()  # Saves the data to the database

            file_content = ""
            if input_data.file:
                file_name = input_data.file.name
                if file_name.endswith('.pdf'):
                    pdf_reader = PdfReader(input_data.file)
                    for page in pdf_reader.pages:
                        file_content += page.extract_text() + "\n"
                elif file_name.endswith('.docx'):
                    doc = Document(input_data.file)
                    for paragraph in doc.paragraphs:
                        file_content += paragraph.text + "\n"
                elif file_name.endswith('.txt'):
                    # Use the 'file' attribute of the field to access the file
                    file_content = input_data.file.read().decode('utf-8')
                elif file_name.endswith('.csv'):
                    import pandas as pd
                    df = pd.read_csv(input_data.file)
                    file_content = df.to_string()
                input_data.text = file_content #save file content
                input_data.save()
            # Redirect to a success page or do something with the content
            return redirect('casper:process_text', id=input_data.id)  # Passes the ID to the next view
    else:
        form = InputDataForm()
    return render(request, 'casper/read_file.html', {'form': form})

def process_text(request, id):
    """
    View to process the extracted text and display the content.
    """
    input_data = InputData.objects.get(pk=id) # Gets the object from the database
    text = input_data.text
    prompt_type = input_data.prompt_type
    file_name = input_data.file_name

    # Here you can call the text processing module and the text generation module
    # to get the formatted response.  For now, we just return the text.

    context = {
        'text': text,
        'prompt_type': prompt_type,
        'file_name': file_name,
    }
    return render(request, 'casper/display_text.html', context)
