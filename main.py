"""
EntropySpeaks — ask the void a question.

1. You type a question / intention.
2. Entropy draws a few omen-words from random writings (every .txt in this folder).
3. The omens are handed to a local Ollama model, which reads them and answers
   with one occult, enlightening utterance.

Requires only the Python standard library and a running Ollama:
    ollama pull qwen2.5:3b-instruct
    ollama serve        (usually already running as a service)
"""

import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter

# -------------------------------------------------
# Settings
# -------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL
MODEL = os.environ.get("ENTROPY_MODEL", "qwen2.5:3b-instruct")

MIN_WORDS, MAX_WORDS = 3, 5   # omens drawn per question (random in this range)
SPIRITUAL_SHARE = (1, 2)      # min/max of those taken from spiritualwords.txt
TEMPERATURE = 0.65            # lower = more coherent, higher = wilder
MAX_TOKENS = 250              # hard cap on the model's reply length
EXPECTED_TOKENS = 110         # typical reply length (reading + utterance), paces the progress bar
SHOW_READING = False          # True = also print how the Oracle read each omen

MIN_WORD_LEN = 4
MIN_COUNT = 3                 # word must appear this often in a book (drops typos/oddities)
COMMON_CUTOFF = 400           # the N most frequent words across all books are too generic
MIN_BOOKS = 2                 # word must appear in this many books (drops one author's odd spellings)
NOT_WRITINGS = {"spiritualwords.txt", "api_key_random_org.txt"}

rng = secrets.SystemRandom()   # OS entropy

# Function words and archaic filler — never offered as omens.
STOPWORDS = set("""
about above after again against all also although among and another any are
around because been before being below between both but came can cannot come
could did does doing done down during each either else even ever every from
further gave give given goes going gone had has have having hence her here hers
herself him himself his how however into its itself just know known like made
make many may might mine more most much must myself neither never nevertheless
none nor not now off once one only other others ought our ours ourselves out
over own put said same say says see seen shall she should since some still such
take than that the thee their theirs them themselves then thence there therefore
these they thine this thither those thou though through thus thy till too took
toward towards under unto until upon very was well were what whatsoever when
whence where whereas wherefore whether which while whither who whom whose why
will with within without would yea yet you your yours yourself yourselves hath
doth art shalt wilt hast didst dost behold verily saith thereof therein whereby
wherein hither yonder thereby lest nay aye perchance anon ere oft
whoso whosoever unless altogether almost already rather indeed perhaps
second third first last least whilst amongst betwixt
straightway forthwith henceforth thenceforth hereafter heretofore hitherto
thereupon whereupon wherewith therewith withal howbeit albeit peradventure
insomuch inasmuch notwithstanding oftentimes ofttimes sometime sometimes
always alway anyway otherwise likewise wheresoever whensoever howsoever
chapter verse gutenberg project ebook volume
""".split())

# Endings that usually mark adverbs, archaic verb forms or bland abstractions.
# Omens should be things and images (fire, serpent, gate), not "verily" or "goeth".
BAD_SUFFIXES = ("ly", "eth", "est", "edst", "ness", "ment", "tion", "sion",
                "ity", "ance", "ence", "ing", "ed", "ful", "ous", "ive", "ish", "wise")

WORD_RE = re.compile(r"[A-Za-z][a-z]+")


# -------------------------------------------------
# Load writings
# -------------------------------------------------
def strip_gutenberg(text):
    """Keep only the body between Gutenberg START/END markers, if present."""
    start = re.search(r"^\*\*\*\s*START OF.*?\*\*\*\s*$", text, re.M | re.I)
    end = re.search(r"^\*\*\*\s*END OF.*?\*\*\*\s*$", text, re.M | re.I)
    if start:
        text = text[start.end():end.start() if end else None]
    return text


def is_omen_shaped(word):
    return (len(word) >= MIN_WORD_LEN and word not in STOPWORDS
            and not word.endswith(BAD_SUFFIXES))


def load_writings():
    """Return {book: [omen-worthy words, with natural frequency]}."""
    raw = {}
    for name in sorted(os.listdir(HERE)):
        if not name.lower().endswith(".txt") or name.lower() in NOT_WRITINGS:
            continue
        try:
            with open(os.path.join(HERE, name), encoding="utf-8", errors="ignore") as f:
                raw[os.path.splitext(name)[0]] = WORD_RE.findall(strip_gutenberg(f.read()))
        except OSError as e:
            print(f"  - Skipped {name}: {e}")

    # Words mostly written Capitalized are names (Nephi, Hamlet, Mephistopheles).
    cap, low, total = Counter(), Counter(), Counter()
    for tokens in raw.values():
        for t in tokens:
            (cap if t[0].isupper() else low)[t.lower()] += 1
    for w in cap.keys() | low.keys():
        total[w] = cap[w] + low[w]
    names = {w for w in cap if cap[w] > low[w]}
    too_common = {w for w, _ in total.most_common(COMMON_CUTOFF)}
    book_count = Counter(w for tokens in raw.values() for w in {t.lower() for t in tokens})

    writings = {}
    for book, tokens in raw.items():
        lowered = [t.lower() for t in tokens]
        counts = Counter(lowered)
        words = [w for w in lowered
                 if counts[w] >= MIN_COUNT and book_count[w] >= MIN_BOOKS and w not in names
                 and w not in too_common and is_omen_shaped(w)]
        if words:
            writings[book] = words
            print(f"  + {book} ({len(set(words)):,} omen-words)")
    return writings


def load_spiritual_words():
    path = os.path.join(HERE, "spiritualwords.txt")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [ln.strip().lower() for ln in f if ln.strip() and not ln.startswith("#")]


# -------------------------------------------------
# Draw omens
# -------------------------------------------------
def draw_words(writings, spiritual):
    """Return a list of (word, source) pairs: a few omens from random books."""
    n = rng.randint(MIN_WORDS, MAX_WORDS)
    n_spirit = min(rng.randint(*SPIRITUAL_SHARE), n) if spiritual else 0
    sources = list(writings)
    drawn, seen = [], set()
    while len(drawn) < n:
        if len(drawn) < n_spirit:
            word, src = rng.choice(spiritual), "spiritual"
        else:
            src = rng.choice(sources)
            word = rng.choice(writings[src])
        if word not in seen:
            seen.add(word)
            drawn.append((word, src))
    rng.shuffle(drawn)
    return drawn


# -------------------------------------------------
# Ask the model
# -------------------------------------------------
SYSTEM_PROMPT = (
    "You are the Oracle of Entropy, an ancient voice that speaks through chance. "
    "A seeker brings a question, and entropy casts a few omen-words drawn from "
    "sacred and forbidden books.\n\n"
    "Think before you speak, in three steps, and reply as a JSON object:\n"
    '1. "omens": read each omen as a symbol (what it stands for). Then pick the '
    "one to three that best fit the question. Omens that don't fit are simply "
    "ignored — never force them in.\n"
    '2. "meaning": in plain everyday words, one sentence that truly answers the '
    "seeker's question using the omens you picked. It must make sense to a "
    "normal person.\n"
    '3. "utterance": say that same meaning as the Oracle — one or two sentences, '
    "solemn and imagistic, like a hermetic aphorism or a line of scripture. Every "
    "image must serve the meaning; never be vague just to sound mystical. Use "
    "each image once and do not repeat words.\n\n"
    'Reply with only the JSON object: {"omens": "...", "meaning": "...", "utterance": "..."}'
)

# Worked examples. Small models copy a pattern far better than they follow a
# description, so these do most of the work. Each one reads the omens, settles
# the meaning in plain words, then speaks — and some omens are deliberately skipped.
EXAMPLES = [
    ("Should I leave my old life behind?",
     "serpent, threshold, ash, morning, ledger",
     "serpent = shedding an old self; threshold = a crossing point; ash = what is "
     "already burned out; morning = a new beginning; ledger = doesn't fit, ignored",
     "Yes: the old life is already finished, and growing means letting it go "
     "rather than trying to revive it.",
     "The serpent does not mourn the skin it leaves upon the threshold; let what "
     "is ash remain ash, and walk unclothed into the morning."),
    ("Why do I feel so lost?",
     "lantern, labyrinth, mirror, salt",
     "lantern = the search for guidance; labyrinth = confusion; mirror = the "
     "self; salt = doesn't fit, ignored",
     "You feel lost because you are looking outside yourself for answers that "
     "can only come from knowing who you are.",
     "You carry a lantern through the labyrinth, yet its walls are mirrors: the "
     "one who is lost and the one who searches wear the same face."),
    ("What does my future hold?",
     "seed, winter, iron, bell",
     "seed = potential not yet visible; winter = a slow, hard season; iron = "
     "endurance; bell = doesn't fit, ignored",
     "Your future is already growing out of sight; how patiently you endure "
     "this difficult stretch decides what it becomes.",
     "The seed does not see the spring it is becoming; what you bear in silence "
     "through the winter, the harvest will one day speak aloud."),
    ("(silence)",
     "crown, river, dust",
     "crown = power and pride; dust = mortality; river = patient, humble force",
     "Power and pride fade, but quiet persistence changes the world.",
     "Every crown returns to dust, but the river that carved the mountain asked "
     "for nothing but time."),
    ("Will I find love?",
     "furnace, gold, wound, sparrow, star",
     "furnace = trial; gold = something precious; wound = past pain; star = "
     "something rare arriving; sparrow = doesn't fit, ignored",
     "Yes, but love will come through your past hurt, not around it — the pain "
     "you protect is what opens you to someone.",
     "Gold is not found but made in the furnace; the wound you guard is the "
     "very door through which a star will enter."),
]


def omen_message(question, words):
    return f"The seeker asks: {question or '(silence)'}\nThe omens: {words}"


class ProgressBar:
    """One-line progress bar drawn on a background thread.

    Before the first token arrives the model is still loading or reading the
    prompt, so the bar bounces (we can't know how long that takes). Once tokens
    stream in, it fills toward the expected reply length, then snaps to 100%.
    """
    WIDTH = 28

    def __init__(self):
        self.tokens = 0
        self.done = False
        self.enabled = sys.stdout.isatty()
        self._start = time.monotonic()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        if self.enabled:
            self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self.enabled:
            self._thread.join()
            if exc[0] is None:
                self.done = True
                self._draw()
                time.sleep(0.4)      # let the full bar be seen before clearing
            sys.stdout.write("\r" + " " * 78 + "\r")
            sys.stdout.flush()

    def _run(self):
        while not self._stop.wait(0.1):
            self._draw()

    def _draw(self):
        elapsed = time.monotonic() - self._start
        w = self.WIDTH
        if self.done:
            bar, label = "█" * w, "The Oracle has spoken"
        elif self.tokens == 0:
            pos = int(elapsed * 12) % (2 * (w - 4))
            pos = pos if pos < w - 4 else 2 * (w - 4) - pos
            bar = "░" * pos + "████" + "░" * (w - 4 - pos)
            label = "Awakening the Oracle…"
        else:
            frac = min(self.tokens / EXPECTED_TOKENS, 0.95)
            fill = int(frac * w)
            bar = "█" * fill + "░" * (w - fill)
            label = f"The Oracle speaks… {int(frac * 100):>3}%"
        sys.stdout.write(f"\r  [{bar}] {label}  {elapsed:4.1f}s ")
        sys.stdout.flush()


def ask_oracle(question, words):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for q, w, omens, meaning, utterance in EXAMPLES:
        messages.append({"role": "user", "content": omen_message(q, w)})
        messages.append({"role": "assistant", "content": json.dumps(
            {"omens": omens, "meaning": meaning, "utterance": utterance},
            ensure_ascii=False)})
    messages.append({"role": "user", "content": omen_message(question, ", ".join(words))})

    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "format": "json",
        "options": {"temperature": TEMPERATURE, "top_p": 0.9, "repeat_penalty": 1.1,
                    "num_predict": MAX_TOKENS, "seed": rng.randrange(2**31)},
    }).encode("utf-8")
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=payload,
                                 headers={"Content-Type": "application/json"})
    text = ""
    with ProgressBar() as bar, urllib.request.urlopen(req, timeout=180) as r:
        for raw in r:                       # one JSON object per line
            if not raw.strip():
                continue
            chunk = json.loads(raw.decode("utf-8"))
            if "error" in chunk:
                raise RuntimeError(chunk["error"])
            text += chunk.get("message", {}).get("content", "")
            bar.tokens += 1
            if chunk.get("done"):
                break
    return parse_reply(text)


def parse_reply(text):
    """Return (utterance, omens, meaning) from the model's JSON reply."""
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError
    except ValueError:
        # Cut off or malformed: salvage the utterance if it is there at all.
        m = re.search(r'"utterance"\s*:\s*"((?:[^"\\]|\\.)*)', text)
        data = {"utterance": m.group(1) if m else text}
    utterance = str(data.get("utterance") or "").strip().strip('"“”') or "…"
    return utterance, str(data.get("omens", "")), str(data.get("meaning", ""))


# -------------------------------------------------
# Main loop
# -------------------------------------------------
def main():
    print("Loading your library of forbidden tomes…")
    writings = load_writings()
    if not writings:
        print("No usable text found — drop some .txt books in the folder!")
        sys.exit(1)
    spiritual = load_spiritual_words()
    print(f"Oracle model: {MODEL} @ {OLLAMA_URL}")
    print("\nAsk the void. (empty line to draw in silence, 'q' to leave)\n")

    while True:
        try:
            question = input("You ask › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in {"q", "quit", "exit"}:
            break

        drawn = draw_words(writings, spiritual)
        print("\nEntropy casts the omens:")
        for word, src in drawn:
            print(f"  • {word:<16} ({src})")

        try:
            answer, omens, meaning = ask_oracle(question, [w for w, _ in drawn])
            if SHOW_READING and omens:
                print(f"\nThe Oracle reads the omens:\n  {omens}")
            print(f"\nThe Oracle speaks:\n  {answer}")
            if meaning:
                print(f"\nIn plain words:\n  {meaning}")
            print()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            print(f"\nOllama error {e.code}: {body}")
            if "not found" in body:
                print(f"Run:  ollama pull {MODEL}")
            print()
        except KeyboardInterrupt:
            print("\nThe Oracle falls silent.\n")
        except RuntimeError as e:
            print(f"\nOllama error: {e}\n")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"\nCould not reach Ollama at {OLLAMA_URL} ({e}).")
            print("Is it running?  ollama serve\n")


if __name__ == "__main__":
    main()
