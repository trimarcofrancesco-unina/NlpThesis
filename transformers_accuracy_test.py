import pprint
import logging
import pandas as pd
from colorama import Fore, Style
from halo import Halo
from collection import init_chroma_client, get_similar_sentences

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

pp = pprint.PrettyPrinter(indent=4)  # PrettyPrinter makes dictionary output easier to read

df_risposte = pd.read_csv('training_data/risposte_test.csv')

risposte_dict = df_risposte.to_dict('records')

correct = 0
total = 0

spinner = Halo(text='Loading...', spinner='dots')  # Creates a loading animation
spinner.start()

init_chroma_client()

for idx, item in enumerate(risposte_dict):  # per ogni risposta
    id_domanda = item['id_domanda']
    voto_giudice = item['label']

    print("")
    print("Domanda test:", item['title'])
    print("Risposta test:", item['text'])

    voto_predetto = get_similar_sentences(id_domanda, item['text'])

    print(
        f"{Fore.GREEN}Test Label: {Fore.YELLOW}{Style.BRIGHT}{voto_giudice}{Style.RESET_ALL}"
    )
    print(
        f"{Fore.GREEN}Final Score: {Fore.YELLOW}{Style.BRIGHT}{voto_predetto}{Style.RESET_ALL}"
    )

    if abs(voto_predetto - voto_giudice) <= 0.5:
        correct += 1

        print(
            f"{Fore.GREEN}Final Result: {Fore.GREEN}{Style.BRIGHT}[PASSED]{Style.RESET_ALL}"
        )
    else:
        print(
            f"{Fore.GREEN}Final Result: {Fore.RED}{Style.BRIGHT}[FAILED]{Style.RESET_ALL}"
        )

    total += 1

spinner.stop()  # Stops the loading animation after receiving the response

print("")
print("Accuracy:", correct / total)
