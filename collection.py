import hashlib
from typing import Optional
import chromadb
import os
import torch
from chromadb import EmbeddingFunction, Documents, Embeddings
from dotenv import load_dotenv
import pprint
import pandas as pd
import logging
from datetime import datetime
from colorama import Fore, Style
from model.answer_model import Answer
from nltk.metrics import edit_distance
from transformers import AutoModel, AutoTokenizer
from model.question_model import Question

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

load_dotenv()  # This loads environment variables from a .env file, which is good for sensitive info like API keys

pp = pprint.PrettyPrinter(indent=4)  # PrettyPrinter makes dictionary output easier to read

# Initializes the Cohere API key from the environment variables. Raises an error if the key isn't found.
PRETRAINED_MODEL_NAME = os.getenv("PRETRAINED_MODEL_NAME")
if PRETRAINED_MODEL_NAME is None:
    raise ValueError("Pretrained model name not found in the environment variables.")


tokenizer = AutoTokenizer.from_pretrained(PRETRAINED_MODEL_NAME)
model = AutoModel.from_pretrained(PRETRAINED_MODEL_NAME)


class SentencesEmbeddingFunction(EmbeddingFunction):
    # Mean Pooling - Take attention mask into account for correct averaging
    def mean_pooling(self, model_output, attention_mask):
        token_embeddings = model_output[0]  # First element of model_output contains all token embeddings
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    def __call__(self, input: Documents) -> Embeddings:
        # embed the documents
        sentences = input
        encoded_inputs = tokenizer(sentences, padding=True, truncation=True, return_tensors='pt')

        with torch.no_grad():
            model_output = model(**encoded_inputs)

        sentence_embeddings = self.mean_pooling(model_output, encoded_inputs['attention_mask'])

        return sentence_embeddings.tolist()


chroma_client: chromadb.ClientAPI


def init_chroma_client():
    # Initializes the ChromaDB client with certain settings. These settings specify that the client should use DuckDB with Parquet for storage,
    # and it should store its data in a directory named 'database'.
    global chroma_client
    if 'chroma_client' not in globals():
        chroma_client = chromadb.PersistentClient(path="./chroma/data")


def get_chroma_q_a_collection():
    if chroma_client is None:
        raise Exception("Chroma client not initialized")

    print("getting get_chroma_q_a_collection")

    # Gets or creates a ChromaDB collection named 'q_a', using the Cohere embedding function.
    # example_collection = chroma_client.get_or_create_collection(name="q_a", embedding_function=cohere_ef)
    # Gets or creates a ChromaDB collection named 'q_a',
    # using the SentenceTransformerEmbeddingFunction embedding function.
    q_a_collection = chroma_client.get_or_create_collection(
        name="q_a",
        metadata={"hnsw:space": "cosine"},
        embedding_function=SentencesEmbeddingFunction())
    return q_a_collection


def get_chroma_questions_collection():
    if chroma_client is None:
        raise Exception("Chroma client not initialized")

    print("getting get_chroma_questions_collection")

    # Gets or creates a ChromaDB collection named 'questions', using the Cohere embedding function.
    # example_collection = chroma_client.get_or_create_collection(name="questions", embedding_function=cohere_ef)
    # Gets or creates a ChromaDB collection named 'questions',
    # using the SentenceTransformerEmbeddingFunction embedding function.
    questions_collection = chroma_client.get_or_create_collection(
        name="questions",
        metadata={"hnsw:space": "cosine"},
        embedding_function=SentencesEmbeddingFunction()
    )
    return questions_collection


def generate_sha256_hash_from_text(text):
    # Create a SHA256 hash object
    sha256_hash = hashlib.sha256()
    # Update the hash object with the text encoded to bytes
    sha256_hash.update(text.encode('utf-8'))
    # Return the hexadecimal representation of the hash
    return sha256_hash.hexdigest()


def init_model_with_exports():
    init_chroma_client()

    export_data_directory = './export_data'

    files = os.listdir(export_data_directory)

    export_domande = []
    export_risposte = []

    for file in files:
        if not file.endswith(".csv"):
            continue

        if file.startswith("export_domande"):
            export_domande.append(os.path.join(export_data_directory, file))
        elif file.startswith("export_risposte"):
            export_risposte.append(os.path.join(export_data_directory, file))

    domande_collection = get_chroma_questions_collection()
    domande_collection_count = domande_collection.count()
    print(domande_collection_count, "documenti trovati in domande_collection")

    q_a_collection = get_chroma_q_a_collection()
    q_a_collection_count = q_a_collection.count()
    print(q_a_collection_count, "documenti trovati in q_a_collection")

    print("Initializing collections.")

    for file_domande in export_domande:
        # Reads the CSV data into pandas DataFrames.
        df_domande = pd.read_csv(file_domande)
        # Converts the DataFrames to lists of dictionaries.
        domande_dict = df_domande.to_dict('records')

        domande_collection_result = domande_collection.get(include=[])

        for idx, item in enumerate(domande_dict):
            id_domanda = item['id'] if not item['id'].startswith("id_") else generate_sha256_hash_from_text(item['id'])

            if id_domanda not in domande_collection_result['ids']:
                print(f"Adding question", idx, item['text'])

                domande_collection.add(
                    documents=[item['text']],  # aggiunge la domanda ai documenti
                    metadatas=[{"id_domanda": id_domanda,
                                "id_docente": item['id_docente'],
                                "categoria": item['label'],
                                "source": item['source'],
                                "archived": item['archived'],
                                "data_creazione": item['data_creazione']}],
                    ids=[id_domanda]
                )
            else:
                print(f"Question {idx} already existing.")

    for file_risposte in export_risposte:
        # Reads the CSV data into pandas DataFrames.
        df_risposte = pd.read_csv(file_risposte)
        # Converts the DataFrames to lists of dictionaries.
        risposte_dict = df_risposte.to_dict('records')

        q_a_collection_result = q_a_collection.get(include=[])

        for idx, item in enumerate(risposte_dict):
            id_domanda = item['id_domanda'] if not item['id_domanda'].startswith("id_") \
                else generate_sha256_hash_from_text(item['id_domanda'])

            id_risposta = item['id'] if not item['id'].startswith("id_") \
                else generate_sha256_hash_from_text(item['id'])

            if id_risposta not in q_a_collection_result['ids']:
                print(f"Adding answer", idx, item['text'])

                q_a_collection.add(
                    documents=[item['text']],  # aggiunge la risposta ai documenti
                    metadatas=[{"id_domanda": id_domanda,
                                "domanda": item['title'],
                                "id_docente": item['id_docente'],
                                "id_autore": item['id_autore'],
                                "voto_docente": item['label'],
                                "voto_predetto": item['voto_predetto'],
                                "commento": item['commento'],
                                "source": item['source'],
                                "data_creazione": item['data_creazione']}],
                    ids=[id_risposta]
                )
            else:
                print(f"Answer {idx} already existing.")

    domande_collection_count = domande_collection.count()
    q_a_collection_count = q_a_collection.count()

    print(f"Collections initialized successfully. "
          f"{domande_collection_count} questions. "
          f"{q_a_collection_count} answers.")


def init_model():
    init_chroma_client()

    # Reads the CSV data into pandas DataFrames.
    df_domande = pd.read_csv('./training_data/domande_archeologia_storia_arte.csv')
    df_risposte = pd.read_csv('./training_data/risposte_archeologia_storia_arte.csv')
    df_risposte_docente = pd.read_csv('./training_data/risposte_docente_archeologia_storia_arte.csv')

    # Converts the DataFrames to lists of dictionaries.
    domande_dict = df_domande.to_dict('records')
    risposte_dict = df_risposte.to_dict('records')
    risposte_docente_dict = df_risposte_docente.to_dict('records')

    domande_collection = get_chroma_questions_collection()
    domande_collection_count = domande_collection.count()

    print(domande_collection_count, "documenti trovati in domande_collection")
    print(len(domande_dict), "domande trovate nei dati di training")

    q_a_collection = get_chroma_q_a_collection()
    q_a_collection_count = q_a_collection.count()

    print(q_a_collection_count, "documenti trovati in q_a_collection")
    print(len(risposte_dict) + len(risposte_docente_dict), "risposte trovate nei dati di training")

    limit_add = None

    # If the number of examples in the collection is less than the number of examples in the questions data,
    # adds the examples to the collection.
    if domande_collection_count < len(domande_dict):
        for idx, item in enumerate(domande_dict[domande_collection_count:]):
            index = domande_collection_count + idx
            print("\nAdding question", index, item)

            # Ottieni la data e l'ora correnti
            now = datetime.now()
            # Converti in formato ISO 8601
            iso_format = now.isoformat()

            domande_collection.add(
                documents=[item['text']],  # aggiunge la domanda ai documenti
                metadatas=[{"id_domanda": item['id'],
                            "id_docente": item['id_docente'],
                            "categoria": item['label'],
                            "source": "internal__training",
                            "archived": False,
                            "data_creazione": iso_format}],
                ids=[item['id']]
            )

            if limit_add == idx:
                break

    # If the number of examples in the collection is less than the number of examples in the q_a data,
    # adds the examples to the collection.
    if q_a_collection_count < len(risposte_docente_dict):
        for idx, item in enumerate(risposte_docente_dict[q_a_collection_count:]):
            index = q_a_collection_count + idx
            print("\nAdding risposta docente", index, item)

            # Ottieni la data e l'ora correnti
            now = datetime.now()
            # Converti in formato ISO 8601
            iso_format = now.isoformat()

            q_a_collection.add(
                documents=[item['text']],  # aggiunge la risposta ai documenti
                metadatas=[{"id_domanda": item['id_domanda'],
                            "domanda": item['title'],
                            "id_docente": item['id_docente'],
                            "id_autore": item['id_docente'],
                            "voto_docente": 5,
                            "voto_predetto": -1,
                            "commento": "undefined",
                            "source": "internal__training",
                            "data_creazione": iso_format}],
                ids=[f"id_{index}"]
            )

            if limit_add is not None and limit_add == idx:
                break

    q_a_collection_count = q_a_collection.count()

    # If the number of examples in the collection is less than the number of examples in the q_a data,
    # adds the examples to the collection.

    if q_a_collection_count < (len(risposte_docente_dict) + len(risposte_dict)):
        for idx, item in enumerate(risposte_dict[(q_a_collection_count - len(risposte_docente_dict)):]):
            index = q_a_collection_count + idx
            print("\nAdding risposta", index, item)

            # Ottieni la data e l'ora correnti
            now = datetime.now()
            # Converti in formato ISO 8601
            iso_format = now.isoformat()

            q_a_collection.add(
                documents=[item['text']],  # aggiunge la risposta ai documenti
                metadatas=[{"id_domanda": item['id_domanda'],
                            "domanda": item['title'],
                            "id_docente": item['id_docente'],
                            "id_autore": "undefined",
                            "voto_docente": item['label'],  # voto del docente che va da 0 a 5
                            "voto_predetto": -1,  # voto non disponibile per i dati di addestramento, default -1
                            "commento": "undefined",
                            "source": "internal__training",
                            "data_creazione": iso_format}],
                ids=[f"id_{index}"]
            )

            if limit_add is not None and limit_add == idx:
                break


def check_answer_records():
    init_chroma_client()

    # Reads the CSV data into pandas DataFrames.
    df_risposte = pd.read_csv('./training_data/risposte_archeologia_storia_arte.csv')
    df_risposte_docente = pd.read_csv('./training_data/risposte_docente_archeologia_storia_arte.csv')

    # Converts the DataFrames to lists of dictionaries.
    risposte_dict = df_risposte.to_dict('records')
    risposte_docente_dict = df_risposte_docente.to_dict('records')

    q_a_collection = get_chroma_q_a_collection()
    q_a_collection_count = q_a_collection.count()

    risposte_docente_result = q_a_collection.get(
        where={"id_autore": {"$ne": "undefined"}}
    )

    ok = True

    print("len(risposte_docente_result['documents'])", len(risposte_docente_result['documents']))
    print("len(risposte_docente_dict)", len(risposte_docente_dict))

    if len(risposte_docente_result['documents']) == len(risposte_docente_dict):
        for idx, item in enumerate(risposte_docente_dict):
            if item['text'] not in risposte_docente_result['documents']:
                print(item['text'], "non trovato")
                ok = False

    risposte_result = q_a_collection.get(
        where={"id_autore": "undefined"}
    )

    print("len(risposte_result['documents'])", len(risposte_result['documents']))
    print("len(risposte_dict)", len(risposte_dict))

    if len(risposte_result['documents']) == len(risposte_dict):
        for idx, item in enumerate(risposte_dict):
            if item['text'] not in risposte_result['documents']:
                print(item['text'], "non trovato")
                ok = False

    print("check_answer_records", ok)

def calcola_voto_finale_ponderato(punteggi, voti):
    if len(punteggi) == 0:
        raise ValueError("I punteggi non possono essere vuoti")

    if punteggi[0] == 0 or len(punteggi) == 1:
        # Se il primo punteggio è 0, abbiamo trovato una risposta identica, restituisci quindi il suo voto
        # Se invece è presente solo una risposta, restituisci il suo voto
        return voti[0]

    # Calcola l'inverso di ciascun punteggio
    inversi = [1 / punteggio for punteggio in punteggi]

    # Calcola la somma totale degli inversi
    somma_totale_inversi = sum(inversi)

    # Calcola il peso di ciascun punteggio in base all'inverso
    pesi = [inverso / somma_totale_inversi for inverso in inversi]

    print("Document distances weights:", pesi)

    if pesi[0] >= 0.9:
        # Se il primo è almeno il 90% rispetto agli altri, assegna il suo voto
        voto_finale_ponderato = voti[0]
    else:
        # Calcola il voto finale ponderato come la somma dei prodotti dei voti per i loro pesi corrispondenti
        voto_finale_ponderato = sum(voto * peso for voto, peso in zip(voti, pesi))

    return voto_finale_ponderato


def adjust_score(distances, score, reduction_start=0.1, reduction_end=0.6):
    """
        Corregge il punteggio basato sulla distanza minima da un punto di riferimento,
        applicando una riduzione proporzionale all'interno di un intervallo definito.

        Parametri:
        - distances (list[float]): Una lista di distanze, dove il primo elemento è considerato
          la distanza minima per la correzione del punteggio.
        - score (float): Il punteggio originale da correggere basato sulla distanza minima.
        - reduction_start (float, opzionale): La distanza a partire dalla quale iniziare la riduzione
          del punteggio. Default a 0.15.
        - reduction_end (float, opzionale): La distanza oltre la quale il punteggio viene ridotto a 0.
          Default a 1.

        Restituisce:
        - float: Il punteggio corretto, arrotondato a una cifra decimale.

        Solleva:
        - ValueError: Se `distances` è vuoto oppure se `reduction_start` è minore di 0 o maggiore di `reduction_end`.

        Note:
        - La funzione calcola una percentuale di riduzione basata sulla posizione della distanza
          minima rispetto all'intervallo definito da `reduction_start` e `reduction_end`.
        - Per distanze inferiori a `reduction_start`, il punteggio rimane invariato. Per distanze
          superiori a `reduction_end`, il punteggio viene impostato a 0. Per distanze intermedie,
          il punteggio viene ridotto proporzionalmente.
        """

    if len(distances) == 0:
        raise ValueError("Le distanze non possono essere vuote")

    min_distance = distances[0]

    if reduction_start < 0 or reduction_start > reduction_end:
        raise ValueError("Valori di riduzione non validi")

    # Se la distanza minima è maggiore di 0.6, il punteggio diventa 0
    if min_distance > reduction_end:
        return 0

    # Se la distanza minima è sotto la soglia, il punteggio rimane invariato
    if min_distance < reduction_start:
        return score

    # Calcola la percentuale da sottrarre basata sulla distanza
    percentage_to_subtract = (min_distance - reduction_start) / (reduction_end - reduction_start)
    print("percentage_to_subtract:", percentage_to_subtract)
    adjusted_result = score * (1 - percentage_to_subtract)

    return round(adjusted_result, 1)


def get_similar_sentences(id_domanda: str, sentence_to_compare_text):
    q_a_collection = get_chroma_q_a_collection()

    results = q_a_collection.query(
        query_texts=[sentence_to_compare_text],
        n_results=10,
        where={"$and": [{"id_domanda": id_domanda},
                        {"voto_docente": {"$gt": -1}}]},  # seleziona solo le risposte valutate dal docente
        include=["documents", "metadatas", "distances"]
    )

    print(f"{Fore.YELLOW}{Style.BRIGHT}Found {len(results['documents'][0])} similar documents{Style.RESET_ALL}:")

    distances = [round(abs(x), 3) for x in results['distances'][0]]

    for idx, doc in enumerate(results['documents'][0]):
        it_metadata = results['metadatas'][0][idx]
        it_distance = distances[idx]
        print(f" - Doc {idx} ({it_metadata['id_autore']}): Vote: {it_metadata['voto_docente']} | Distance: {it_distance}", doc)

    levenshtein_distance = edit_distance(sentence_to_compare_text, results['documents'][0][0])

    print(f"\n{Fore.CYAN}Best similarity match{Style.RESET_ALL}:\n"
          f"\tCosine Distance: {distances[0]}"
          f"\tLevenshtein Distance: {levenshtein_distance}"
          f"\n\tRef. Result: {Fore.GREEN if results['metadatas'][0][0]['voto_docente'] >= 3 else Fore.RED}{results['metadatas'][0][0]['voto_docente']}{Style.RESET_ALL}"
          f"\n\tDocument: {results['documents'][0][0]}"
          f"\n\tAuthor: {results['metadatas'][0][0]['id_autore']}")

    voti = extract_metadata_from_query_result(results['metadatas'], 'voto_docente')
    voto_ponderato = round(calcola_voto_finale_ponderato(distances, voti), 1)
    final_score = adjust_score(distances, voto_ponderato)

    print(
        f"{Fore.GREEN}Result Detected: {Fore.YELLOW}{Style.BRIGHT}{voto_ponderato}{Style.RESET_ALL}"
    )

    print(
        f"{Fore.GREEN}Fixed score: {Fore.YELLOW}{Style.BRIGHT}{final_score}{Style.RESET_ALL}"
    )

    return final_score


def add_answer_to_collection(authenticated_user, question: Question, answer_text: str,
                             error_callback=None, fake_add=False):
    voto_ponderato = get_similar_sentences(question.id, answer_text)

    # Ottieni la data e l'ora correnti
    now = datetime.now()
    # Converti in formato ISO 8601
    iso_format = now.isoformat()

    id_risposta = generate_sha256_hash_from_text(f"{question.id}_{authenticated_user['username']}")

    if not fake_add:
        q_a_collection = get_chroma_q_a_collection()

        try:
            q_a_collection.add(
                documents=[answer_text],  # aggiunge la risposta ai documenti
                metadatas=[{"id_domanda": question.id,
                            "domanda": question.domanda,
                            "id_docente": question.id_docente,
                            "id_autore": authenticated_user['username'],
                            "voto_docente": -1,
                            "voto_predetto": voto_ponderato,
                            "commento": "undefined",
                            "source": "application",
                            "data_creazione": iso_format}],
                ids=[id_risposta]
            )
        except ValueError:
            if error_callback is not None:
                error_callback("Errore durante l'inserimento della risposta.")

            return None

    answer = Answer(
        id_risposta,
        question.id,
        question.domanda,
        question.id_docente,
        answer_text,
        authenticated_user['username'],
        -1,
        voto_ponderato,
        "undefined",
        "application",
        iso_format,
    )

    return answer


def add_question_to_collection(authenticated_user, categoria: str, question_text: str,
                               ref_answer_text: str, error_callback=None) -> Optional[Question]:
    questions_collection = get_chroma_questions_collection()
    q_a_collection = get_chroma_q_a_collection()

    # Ottieni la data e l'ora correnti
    now = datetime.now()
    # Converti in formato ISO 8601
    iso_format = now.isoformat()

    id_domanda = generate_sha256_hash_from_text(f"{authenticated_user['username']}_q_{iso_format}")
    id_risposta = generate_sha256_hash_from_text(f"{authenticated_user['username']}_a_{iso_format}")

    try:
        questions_collection.add(
            documents=[question_text],  # aggiunge la domanda ai documenti
            metadatas=[{"id_domanda": id_domanda,
                        "id_docente": authenticated_user['username'],
                        "categoria": categoria,
                        "source": "application",
                        "archived": False,
                        "data_creazione": iso_format}],
            ids=[id_domanda]
        )

        q_a_collection.add(
            documents=[ref_answer_text],  # aggiunge la risposta ai documenti
            metadatas=[{"id_domanda": id_domanda,
                        "domanda": question_text,
                        "id_docente": authenticated_user['username'],
                        "id_autore": authenticated_user['username'],
                        "voto_docente": 5,
                        "voto_predetto": -1,
                        "commento": "undefined",
                        "source": "application",
                        "data_creazione": iso_format}],
            ids=[id_risposta]
        )
    except ValueError:
        if error_callback is not None:
            error_callback("Errore durante l'inserimento della domanda.")

        return None

    question = Question(
        id_domanda,
        question_text,
        authenticated_user['username'],
        categoria,
        "application",
        False,
        iso_format,
    )

    return question


def get_collections():
    if chroma_client is None:
        raise Exception("Chroma client not initialized")

    print("getting collections")

    question_collection = get_chroma_questions_collection()
    q_a_collection = get_chroma_q_a_collection()

    return question_collection, q_a_collection


def extract_data(query_result):
    result = []

    if query_result is not None:
        for i, metadata in enumerate(query_result['metadatas']):
            data = {
                'id': query_result['ids'][i],
                'document': query_result['documents'][i] if query_result['documents'] is not None else None,
                'embeddings': query_result['embeddings'][i] if query_result['embeddings'] is not None else None
            }
            for key, value in metadata.items():
                data[key] = value
            result.append(data)

    return result


def extract_metadata_from_query_result(data, key):
    # Inizializza una lista vuota per i valori di status
    metadata_values = []

    # Itera attraverso i dati per trovare tutte le occorrenze del valore 'key'
    for item in data:
        for sub_item in item:
            # Se la chiave è presente nell'elemento corrente, aggiungi il suo valore alla lista dei valori di status
            if key in sub_item:
                metadata_values.append(sub_item[key])

    # Restituisci la lista dei valori di status
    return metadata_values


def extract_metadata_from_get_result(data, key):
    # Inizializza una lista vuota per i valori di status
    metadata_values = []

    # Itera attraverso i dati per trovare tutte le occorrenze del valore 'key'
    for item in data:
        print("item", item)
        # Se la chiave è presente nell'elemento corrente, aggiungi il suo valore alla lista dei valori di status
        if key in item:
            metadata_values.append(item[key])

    # Restituisci la lista dei valori di status
    return metadata_values
