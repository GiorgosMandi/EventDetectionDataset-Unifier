from .transformers.RAMS_Trasnformer import RamsTransformer
from .transformers.M2E2_Transformer import M2e2Transformer
from .transformers.ACE_Transformer import AceTransformer
from .utils import utilities
import argparse
from os import path

import os

parser = argparse.ArgumentParser(description="Give arguments")
parser.add_argument('-base', metavar='base_path', type=str, help='Path of working folder')
parser.add_argument('-dt', metavar='base_path', type=str, help='witch dataset to transform')

args = parser.parse_args()
os.chdir(args.base)
ACE_dir_path = 'data/ACE'
M2E2_dir_path = 'data/M2E2'
RAMS_dir_path = 'data/RAMS'

core_nlp_path = 'model/stanford-corenlp-full-2018-10-05'
rams_path = RAMS_dir_path + '/rams_100.jsonlines'
m2e2_path = M2E2_dir_path + '/article_0816_filter.json'
ace_path = ACE_dir_path + '/ace.json'

if args.dt == "rams":
    transformer = RamsTransformer(rams_path, core_nlp_path)
    instances = transformer.transform()

elif args.dt == "m2e2":
    transformer = M2e2Transformer(m2e2_path, core_nlp_path)
    instances = transformer.transform()

elif args.dt == "ace":
    transformer = AceTransformer(ace_path, core_nlp_path)

    ace_roles_path = ACE_dir_path + '/ACE_roles.txt'
    ace_roles_mapping_path = ACE_dir_path + '/ACE_roles_mapping.json'

    ace_events_path = ACE_dir_path + '/ACE_events.txt'
    ace_events_mapping_path = ACE_dir_path + '/ACE_events_mapping.json'

    if not path.exists(ace_roles_mapping_path) or not path.exists(ace_events_mapping_path):
        if not path.exists(ace_roles_path) or not path.exists(ace_events_path):
            transformer.export_types(ace_roles_path, ace_events_path)

        roles_mapping = utilities.match_entities(ace_roles_path, RAMS_dir_path + '/RAMS_roles.txt')
        events_mapping = utilities.match_entities(ace_events_path, RAMS_dir_path + '/RAMS_event_types.txt')

        utilities.write_json(roles_mapping, ace_roles_mapping_path)
        utilities.write_json(events_mapping, ace_events_mapping_path)

    # instances = transformer.transform()

elif args.dt == "all":
    rams_transformer = RamsTransformer(rams_path, core_nlp_path)
    rams_instances = rams_transformer.transform()

    m2e2_transformer = M2e2Transformer(m2e2_path, core_nlp_path)
    m2e2_instances = m2e2_transformer.transform()


print("done")
