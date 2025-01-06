# BFO-FormalLogicOllama-guided
For building ontologies using prompted queries
# BFO + Ollama Ontology System

This project is an **interactive** system that builds a **Basic Formal Ontology (BFO)**-based knowledge graph from natural language statements. It supports:

1. **Guided mode**: The user manually enters statements, which the system parses and stores in `knowledge.json` / `ontology.owl`.  
2. **Auto mode**: The system queries **Ollama** (a local LLM runner) for clarifications and attempts to **self-answer** them, storing facts in `auto_knowledge.json` / `auto_ontology.owl`.  

We also integrate **rdflib** to **export** the knowledge graph as an **OWL** file (RDF/XML), plus handle:
- **Negation** (`"car is not a living organism"` → `~∃x (LivingOrganism(x) & x=Car)`)
- **Pronoun resolution** (naive approach: “it” → last subject)
- **Ollama** calls for clarifications about each new entity

## Goals

- **Build** an evolving knowledge base in line with **BFO**.  
- **Store** symbolic formal logic (SFL) statements, e.g., `∃x (Vehicle(x) & x=Car)`.  
- **Export** an **OWL** ontology for external tools like Protégé.  
- **Separate** guided vs. auto knowledge so users can see which facts were added manually vs. automatically.  

## Dependencies

- **Python 3.9+** (or similar)
- [`spaCy`](https://spacy.io/) for parsing  
- [`rdflib`](https://pypi.org/project/rdflib/) for ontology export  
- A local [Ollama](https://docs.ollama.ai/) installation for LLM-based clarifications (model name default is `llama3`).


## Notes
spaCy is used for NLP parsing (finding subjects, objects, negation words, etc.).
rdflib is for RDF/OWL generation.
If you use a specific version of spaCy or rdflib, you can pin the version explicitly, e.g. spacy==3.5.1.
This file doesn’t include Ollama because Ollama isn’t installed via pip; it’s a separate local LLM runtime. Make sure Ollama is installed on your system per its own instructions.
With these packages installed, plus the en_core_web_sm model downloaded, you’ll be able to run the BFOtoSFL.py script and build your ontology.
