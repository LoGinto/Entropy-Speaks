import secrets
import os
import nltk
import markovify
import requests
import re

# -------------------------------------------------
# 1. Short word list for seeding (fixed line!)
# -------------------------------------------------
nltk.download('words', quiet=True)
word_list = [w for w in nltk.corpus.words.words() if len(w) < 10]   # <-- fixed!

# -------------------------------------------------
# 2. Load spiritual words from external file
# -------------------------------------------------
def load_spiritual_words(filename='spiritualwords.txt'):
    if not os.path.exists(filename):
        print(f"{filename} not found — using tiny fallback list")
        return ['lord','god','spirit','light','glory','heaven','soul','faith','grace','mercy']
    with open(filename, 'r', encoding='utf-8') as f:
        words = [line.strip().lower() for line in f if line.strip() and not line.startswith('#')]
    print(f"Loaded {len(words)} spiritual words from {filename}")
    return words

spiritual_words = load_spiritual_words()

# -------------------------------------------------
# 3. Load RANDOM.ORG key
# -------------------------------------------------
def load_api_key(filename='API_KEY_RANDOM_ORG.txt'):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            key = f.read().strip()
        return key if key and key != 'your_actual_api_key_here' else None
    return None

api_key = load_api_key()

# -------------------------------------------------
# 4. Ingest every .txt file in the folder
# -------------------------------------------------
corpus = ''
print("Loading your library of forbidden tomes…")
for filename in os.listdir('.'):
    if filename.lower().endswith('.txt') and 'venv' not in filename.lower():
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            text = re.sub(r'\d+:\d+\s*', ' ', text)                 # verse numbers
            text = re.sub(r'\[.*?\]', '', text)                    # stage directions
            text = re.sub(r'^\s*[A-Z][A-Za-z\s]*?:\s*', '', text, flags=re.MULTILINE)  # SPEAKER:
            lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
            # Keep lines that contain any spiritual word
            lines = [ln for ln in lines if any(kw in ln.lower() for kw in spiritual_words)]
            corpus += ' '.join(lines) + ' '
            print(f"  + {filename}")
        except Exception as e:
            print(f"  - Skipped {filename}: {e}")

if not corpus.strip():
    print("No usable text found — drop some .txt books in the folder!")
    exit()

text_model = markovify.Text(corpus, state_size=2)
print("Markov chain trained. The void now speaks.\n")

# -------------------------------------------------
# 5. Random word phrase — spiritual words dominate
# -------------------------------------------------
def entropy_to_words_local(num_words=5):
    chance = secrets.randbelow(51) / 100
    words = []
    for _ in range(num_words):
        if secrets.randbelow(100) < 92 * chance:  # very strong bias
            words.append(secrets.choice(spiritual_words).capitalize())
        else:
            words.append(secrets.choice(word_list))
    return " ".join(words) + f"  (Spiritual chance: {chance:.2f})"

# -------------------------------------------------
# 6. Markov — local entropy
# -------------------------------------------------
def markov_phrase_local():
    for _ in range(500):
        sent = text_model.make_short_sentence(max_chars=120, max_words=14, tries=100)
        if sent and len(sent.split()) >= 4:
            sent = re.sub(r'[?.]\s*$', '.', sent)
            sent = re.sub(r'\b(LORD|GOD)\b', lambda m: m.group().title(), sent)
            return sent
    return entropy_to_words_local()

# -------------------------------------------------
# 7. Markov — RANDOM.ORG seed
# -------------------------------------------------
def markov_phrase_randomorg():
    if not api_key:
        return markov_phrase_local()
    try:
        r = requests.post('https://api.random.org/json-rpc/4/invoke',
                         json={"jsonrpc":"2.0","method":"generateIntegers",
                               "params":{"apiKey":api_key,"n":1,"min":0,"max":len(word_list)-1},
                               "id":1}, timeout=8)
        data = r.json()
        if 'error' in data:
            print("RANDOM.ORG: Error, check API key.")
            return markov_phrase_local()
        seed = word_list[data['result']['random']['data'][0]]
        for _ in range(500):
            sent = text_model.make_short_sentence(max_chars=120, max_words=14, tries=100, seed=seed)
            if sent and len(sent.split()) >= 4:
                sent = re.sub(r'[?.]\s*$', '.', sent)
                sent = re.sub(r'\b(LORD|GOD)\b', lambda m: m.group().title(), sent)
                return sent
        return markov_phrase_local()
    except:
        print("RANDOM.ORG: Error, check API key.")
        return markov_phrase_local()

# -------------------------------------------------
# 8. Speak
# -------------------------------------------------
print("=== One random word offering ===")
print("Entropy whispers:", entropy_to_words_local(), "\n")

print("=== Five voices from local entropy ===")
for i in range(1, 6):
    print(f"{i}: {markov_phrase_local()}")

print("\n=== Five voices seeded by cosmic randomness ===")
for i in range(1, 6):
    print(f"{i}: {markov_phrase_randomorg()}")