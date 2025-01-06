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

You can install these with:

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
