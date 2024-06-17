from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.azure_ai.config import (
    AZUREAI_API_KEY,
    AZUREAI_API_VERSION,
    AZUREAI_SERVICE_NAME,
    AZUREAI_INDEX_NAME,
    list_indices,
    delete_index,
    create_index,
)


class AzureAIConfigurator(BaseConfigurator):
    # https://github.com/MicrosoftDocs/azure-docs/blob/main/articles/search/vector-search-how-to-query.md#similarity-metric
    # The similarity metric specified in the index vectorSearch section for a vector-only query.
    # Valid values are cosine, euclidean, and dotProduct
    DISTANCE_MAPPING = {
        Distance.L2: "euclidean",
        Distance.DOT: "dotProduct",
        Distance.COSINE: "cosine",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        if AZUREAI_API_VERSION is None:
            raise Exception(
                "An api key is required to use Azure AI Search. Specify it via AZUREAI_API_KEY=..."
            )
        self.api_version = AZUREAI_API_VERSION
        self.service_endpoint = f"https://{AZUREAI_SERVICE_NAME}.search.windows.net"

    def clean(self):
        indices = list_indices(self.service_endpoint, self.api_version, AZUREAI_API_KEY)
        len_indices = len(indices["value"])
        print(f"within clean, detected {len_indices} indices.")
        for index in indices["value"]:
            if index["name"] == AZUREAI_INDEX_NAME:
                print(
                    f"Found existing index with name {AZUREAI_INDEX_NAME}. deleting it..."
                )
                res = delete_index(
                    self.service_endpoint,
                    self.api_version,
                    AZUREAI_INDEX_NAME,
                    AZUREAI_API_KEY,
                )
                print(f"\tindex delete result: {res}")

    def recreate(self, dataset: Dataset, collection_params):
        if dataset.config.type == "sparse":
            raise Exception("Sparse vector not implemented.")
        vector_size = dataset.config.vector_size
        distance = self.DISTANCE_MAPPING[dataset.config.distance]

        hnsw_config = self.collection_params.get(
            "hnsw_config", {"m": 4, "efConstruction": 100, "efSearch": 100}
        )
        m = hnsw_config["m"]
        efConstruction = hnsw_config["efConstruction"]
        efSearch = hnsw_config["efSearch"]
        # Index definition
        index_definition = {
            "name": AZUREAI_INDEX_NAME,
            "fields": [
                {
                    "name": "Id",
                    "type": "Edm.String",
                    "key": True,
                    "searchable": False,
                    "filterable": True,
                    "retrievable": True,
                    "sortable": False,
                    "facetable": False,
                },
                {
                    "name": "VectorField",
                    "type": "Collection(Edm.Single)",
                    "searchable": True,
                    "retrievable": True,
                    "dimensions": vector_size,
                    "vectorSearchProfile": "simple-vector-profile",
                },
            ],
            "vectorSearch": {
                "algorithms": [
                    {
                        "name": "simple-hnsw-config",
                        "kind": "hnsw",
                        "hnswParameters": {
                            "m": m,
                            "efSearch": efSearch,
                            "efConstruction": efConstruction,
                            "metric": distance,
                        },
                    }
                ],
                "profiles": [
                    {"name": "simple-vector-profile", "algorithm": "simple-hnsw-config"}
                ],
            },
        }
        create_index(
            self.service_endpoint, self.api_version, AZUREAI_API_KEY, index_definition
        )
