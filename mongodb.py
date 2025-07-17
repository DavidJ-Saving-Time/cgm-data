from collections import defaultdict
from pymongo import MongoClient
from pprint import pprint
import os

client = MongoClient(os.environ["MONGODBKEY"])
db     = client["nightscout"]
