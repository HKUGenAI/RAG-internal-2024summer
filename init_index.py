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

# Create an index
client = SearchIndexClient(service_endpoint, index_creds)

fields = [
    SimpleField(name="id", type="Edm.String", key=True),
    SearchableField(name="content", type="Edm.String", analyzer_name="standard.lucene"),
    SearchField(name="embedding", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),  
                hidden=False, searchable=True, filterable=False, sortable=False, facetable=False,
                vector_search_dimensions=1536, vector_search_profile_name="my-vector-config"),
    SimpleField(name="sourcepage", type="Edm.String", filterable=True, facetable=True),
    SimpleField(name="sourcefile", type="Edm.String", filterable=True, facetable=True),
]

index = SearchIndex(
    name=index_name, 
    fields=fields,
    # semantic_search=SemanticSearch(
    #     configurations=[SemanticConfiguration(
    #         name="default",
    #         prioritized_fields=[SemanticPrioritizedFields(title_field=None, content_fields=[SemanticField(field_name="content")])],
    #     )]
    # ),
    
    vector_search=VectorSearch(
        profiles=[VectorSearchProfile(
            name="my-vector-config",
            algorithm_configuration_name="my-hnsw")
        ],
        algorithms=[
            # VectorSearchAlgorithmConfiguration(
            #     name="myHnsw",
            #     # kind="hnsw"
            #     kind=VectorSearchAlgorithmKind.HNSW,
            # ) # I followed the documents on official website, but it doesn't work
            HnswAlgorithmConfiguration(name="my-hnsw")
        ]
    )
)

result = client.create_index(index)
# result = client.create_or_update_index(index, allow_index_downtime=True)