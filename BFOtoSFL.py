import os
import json
import sys
import spacy
import subprocess
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef, Literal

##############################################################################
# Configuration
##############################################################################

OLLAMA_MODEL = "llama3"

GUIDED_JSON_FILENAME = "knowledge.json"
GUIDED_OWL_FILENAME = "ontology.owl"
AUTO_JSON_FILENAME = "auto_knowledge.json"
AUTO_OWL_FILENAME = "auto_ontology.owl"

AUTO_MODE = False

EX = Namespace("http://example.org/ex#")
BFO = Namespace("http://example.org/bfo#")

BFO_CLASSES = {
    'teacher': 'Teacher',
    'student': 'Student',
    'learning': 'Learning',
    'object': 'Object',
    'physical thing': 'PhysicalThing',
    'wheel': 'Wheel',
    'car': 'Car',
    'process': 'Process',
    'teaching': 'Teaching',
    'mathematics': 'Mathematics',
    'dog': 'Dog',
    'vehicle': 'Vehicle',
    'planet': 'Planet',
}
BFO_RELATIONS = {
    'part-of': 'partOf',
    'has-part': 'hasPart',
    'causes': 'causes'
}

knowledge = {}
logic_history = []
last_subject = None

def current_json_filename():
    return AUTO_JSON_FILENAME if AUTO_MODE else GUIDED_JSON_FILENAME

def current_owl_filename():
    return AUTO_OWL_FILENAME if AUTO_MODE else GUIDED_OWL_FILENAME

def load_knowledge():
    global knowledge
    fn = current_json_filename()
    if os.path.exists(fn):
        with open(fn, 'r', encoding='utf-8') as f:
            data = json.load(f)
        knowledge = {}
        for subj, rels in data.items():
            knowledge[subj] = {}
            for rel, objs in rels.items():
                knowledge[subj][rel] = set(objs)
    else:
        knowledge = {}

def save_knowledge():
    fn = current_json_filename()
    data = {}
    for subj, rels in knowledge.items():
        data[subj] = {}
        for rel, objs in rels.items():
            data[subj][rel] = list(objs)
    with open(fn, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def generate_owl():
    g = Graph()
    g.bind("ex", EX)
    g.bind("bfo", BFO)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("rdf", RDF)
    
    for subj, rels in knowledge.items():
        subj_uri = EX[subj]
        for rel, objs in rels.items():
            for obj in objs:
                obj_uri = EX[obj]
                if rel == "isa":
                    g.add((subj_uri, RDF.type, obj_uri))
                elif rel.startswith("neg-isa"):
                    g.add((subj_uri, EX["negIsa"], obj_uri))
                elif rel.startswith("neg-relation"):
                    parts = rel.split("neg-relation-")
                    if len(parts) == 2:
                        rname = parts[1]
                        neg_uri = EX[f"neg{rname.capitalize()}"]
                        g.add((subj_uri, neg_uri, obj_uri))
                    else:
                        g.add((subj_uri, EX["negRelation"], obj_uri))
                else:
                    rel_uri = EX[rel]
                    g.add((subj_uri, rel_uri, obj_uri))
    
    fn = current_owl_filename()
    g.serialize(destination=fn, format='xml')

nlp = spacy.load("en_core_web_sm")
NEGATION_WORDS = {"not", "no", "never"}

def replace_pronouns(statement):
    global last_subject
    if not last_subject:
        return statement
    tokens = statement.split()
    replaced = []
    for t in tokens:
        low = t.lower().strip(",.!?")
        if low in ["it", "they", "them"]:
            replaced.append(last_subject)
        else:
            replaced.append(t)
    return " ".join(replaced)

def parse_statement_spacy(statement):
    global last_subject
    statement = statement.strip()
    if statement.startswith("?"):
        return None
    
    s2 = replace_pronouns(statement)
    doc = nlp(s2)
    
    is_negation = any(tok.lower_ in NEGATION_WORDS for tok in doc)
    
    root = None
    for t in doc:
        if t.dep_ == "ROOT":
            root = t
            break
    if not root:
        return [('error', 'No root found')]
    
    root_lemma = root.lemma_.lower()
    subjs = [t for t in doc if t.dep_ in ("nsubj","nsubjpass") and t.head == root]
    objs  = [t for t in doc if t.dep_ in ("dobj","pobj","obj","attr","acomp") and t.head == root]
    
    subj_txt = subjs[0].text if subjs else None
    obj_txt  = objs[0].text if objs else None
    
    def make_triple(typ, r, s, o):
        return (typ, r, s, o)
    
    if root_lemma in ["is","be"]:
        if subj_txt and obj_txt:
            if is_negation:
                return [make_triple('negation', 'isa', subj_txt, obj_txt)]
            else:
                return [('isa', subj_txt, obj_txt)]
        else:
            return [('error', 'incomplete is-a statement')]
    else:
        if subj_txt and obj_txt:
            if is_negation:
                return [make_triple('negation', root_lemma, subj_txt, obj_txt)]
            else:
                return [('relation', root_lemma, subj_txt, obj_txt)]
        else:
            return [('error', f'incomplete relation: {root_lemma}')]

def classify_token(token_text):
    t_lower = token_text.lower()
    if t_lower in BFO_CLASSES:
        return ('class', BFO_CLASSES[t_lower])
    if t_lower in BFO_RELATIONS:
        return ('relation', BFO_RELATIONS[t_lower])
    return ('name', token_text)

def to_sfl_expression(parse_output):
    pieces = []
    for item in parse_output:
        typ = item[0]
        
        if typ == 'isa':
            # item = ('isa', subj, obj)
            _, subj, obj = item
            subj_type, subj_val = classify_token(subj)
            obj_type, obj_val   = classify_token(obj)
            expr = f"∃x ({obj_val}(x) & x={subj_val})"
            pieces.append(expr)
        
        elif typ == 'relation':
            # item = ('relation', rel, subj, obj)
            _, rel, subj, obj = item
            subj_type, subj_val = classify_token(subj)
            obj_type, obj_val   = classify_token(obj)
            rel_val = BFO_RELATIONS.get(rel, rel)
            expr = f"{rel_val}({subj_val},{obj_val})"
            pieces.append(expr)
        
        elif typ == 'negation':
            # item = ('negation', r, s, o)
            _, r, s, o = item
            s_type, s_val = classify_token(s)
            o_type, o_val = classify_token(o)
            if r == 'isa':
                expr = f"~∃x ({o_val}(x) & x={s_val})"
            else:
                rel_val = BFO_RELATIONS.get(r, r)
                expr = f"~{rel_val}({s_val},{o_val})"
            pieces.append(expr)
        
        elif typ == 'error':
            pieces.append(f"[ERROR: {item[1]}]")
        
        else:
            pieces.append(f"[ERROR: unknown parse type: {item}]")

    return " & ".join(pieces)

def store_fact(subject, relation, obj):
    subject = subject.strip()
    obj = obj.strip()
    if subject not in knowledge:
        knowledge[subject] = {}
    if relation not in knowledge[subject]:
        knowledge[subject][relation] = set()
    knowledge[subject][relation].add(obj)
    
    save_knowledge()
    generate_owl()

def process_statement(statement):
    global last_subject
    parse_result = parse_statement_spacy(statement)
    if parse_result is None:
        return None
    
    sfl_str = to_sfl_expression(parse_result)
    if "[ERROR:" not in sfl_str:
        logic_history.append(sfl_str)
    
    for item in parse_result:
        typ = item[0]
        if typ == 'isa':
            _, subj, obj = item
            store_fact(subj, 'isa', obj.lower())
            last_subject = subj
        elif typ == 'relation':
            _, rel, s, o = item
            store_fact(s, rel, o.lower())
            last_subject = s
        elif typ == 'negation':
            _, r, s, o = item
            if r == 'isa':
                store_fact(s, 'neg-isa', o.lower())
            else:
                store_fact(s, f"neg-relation-{r}", o.lower())
            last_subject = s
        # else error
    
    return sfl_str

def query_entity(entity):
    lines = []
    found_something = False
    
    if entity in knowledge:
        out_rels = knowledge[entity]
        if out_rels:
            lines.append("Outgoing relations:")
            for rel, targets in out_rels.items():
                for t in targets:
                    lines.append(f"  {entity} -[{rel}]-> {t}")
            found_something = True
    
    incoming = []
    for s, rels in knowledge.items():
        for r, objs in rels.items():
            if entity in objs:
                incoming.append((s, r))
    if incoming:
        lines.append("Incoming relations:")
        for (x, r) in incoming:
            lines.append(f"  {x} -[{r}]-> {entity}")
        found_something = True
    
    if not found_something:
        lines.append(f"No information about {entity}.")
    return "\n".join(lines)

def ask_ollama(prompt):
    cmd = [
        "ollama", "run", OLLAMA_MODEL
    ]
    result = subprocess.run(cmd, input=prompt, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        err_out = result.stderr.decode("utf-8", errors="ignore")
        return f"[ERROR from Ollama]: {err_out}"
    return result.stdout.strip()

def generate_clarification_questions(entity):
    prompt = f"""You are building an ontology using Basic Formal Ontology (BFO).
We just learned about an entity named '{entity}'.
Please propose 1-3 concise questions about '{entity}' to clarify how it fits into BFO.
Respond with short bullet points, each a question.
"""
    return ask_ollama(prompt)

def parse_ollama_questions(response):
    lines = response.splitlines()
    questions = []
    for line in lines:
        line = line.strip("-* \t")
        if line:
            questions.append(line)
    return questions

def auto_answer_question(entity, question):
    known_facts = query_entity(entity)
    prompt = f"""We have the following knowledge about '{entity}':
{known_facts}

Here's a BFO-related question about '{entity}': 
"{question}"

Answer succinctly in a single statement (like "Entity is a X" or "Entity verb Y").
Try to handle negation if appropriate, using 'not' or 'no' if needed.
"""
    resp = ask_ollama(prompt)
    return resp

clarified_entities = set()

def maybe_clarify_entity(entity):
    e_lower = entity.lower()
    if e_lower in clarified_entities:
        return
    clarified_entities.add(e_lower)
    
    qresp = generate_clarification_questions(entity)
    if qresp.startswith("[ERROR from Ollama]"):
        print(qresp)
        return
    
    questions = parse_ollama_questions(qresp)
    if not questions:
        return
    
    print(f"Ollama has {len(questions)} question(s) about '{entity}':")
    for idx, q in enumerate(questions, start=1):
        print(f"{idx}. {q}")
        if AUTO_MODE:
            print("(Auto mode) Generating system answer...\n")
            answer = auto_answer_question(entity, q)
            print(f"System's answer: {answer}")
            logic = process_statement(answer)
            if logic:
                print(f"Translated to logic: {logic}\n")
            else:
                print("[No parseable statement recognized]\n")
        else:
            ans = input("Your answer (or Enter to skip): ").strip()
            if ans.lower() in ["yes","no"]:
                print("Skipping short yes/no. Rephrase in a full statement if needed.\n")
                continue
            if ans:
                logic = process_statement(ans)
                if logic:
                    print(f"Translated to logic: {logic}\n")
                else:
                    print("[No parseable statement recognized]\n")

def main():
    global AUTO_MODE
    load_knowledge()
    generate_owl()
    
    print("=== BFO Ontology + Ollama + Persistent + Automatic Demo ===")
    print("You can enable auto mode by typing 'auto on', or disable by 'auto off'.")
    print("When auto mode is on, knowledge is stored in auto_knowledge.json & auto_ontology.owl.")
    print("When off, we store in knowledge.json & ontology.owl.")
    print("Enter statements (e.g. 'Car is a vehicle'), or queries '? Car', or 'ollama <Entity>'.")
    print(" - 'logic?' => view logic statements.")
    print(" - 'owl?' => display current OWL file.")
    print(" - 'exit' or 'quit' => stop.\n")
    
    while True:
        try:
            user_input = input("> ").strip()
        except KeyboardInterrupt:
            print("\n[Interrupted]")
            sys.exit(0)
        
        if user_input.lower() in ["exit","quit"]:
            print("Goodbye!")
            break
        
        if user_input.lower() == "auto on":
            AUTO_MODE = True
            print("=== Switched to AUTO MODE ===")
            print(f"Now using {AUTO_JSON_FILENAME} and {AUTO_OWL_FILENAME}.")
            load_knowledge()
            generate_owl()
            continue
        
        if user_input.lower() == "auto off":
            AUTO_MODE = False
            print("=== Switched to GUIDED MODE ===")
            print(f"Now using {GUIDED_JSON_FILENAME} and {GUIDED_OWL_FILENAME}.")
            load_knowledge()
            generate_owl()
            continue
        
        if user_input.lower() == "logic?":
            if not logic_history:
                print("No logic statements recorded yet.\n")
            else:
                print("=== Logic Statements Recorded ===")
                for i, stmt in enumerate(logic_history, start=1):
                    print(f"{i}. {stmt}")
                print()
            continue
        
        if user_input.lower() == "owl?":
            f_owl = current_owl_filename()
            if not os.path.exists(f_owl):
                print(f"[No OWL file found: {f_owl}]\n")
            else:
                print(f"=== Contents of {f_owl} ===\n")
                with open(f_owl, "r", encoding="utf-8") as f:
                    contents = f.read()
                print(contents)
                print("=== End of OWL File ===\n")
            continue
        
        if user_input.startswith("?"):
            ent = user_input[1:].strip()
            info = query_entity(ent)
            print(info + "\n")
            continue
        
        if user_input.lower().startswith("ollama "):
            parts = user_input.split(maxsplit=1)
            if len(parts) == 2:
                ent = parts[1].strip()
                print(f"Asking Ollama for clarifications about '{ent}'...\n")
                qresp = generate_clarification_questions(ent)
                if qresp.startswith("[ERROR from Ollama]"):
                    print(qresp)
                else:
                    questions = parse_ollama_questions(qresp)
                    if not questions:
                        print("No questions found.\n")
                    else:
                        print(f"Ollama has {len(questions)} question(s) about '{ent}':")
                        for idx, q in enumerate(questions, start=1):
                            print(f"{idx}. {q}")
                            if AUTO_MODE:
                                print("(Auto mode) Generating system answer...\n")
                                answer = auto_answer_question(ent, q)
                                print(f"System's answer: {answer}")
                                logic = process_statement(answer)
                                if logic:
                                    print(f"Translated to logic: {logic}\n")
                                else:
                                    print("[No parseable statement recognized]\n")
                            else:
                                ans = input("Your answer (or Enter to skip): ").strip()
                                if ans.lower() in ["yes","no"]:
                                    print("Skipping short yes/no.\n")
                                    continue
                                if ans:
                                    logic = process_statement(ans)
                                    if logic:
                                        print(f"Translated to logic: {logic}\n")
                                    else:
                                        print("[No parseable statement recognized]\n")
            else:
                print("[Usage: ollama <Entity>]\n")
            continue
        
        # otherwise treat as statement
        logic = process_statement(user_input)
        if logic is None:
            print("[Unrecognized or query syntax.]\n")
        else:
            print(f"Translated to logic: {logic}\n")

if __name__ == "__main__":
    main()
