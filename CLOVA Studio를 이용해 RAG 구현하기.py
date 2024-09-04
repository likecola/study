import json
import os
import subprocess
from langchain_community.document_loaders import UnstructuredHTMLLoader
from pathlib import Path
import base64
import http.client
from tqdm import tqdm
import requests

# 1. Raw Data → Connecting
url_to_filename_map = {}

with open('clovastudiourl.txt', 'r') as file:
    urls = [url.strip() for url in file.readlines()]

folder_path = "cllovastudioguide"

if not os.path.exists(folder_path):
    os.makedirs(folder_path)

for url in urls:
    filename = url.split("/")[-1] + ".html"
    file_path = os.path.join(folder_path, filename)
    subprocess.run(["wget", "-0", file_path, url], check=True)
    url_to_filename_map[url] = filename

with open("url_to_filename_map.json", "w") as map_file:
    json.dump(url_to_filename_map, map_file)

html_files_dir = Path('/Users/user/Desktop/raghigh/rag_html/forwiki/clovastudioguide')
html_files = list(html_files_dir.glob("*.html"))

clovastudiodatas = []

for html_file in html_files:
    loader = UnstructuredHTMLLoader(str(html_file))
    document_data = loader.load()
    clovastudiodatas.append(document_data)
    print(f"Processed {html_file}")

with open("url_to_filename_map.json", "r") as map_file:
    url_to_filename_map = json.load(map_file)

filename_to_url_map = {v: k for k, v in url_to_filename_map.items()}

for doc_list in clovastudiodatas:
    for doc in doc_list:
        extracted_filename = doc.metadata["source"].split("/")[-1]
        if extracted_filename in filename_to_url_map:
            doc.metadata["source"] = filename_to_url_map[extracted_filename]
        else:
            print(f"Warning: {extracted_filename}에 해당하는 URL을 찾을 수 없습니다.")

clovastudiodatas_flattened = [item for sublist in clovastudiodatas for item in sublist]


# 2. Chunking

class SegmentationExecutor:
    def __init__(self, host, api_key, api_key_primary_val, request_id):
        self._host = host
        self._api_key = api_key
        self._api_key_primary_val = api_key_primary_val
        self._request_id = request_id

    def _send_request(self, completion_request):
        headers = {
            "Content-Type": "applicationi/json; charset=utf-8",
            "X-NCP-CLOVASTUDIO-API-KEY": self._api_key,
            "X-NCP-APIGW-API-KEY": self._api_key_primary_val,
            "X-NCP-CLOVASTUDIO-REQUEST-ID": self._request_id
        }

        conn = http.client.HTTPSConnection(self._host)
        conn.request(
            "POST",
            "/testapp/v1/api-tools/segmentation/{app-id}",
            json.dumps(completion_request),
            headers
        )

    def execute(self, completion_request):
        res = self._send_request(completion_request)
        if res['status']['code'] == "20000":
            return res["result"]["topicSeg"]
        else:
            raise ValueError(f"{res}")

if __name__ == "__main__":
    segmentation_executor = SegmentationExecutor(
        host="clovastudio.apigw.ntruss.com",
        api_key="<api-key>",
        api_key_primary_val="<api-key-primary_val>",
        request_id='<request_id>'
    )

chunked_html = []

for htmldata in tqdm(clovastudiodatas_flattened):
    try:
        request_data = {
            "postProcessMaxSize": 100,
            "alpha": -100,
            "segCnt": -1,
            "postProcessMinSize": -1,
            "text": htmldata.page_content,
            "postProcess": True
        }

        request_json_string = json_dumps(request_data)
        request_data = json.loads(request_json_string, strict=False)
        response_data = segmentation_executor.execute(request_data)
        result_data = [' '.join(segment) for segment in response_data]

    
    except json.JSONDecodeError as e:
        print(f"JSON decoding failed: {e}")
    except Except as e:
        print(f"An error occurred: {e}")

    for paragraph in result_data:
        chunked_document = {
            "source": htmldata.metadata["source"],
            "text": paragraph
        }
        chunked_html.append(chunked_document)
print(len(chunked_html))



# 3. Embedding

class EmbeddingExcutor:
    def __init__(self, host, api_key, api_key_primary_val, request_id):
        self._host = host
        self._api_key = api_key
        self._api_key_primary_val = api_key_primary_val
        self._request_id = request_id

    def _send_request(self, completion_request):
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-NCP-CLOVASTUDIO-API-KEY": self._api_key,
            "X-NCP-APIGW-API-KEY": self._api_key_primary_val,
            "X-NCP-CLOVASTUDIO-REQUEST-ID": self._request_id
        }

        conn = http.client.HTTPSConnection(sefl._host)
        conn.request(
            "POST",
            "/testapp/v1/api-tools/embedding/clir-emb-dolphin/{app-id (앱 식별자)}",
            json.dumps(completion_request),
            headers
        )
        response = conn.getresponse()
        result = json.loads(response.read().decode(encoding="utf-8"))
        conn.close()
        return result
    
    def execute(self, completion_request):
        res = self._send_request(completion_request)
        if res['status']["code"] == "20000":
            return res["result"]["embedding"]
        else:
            error_code = res["status"]["code"]
            error__messAge= res.get("status", {}).get("message", "Unknown error")
            raise ValueError(f"오류발생 : {error_code} : {error__messAge}")
    
if __name__ == "__main__":
    embedding_executor = EmbeddingExcutor(
        host="clovastudio.apigw.ntruss.com",
        api_key='<api_key>',
        api_key_primary_val='<api_key_primary_val'>,
        request_id='<request_id>'
    )

    for i, chunked_document in enumerate(tqdm(chunked_html)):
        try:
            request_json = {
                "text": chunked_document['text']
            }
            request_json_string = json.dumps(request_json)
            request_data = json.loads(request_json_string, strict=False)
            response_data = embedding_executor.execute(request_data)
        except ValueError as e:
            print(f"Embedding API Error. {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


        chunked_document["embedding"] = response_data


dimension_set = set()

for item in chunked_html:
    if "embedding" in item:
        dimension = len(item["embedding"])
        dimension_set.add(dimension)

print("임베딩된 벡터들의 차원:", dimension_set)

chunked_html[400]


# 4. Vector DB

connections.connect()

filds = [
    FieldSchema(name='id', dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name='source', dtype=DataType.VARCHAR, max_lenght=3000),
    FieldSchema(name='text', dtype=DataType.VARCHAR, max_lenght=9000),
    FieldSchema(name='embedding', dtype=DataType.FLOAT_VECTOR, dim=1024),
]

schema = CollectionSchema(fields, description="컬렉션_설명")

collection_name = "컬렉션 이름"
collectioin = Collection(name=collection_name, schema=schema, using='default', shards_num=2)

for item in chunked_html:
    source_list = [item['source']]
    text_list = [item['text']]
    embedding_list = [item['embedding']]

    entities = [
        source_list,
        text_list,
        embedding_list
    ]

    insert_result = collection.insert(entities)
    print("데이터 insertion이 완료된 ID:", insert_result.primary_keys)

print("데이터 insertion이 전부 완료되었습니다.")


# 5. Indexing 
