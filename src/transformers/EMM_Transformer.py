from .Transformer import Transformer
from tqdm import tqdm
from ..utils import utilities
from ..conf.Constants import Keys
import re
import os
import time


class EmmTransformer(Transformer):

    def __init__(self, edd_path, model):
        super().__init__(model)
        self.log.info("Initializing EmmTransformer")
        self.id_base = "EMM-instance-"
        self.path = edd_path
        self.origin = "EMM"

    # accumulate and store all the roles/eventTypes
    def export_types(self, roles_path, event_paths):
        events = set()
        roles = set()

        for file in os.listdir(self.path):
            json_file = self.path + file
            edd_jsons = utilities.read_json(json_file)
            for instance in edd_jsons:
                instance_result = instance['completions'][0]['result']

                for i, result in enumerate(instance_result):
                    value = result['value']
                    if result['from_name'] == "ev_type":
                        event = value['choices'][0]
                        event = re.sub(r"\s+", ".", event.lower())
                        events.add(event)
                    elif value['labels'][0] != 'Event Trigger':
                        role = value['labels'][0]
                        role = re.sub(r"\s+", ".", role.lower())
                        roles.add(role)

        utilities.write_iterable(roles_path, roles)
        utilities.write_iterable(event_paths, events)

    def transform(self, output_path):
        self.log.info("Starts transformation of EMM")
        start_time = time.monotonic()
        i = 0
        if os.path.isdir(self.path):
            for file in os.listdir(self.path):
                json_file = os.path.join(self.path, file)
                self.log.info("Transforming " + file)
                self.transform_json(json_file, output_path, i)
                i += 1
        else:
            self.transform_json(self.path, output_path, i)
        self.log.info("Transformation of EMM completed in " + str(round(time.monotonic() - start_time, 3)) + "sec")

    def transform_json(self, json_file, output_path, i):
        new_instances = []
        edd_jsons = utilities.read_json(json_file)
        for instance in tqdm(edd_jsons):
            instance_data = instance['data']
            new_instance_id = self.id_base + "-" + instance_data['filename'] + str(i)
            initial_text = instance_data['text']
            text = re.sub(r'(?<!\.)\n', ' . ', instance_data['text']).replace("\n", "")
            try:
                parsing = self.advanced_parsing(text)
            except ValueError:
                continue
            text_sentence = parsing[Keys.TEXT.value]
            sentences = parsing[Keys.SENTENCES.value]
            words = parsing[Keys.WORDS.value]
            lemma = parsing[Keys.LEMMA.value]
            pos_tags = parsing[Keys.POS_TAGS.value]
            ner = parsing[Keys.NER.value]

            # sentence centric
            penn_treebanks = parsing[Keys.PENN_TREEBANK.value]
            dependency_parsing = parsing[Keys.DEPENDENCY_PARSING.value]
            chunks = parsing[Keys.CHUNKS.value]
            no_of_sentences = len(sentences)

            event_type = None
            trigger = None
            arguments = []
            entities = []
            instance_result = instance['completions'][0]['result']
            for j, result in enumerate(instance_result):
                if result['from_name'] == "ev_type":
                    event_type = result['value']['choices'][0].lower()
                    event_type = self.events_mapper[event_type]
                else:
                    value = result['value']
                    entity_text = value['text']
                    entity_char_start = value['start']
                    entity_char_end = value['end']

                    indices = self.search_text_in_list(entity_char_start, entity_char_end, initial_text, entity_text, words)
                    entity_start = indices[Keys.START.value]
                    entity_end = indices[Keys.END.value]
                    if not (entity_end and entity_start):
                        continue
                    role = value['labels'][0].lower()
                    if role == 'event trigger':
                        trigger = {Keys.START.value: entity_start,
                                   Keys.END.value: entity_end,
                                   Keys.TEXT.value: entity_text}
                    else:
                        entity_id = new_instance_id + "-" + str(j)
                        types = set(ner[entity_start: entity_end])
                        entity_type = "O"
                        if len(types) > 0:
                            entity_type = utilities.most_frequent(ner[entity_start: entity_end])

                        entity = {Keys.START.value: entity_start, Keys.END.value: entity_end,
                                  Keys.TEXT.value: entity_text, Keys.ENTITY_ID.value: entity_id,
                                  Keys.ENTITY_TYPE.value: entity_type, Keys.EXISTING_ENTITY_TYPE.value: ""}
                        entities.append(entity)

                        role = self.roles_mapper[role] if role in self.roles_mapper else role
                        new_argument = {Keys.START.value: entity_start,
                                        Keys.END.value: entity_end,
                                        Keys.TEXT.value: entity_text,
                                        Keys.ENTITY_TYPE.value: entity_type,
                                        Keys.EXISTING_ENTITY_TYPE.value: "",
                                        Keys.ROLE.value: role}
                        arguments.append(new_argument)

            if not (event_type and trigger):
                self.log.error("")
                if not event_type:
                    self.log.error("An empty Event Type was detected")
                else:
                    self.log.error("An empty Trigger was detected")
                continue
            events = [{'arguments': arguments, 'trigger': trigger, 'event-type': event_type}]
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
            if len(new_instances) == self.batch_size:
                utilities.write_jsons(new_instances, output_path)
                new_instances = []
        utilities.write_jsons(new_instances, output_path)

    def search_text_in_list(self, start_, end_, whole_text, text, parsed_words):
        try:
            parsed_words = [re.sub("-", " ", pw).strip(",. \n\'\"-") for pw in parsed_words]
            text_ = re.sub(r"-|\.|\'|\"", " ", text).replace("(", " LRB ").replace(")", " RRB ")
            text_ = re.sub(r"(\d\d)pm", r"\1 pm", text_)
            text_ = re.sub(r"(\d\d)am", r"\1 pm", text_)
            parsed = list(filter(lambda name: name.strip(",. \n\'\"-"), [token.text for token in self.nlp(text_)]))

            all_tokens = [token.strip(",. \n\'\"-") for token in whole_text.split()]
            entity_text = whole_text[start_:end_].replace("(", " LRB ").replace(")", " RRB ").split()

            try:
                # find first word in the whole text
                first_word = entity_text[0]
                # find its index
                initial_start = all_tokens.index(first_word)
                # give some buffer
                initial_start = initial_start - 2 if initial_start > 2 else 0
            except ValueError:
                initial_start = 0

            # get the word in the parsed document - this is the one we seek
            parsed_first_word = parsed[0]
            # find the starting index in the parsed list of words
            start = parsed_words[initial_start:].index(parsed_first_word) + initial_start

            try:
                # same for last word
                last_word = entity_text[-1]
                initial_end = all_tokens.index(last_word)
                initial_end = initial_end + 2 if initial_end > len(parsed_words)-3 else len(parsed_words) - 1
            except ValueError:
                initial_end = -1

            parsed_last_word = parsed[-1]
            end = parsed_words[initial_start:initial_end].index(parsed_last_word) + initial_start

            return {Keys.START.value: start, Keys.END.value: end+1}
        except ValueError as ve:
            self.log.error("")
            self.log.error("Not able to find '" + text + "' in the list of words")
            return {Keys.START.value: None, Keys.END.value: None}
