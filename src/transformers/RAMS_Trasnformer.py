import re
from .Transformer import Transformer
from tqdm import tqdm
from ..utils import utilities


# todo add word's text in argument
class RamsTransformer(Transformer):

    def __init__(self, rams_path, stanford_core_path):
        super().__init__(stanford_core_path)
        print("rams-transformer intialization")
        self.id_base = "RAMS-instance-"
        self.rams_path = rams_path
        self.origin = "RAMS"

    def transform(self):
        new_instances = []
        i = -1
        rams_jsons = utilities.read_jsonlines(self.rams_path)
        for instance in tqdm(rams_jsons):
            i += 1
            new_instance_id = self.id_base + str(i) + "-" + instance['doc_key']
            no_of_sentences = len(instance['sentences'])

            sentences = []
            next_start = 0
            for s in instance['sentences']:
                start = next_start
                end = start + len(s)
                next_start = end
                text = ' '.join(s)
                sentences.append({'start': start, 'end': end, 'text': text})

            text_sentence = ' '.join([s['text'] for s in sentences])

            parsing = self.simple_parsing(text_sentence)
            lemma = parsing[2]
            words = parsing[0]
            pos_tags = parsing[1]
            conll_head = parsing[3]
            entity_types = parsing[4]

            # chunking
            chunks = [self.chunking(words[s['start']: s['end']], pos_tags[s['start']: s['end']]) for s in sentences]

            # zip(*list) unzips a list o tuples
            annotations = list(zip(*[self.coreNLP_annotation(s['text']) for s in sentences]))
            penn_treebanks = annotations[0]
            dependency_parsing = annotations[1]


            entities = []
            for j, entity in enumerate(instance['ent_spans']):
                start = entity[0]
                end = entity[1] + 1
                text = ' '.join(words[start: end])
                entity_id = new_instance_id + "-entity-" + str(j)
                entity_type = utilities.most_frequent(entity_types[start: end])
                new_entity = {'start': start, 'end': end, 'text': text, 'entity-id': entity_id,
                              'entity-type': entity_type, 'detailed-entity-type': ""}
                entities.append(new_entity)

            if len(instance['evt_triggers']) > 1:
                print("ERROR: More triggers than expected")

            trigger_start = instance['evt_triggers'][0][0]
            trigger_end = instance['evt_triggers'][0][1] + 1
            trigger_text = ' '.join(words[trigger_start: trigger_end]).lower()
            trigger = {'start': trigger_start, 'end': trigger_end, 'text': trigger_text}

            event_type = instance['evt_triggers'][0][2][0][0]

            events_triples = []
            arguments = []

            for triple in instance['gold_evt_links']:
                arg_start = triple[1][0]
                arg_end = triple[1][1] + 1
                entity_type = utilities.most_frequent(entity_types[arg_start: arg_end])
                arg_role = re.split("\d", triple[2])[-1]
                argument = {'start': arg_start, 'end': arg_end, 'role': arg_role, 'entity-type': entity_type,
                            'detailed-entity-type': ""}
                arguments.append(argument)

            events_triples.append({'arguments': arguments, 'trigger': trigger, 'event-type': event_type})

            new_instance = {
                'origin': self.origin,
                'id': new_instance_id,
                'no-of-sentences': no_of_sentences,
                'sentences': sentences,
                'text': text_sentence,
                'words': words,
                'lemma': lemma,
                'pos-tags': pos_tags,
                'head': conll_head,
                'golden-entity-mentions': entities,
                'golden-event-mentions': events_triples,
                'penn-treebank': penn_treebanks,
                "dependency-parsing": dependency_parsing,
                'chunks': chunks
            }
            new_instances.append(new_instance)
        return new_instances

