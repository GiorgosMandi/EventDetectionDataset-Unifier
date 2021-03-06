from .utils import utilities
from .conf.Constants import Keys
import argparse
import logging
import sys
from tqdm import tqdm
import os

log = logging.getLogger("VALIDATOR")
log.setLevel(logging.DEBUG)
consoleOUT = logging.StreamHandler(sys.stdout)
consoleOUT.setLevel(logging.DEBUG)
formatter = logging.Formatter('\n%(asctime)s - %(name)s - %(levelname)s - %(message)s')
consoleOUT.setFormatter(formatter)
consoleOUT.terminator = ""
log.addHandler(consoleOUT)

log_root = logging.getLogger()
consoleER = logging.StreamHandler(sys.stdout)
consoleER.setLevel(logging.FATAL)
consoleER.setFormatter(formatter)
consoleER.terminator = ""
log_root.addHandler(consoleER)


class ValidateTransformation:

    def test_pointers(self, text, start, end, words):
        try:
            new_text = ' '.join(words[start:end])
            if utilities.string_similarity(new_text, text) < 0.9:
                return False
            return True
        except IndexError:
            log.error("Index ERROR: Text'" + text + "' not found in the list of words")
            return False

    def validate_parsing(self, parsing_dict, detailed=True):
        try:
            # test all fields exists
            if detailed:
                assert(Keys.SENTENCES.value in parsing_dict and
                       Keys.TEXT.value in parsing_dict and
                       Keys.WORDS.value in parsing_dict and
                       Keys.LEMMA.value in parsing_dict and
                       Keys.POS_TAGS.value in parsing_dict and
                       Keys.NER.value in parsing_dict and
                       Keys.PENN_TREEBANK.value in parsing_dict and
                       Keys.DEPENDENCY_PARSING.value in parsing_dict and
                       Keys.CHUNKS.value in parsing_dict)

                # test word-centric features
                assert(len(parsing_dict[Keys.WORDS.value]) == len(parsing_dict[Keys.LEMMA.value]) and
                       len(parsing_dict[Keys.WORDS.value]) == len(parsing_dict[Keys.POS_TAGS.value]) and
                       len(parsing_dict[Keys.WORDS.value]) == len(parsing_dict[Keys.NER.value]))

                # test sentences-centric features
                assert (parsing_dict[Keys.NO_SENTENCES.value] == len(parsing_dict[Keys.SENTENCES.value]) and
                        parsing_dict[Keys.NO_SENTENCES.value] == len(parsing_dict[Keys.PENN_TREEBANK.value]) and
                        parsing_dict[Keys.NO_SENTENCES.value] == len(parsing_dict[Keys.CHUNKS.value]) and
                        parsing_dict[Keys.NO_SENTENCES.value] == len(parsing_dict[Keys.DEPENDENCY_PARSING.value]))

            # test chunks
            assert(len(parsing_dict[Keys.WORDS.value]) == len([c for ch in parsing_dict[Keys.CHUNKS.value] for c in ch]))

            words = parsing_dict[Keys.WORDS.value]

            # test sentences
            for sentence in parsing_dict[Keys.SENTENCES.value]:
                assert (self.test_pointers(sentence[Keys.TEXT.value],
                                           sentence[Keys.START.value],
                                           sentence[Keys.END.value],
                                           words))

            # test entities
            if detailed:
                for entity in parsing_dict[Keys.ENTITIES_MENTIONED.value]:
                    assert(self.test_pointers(entity[Keys.TEXT.value],
                                              entity[Keys.START.value],
                                              entity[Keys.END.value],
                                              words))

            # test events
            for event in parsing_dict[Keys.EVENTS_MENTIONED.value]:
                # test trigger
                assert(self.test_pointers(event[Keys.TRIGGER.value][Keys.TEXT.value],
                                          event[Keys.TRIGGER.value][Keys.START.value],
                                          event[Keys.TRIGGER.value][Keys.END.value],
                                          words))
                # test arguments
                for arg in event[Keys.ARGUMENTS.value]:
                    assert(self.test_pointers(arg[Keys.TEXT.value],
                                              arg[Keys.START.value],
                                              arg[Keys.END.value],
                                              words))
            return True
        except AssertionError:
            log.error("Assertion ERROR json with id: '" + parsing_dict[Keys.ID.value] + "'")
            return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Give arguments")
    parser.add_argument('-input', metavar='--input', type=str, help='Path to the json to validate', required=True)
    parser.add_argument('-disableDetailed', action='store_true', help='Disable event type mapping matching ')

    args = parser.parse_args()
    disableDetailed = args.disableDetailed
    if not os.path.exists(args.input):
        log.error("Path '" + args.input + "' does not exist")
        exit(1)

    jsons = utilities.read_jsonlines(args.input)
    validator = ValidateTransformation()
    log.info("Starting validation")
    successful = True
    for json in tqdm(jsons):
        successful = successful and validator.validate_parsing(json, not disableDetailed)
        if not successful:
            break
    if successful:
        log.info("Validation was completed Successfully")
        log.info("Document is correct")
    else:
        log.error("Document contains mistakes")
        log.error("Validation Failed")
    print()
