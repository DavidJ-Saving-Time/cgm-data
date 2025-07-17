from collections import defaultdict
from pymongo import MongoClient
from pprint import pprint
import os

client = MongoClient(os.environ["MONGODBKEY"])
db     = client["nightscout"]

def infer_schema(db, sample_size=100):
    schema = {}
    for coll_name in db.list_collection_names():
        coll = db[coll_name]
        field_types = defaultdict(set)

        # sample up to sample_size docs
        for doc in coll.find({}, limit=sample_size):
            for k, v in doc.items():
                field_types[k].add(type(v).__name__)

        # convert sets to sorted lists
        schema[coll_name] = {k: sorted(list(types)) for k, types in field_types.items()}

    return schema

if __name__ == "__main__":
    schema = infer_schema(db, sample_size=200)
    pprint(schema)
