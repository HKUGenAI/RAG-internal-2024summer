import os
import base64
import re
from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter

import openai
from openai import AzureOpenAI

load_dotenv()

openai.api_type = "azure"
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.azure_endpoint = os.getenv("OPENAI_API_ENDPOINT")
openai.api_version = os.getenv("OPENAI_API_VERSION")

client = AzureOpenAI(
    api_key = os.getenv("OPENAI_API_KEY"),
    api_version = os.getenv("OPENAI_API_VERSION"),
    azure_endpoint = os.getenv("OPENAI_API_ENDPOINT")
)

# def compute_embedding(text):
    # return openai.Embedding.create(engine="embedding", input=text)["data"][0]["embedding"]

def compute_embedding(text, model="textembedding"): # model=[Deployment Name]
   text = text.replace("\n", " ")
   return client.embeddings.create(input = [text], model=model).data[0].embedding

filename="./data/" + "The_Innovation_Wings.pdf" #Change to name of your file (make sure the file name does not include any space)

offset = 0       #The character count from the start of the document
page_map = []    #List of tuples: (page_num, offset, page_text)

print(f"Extracting text from '{filename}' using PdfReader")

reader = PdfReader(filename)
pages = reader.pages
for page_num, p in enumerate(pages):
    page_text = p.extract_text()
    page_map.append((page_num, offset, page_text))
    offset += len(page_text)

MAX_SECTION_LENGTH = 1000
SENTENCE_SEARCH_LIMIT = 100
SECTION_OVERLAP = 100


def filename_to_id(filename): 
    filename_ascii = re.sub("[^0-9a-zA-Z_-]", "_", filename)
    filename_hash = base64.b16encode(filename.encode('utf-8')).decode('ascii')
    return f"file-{filename_ascii}-{filename_hash}"

def split_text(page_map):
    SENTENCE_ENDINGS = [".", "!", "?"]
    WORDS_BREAKS = [",", ";", ":", " ", "(", ")", "[", "]", "{", "}", "\t", " "]

    def find_page(offset):
        l = len(page_map)
        for i in range(l - 1):
            if offset >= page_map[i][1] and offset < page_map[i + 1][1]:
                return i
        return l - 1

    all_text = "".join(p[2] for p in page_map)
    length = len(all_text)
    start = 0
    end = length
    while start + SECTION_OVERLAP < length:
        last_word = -1
        end = start + MAX_SECTION_LENGTH

        if end > length:
            end = length
        else:
            # Try to find the end of the sentence
            while end < length and (end - start - MAX_SECTION_LENGTH) < SENTENCE_SEARCH_LIMIT and all_text[end] not in SENTENCE_ENDINGS:
                if all_text[end] in WORDS_BREAKS:
                    last_word = end
                end += 1
            if end < length and all_text[end] not in SENTENCE_ENDINGS and last_word > 0:
                end = last_word # Fall back to at least keeping a whole word
        if end < length:
            end += 1

        # Try to find the start of the sentence or at least a whole word boundary
        last_word = -1
        while start > 0 and start > end - MAX_SECTION_LENGTH - 2 * SENTENCE_SEARCH_LIMIT and all_text[start] not in SENTENCE_ENDINGS:
            if all_text[start] in WORDS_BREAKS:
                last_word = start
            start -= 1
        if all_text[start] not in SENTENCE_ENDINGS and last_word > 0:
            start = last_word
        if start > 0:
            start += 1

        section_text = all_text[start:end]
        yield (section_text, find_page(start))

        last_table_start = section_text.rfind("<table")
        if (last_table_start > 2 * SENTENCE_SEARCH_LIMIT and last_table_start > section_text.rfind("</table")):
            # If the section ends with an unclosed table, we need to start the next section with the table.
            # If table starts inside SENTENCE_SEARCH_LIMIT, we ignore it, as that will cause an infinite loop for tables longer than MAX_SECTION_LENGTH
            # If last table starts inside SECTION_OVERLAP, keep overlapping
            start = min(end - SECTION_OVERLAP, start + last_table_start)
        else:
            start = end - SECTION_OVERLAP
        
    if start + SECTION_OVERLAP < end:
        yield (all_text[start:end], find_page(start))

sections = []
file_id = filename_to_id(filename)
for i, (content, pagenum) in enumerate(split_text(page_map)):
    section = {
        "id": f"{file_id}-page-{i}",
        "content": content,
        "embedding": compute_embedding(content),
        "sourcepage": os.path.splitext(os.path.basename(filename))[0] + f"-{pagenum}" + ".pdf",
        "sourcefile": filename
    }
    sections.append(section)

##############################################################
import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential

from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
# from azure.search.documents.indexes.models import SearchIndex, SearchField, SimpleField, SemanticSearch, SemanticConfiguration
from azure.search.documents.indexes.models import *

load_dotenv()
service_endpoint = f"{os.getenv('AZURE_SEARCH_SERVICE_ENDPOINT')}"
index_creds = AzureKeyCredential(os.getenv("AZURE_SEARCH_INDEX_KEY"))
index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

# Create a client for querying the index
search_client = SearchClient(endpoint=service_endpoint, index_name=index_name, credential=index_creds)

i = 0
batch = []
#index 1000 sections at a time
for s in sections:
    batch.append(s)
    i += 1
    if i % 1000 == 0:
        results = search_client.upload_documents(documents=batch)
        succeeded = sum([1 for r in results if r.succeeded])
        print(f"\tIndexed {len(results)} sections, {succeeded} succeeded")
        batch = []
        
#index the remaining sections
if len(batch) > 0:
    results = search_client.upload_documents(documents=batch)
    succeeded = sum([1 for r in results if r.succeeded])
    print(f"\tIndexed {len(results)} sections, {succeeded} succeeded")

##################################################################
query = "Innowing" #your query keywords
query_vector = compute_embedding(query)

def nonewlines(s: str) -> str:
    return s.replace(' ', ' ').replace('\r', ' ')

r = search_client.search(query, 
                        top=3, 
                        vector=query_vector, 
                        top_k=50, 
                        vector_fields="embedding")

results = [doc["sourcepage"] + ": " + nonewlines(doc["content"]) for doc in r]

for result in results:
    print(result)
