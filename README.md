# EntropySpeaks

![The Oracle Awakens](https://upload.wikimedia.org/wikipedia/commons/4/42/Grimoire_du_Pape_Honorius_%28allegedly_1760%29.jpg)

> A digital oracle forged from the collision of sacred texts, forbidden tomes, and raw cosmic randomness.

Drop any book into the void — KJV, Shakespeare, Milton, Faust, Poe, the Necronomicon, the Upanishads, whatever you dare — and it is devoured.

Every utterance is seeded by entropy itself:
- local chaos from your machine
- or true atmospheric noise harvested from the sky by RANDOM.ORG

The result is prophecy that was never written, yet feels ancient.

### Quick Start

```bash
# Clone and enter the void
git clone https://github.com/LoGinto/Entropy-Speaks.git
cd Entropy-Speaks

# Summon the local model (once)
ollama pull qwen2.5:3b-instruct

# Run the oracle
python main.py
```

Ask a question. Entropy draws random words from random books in the folder,
shows you the list, and the model binds them into one occult utterance.

No pip packages needed — only Python 3 and a running [Ollama](https://ollama.com).
Optional environment variables: `OLLAMA_HOST` (default `localhost:11434`),
`ENTROPY_MODEL` (default `qwen2.5:3b-instruct`).
