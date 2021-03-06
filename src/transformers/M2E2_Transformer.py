from tqdm import tqdm
from .Transformer import Transformer
from ..utils import utilities
from ..conf.Constants import Keys
import time


class M2e2Transformer(Transformer):

    def __init__(self, m2e2_path, model, disable_mapping):
        super().__init__(model, disable_mapping)
        self.log.info("Initializing M2e2Transformer")
        self.id_base = "M2E2-instance-"
        self.m2e2_path = m2e2_path
        self.origin = "M2E2"

    def transform(self, output_path):
        """
        Transform dataset into the common schema and store the results
        in the output path. Storing is performed in batches.
        Actions:
            - Parse text and produce text-based features
            - Parse entities and adjust them to the new list of words
            - Parse event triples and adjust them to the new list of words
        :param output_path: output path
        :return:  None
        """
        self.log.info("Starting the transformation of M2E2")
        start_time = time.monotonic()
        i = -1
        new_instances = []

        # read file and iterate over instances
        m2e2_jsons = utilities.read_simple_json(self.m2e2_path)
        print()
        for instance in tqdm(m2e2_jsons):
            i += 1
            new_instance_id = self.id_base + str(i) + "-" + instance['sentence_id']
            text_sentence = instance['sentence']
            try:
                parsing = self.advanced_parsing(text_sentence)
            except ValueError:
                continue
            # extract parsing results
            words = parsing[Keys.WORDS.value]
            lemma = parsing[Keys.LEMMA.value]
            pos_tags = parsing[Keys.POS_TAGS.value]
            ner = parsing[Keys.NER.value]
            sentences = parsing[Keys.SENTENCES.value]
            # sentence centric
            penn_treebanks = parsing[Keys.PENN_TREEBANK.value]
            dependency_parsing = parsing[Keys.PENN_TREEBANK.value]
            chunks = parsing[Keys.CHUNKS.value]
            no_of_sentences = len(sentences)

            # parse entities
            text_to_entity = {}
            entities = []
            successfully = True
            for j, entity in enumerate(instance['golden-entity-mentions']):
                entity_id = new_instance_id + "-entity-" + str(j)
                existing_ner = entity['entity-type']

                entity_text = ' '.join(instance['words'][entity['start']:entity['end']])
                indices = self.search_text_in_list(entity['start'], entity['end'], entity_text, words)
                entity_start = indices[Keys.START.value]
                entity_end = indices[Keys.END.value]
                if entity_start is None or entity_end is None:
                    successfully = False
                    continue
                entity_text = ' '.join(words[entity_start: entity_end])
                new_ner = utilities.most_frequent(ner[entity_start: entity_end])
                new_entity = {Keys.ENTITY_ID.value: entity_id,
                              Keys.START.value: entity_start,
                              Keys.END.value: entity_end,
                              Keys.TEXT.value: entity_text,
                              Keys.ENTITY_TYPE.value: new_ner,
                              Keys.EXISTING_ENTITY_TYPE.value: existing_ner
                              }
                entities.append(new_entity)
                text_in_dataset = ' '.join(instance['words'][entity['start']: entity['end']])
                text_to_entity[text_in_dataset] = new_entity

            if not successfully:
                self.log.warning("Failed to parse entity, skipping instance")
                continue

            # parse events
            events = []
            if len(instance['golden-event-mentions']) > 0:
                for event in instance['golden-event-mentions']:
                    event_type = self.get_event_type(event['event_type'])
                    event['event_type'] = event_type
                    arguments = []
                    for arg in event['arguments']:
                        role = arg['role'].lower()
                        role = self.roles_mapper[role] if role in self.roles_mapper else role

                        # there are also inconsistencies between arguments' text and entities' text
                        text_in_dataset = ' '.join(instance['words'][arg['start']: arg['end']])
                        corresponding_entity = text_to_entity[text_in_dataset]
                        arguments.append({Keys.START.value: corresponding_entity[Keys.START.value],
                                          Keys.END.value: corresponding_entity[Keys.END.value],
                                          Keys.TEXT.value: corresponding_entity[Keys.TEXT.value],
                                          Keys.ROLE.value: role,
                                          Keys.ENTITY_TYPE.value: corresponding_entity[Keys.ENTITY_TYPE.value],
                                          Keys.EXISTING_ENTITY_TYPE.value: corresponding_entity[Keys.EXISTING_ENTITY_TYPE.value]
                                          })

                    trigger_text = ' '.join(instance['words'][event['trigger']['start']:event['trigger']['end']])
                    indices = self.search_text_in_list(event['trigger']['start'], event['trigger']['end'], trigger_text, words)
                    trigger_start = indices[Keys.START.value]
                    trigger_end = indices[Keys.END.value]
                    if trigger_start is None or trigger_end is None:
                        successfully = False
                        self.log.warning("Failed to parse trigger, skipping instance")
                        continue
                    trigger_text = ' '.join(words[trigger_start: trigger_end])
                    trigger = {
                        Keys.TEXT.value: trigger_text,
                        Keys.START.value: trigger_start,
                        Keys.END.value: trigger_end
                    }

                    events.append({Keys.ARGUMENTS.value: arguments,
                                   Keys.TRIGGER.value: trigger,
                                   Keys.EVENT_TYPE.value: event_type})
            if not successfully:
                continue
            # create new instance
            new_instance = {
                Keys.ORIGIN.value: self.origin,
                Keys.ID.value: new_instance_id,
                Keys.NO_SENTENCES.value: no_of_sentences,
                Keys.SENTENCES.value: sentences,
                Keys.TEXT.value: text_sentence,
                Keys.WORDS.value: words,
                Keys.LEMMA.value: lemma,
                Keys.POS_TAGS.value: pos_tags,
                Keys.NER.value: ner,
                Keys.ENTITIES_MENTIONED.value: entities,
                Keys.EVENTS_MENTIONED.value: events,
                Keys.PENN_TREEBANK.value: penn_treebanks,
                Keys.DEPENDENCY_PARSING.value: dependency_parsing,
                Keys.CHUNKS.value: chunks
            }
            new_instances.append(new_instance)

            # write results if we reached batch size
            if len(new_instances) == self.batch_size:
                utilities.write_jsons(new_instances, output_path)
                new_instances = []
        utilities.write_jsons(new_instances, output_path)
        self.log.info("Transformation of M2E2 completed in " + str(round(time.monotonic() - start_time, 3)) + "sec")
