"""
Use this script to generate IOB-formatted training data.
For the moment the input will be the outfiles from the postprocessing.
In the future, a complete pipeline from project folder to iob might be implemented.

This script will also handle the resolution of a file that was annotated by 2 users.
We handle it with the following solution:
Ranking: Requires additionally a list of the user names and will take the first-named users file over latter named users files.

The user may change the ratios of training data to validation and testing data. If unchanged, a 8-1-1 ratio is default.
If all data in one file is wanted, just set the chances 1, 0, 0 and everything will be put into train.txt.
Mind you the script uses randomness to decide where to put any respective document, so the split will not be an exact 8-1-1
and may especially vary if the dataset is small.

For more order examples, check to_iob.py in the transformation subfolder.
"""

import json
import csv
import os
from glob import glob
import pathlib
from transformation.to_exp import process_document


### SETTINGS ###
INFOLDER = "outfolder_24_04_30/"  # The folder where all the standoff xml are
OUTFOLDER = "trainingdata_exp/24_04_30/full"
CONSISTENT_DATA = "consistent_data_24_04_03.json"
tags_to_include = ["date", "per", "loc", "money", "gpe", "org"]
ORDER = {
            "tags": {
                #"List": {
                #    "tag": "lst",
                #    "entity_types": {"include": [], "prefix": "ent"},
                #    "subtype": {"include": [], "prefix": "stype"}, 
                #},
                "Reference": {
                    "tag": "ref",
                    #"mention_type": {"include": [], "prefix": "men"}, 
                    "entity_type": {"include": [], "prefix": "ent"}, 
                    #"mention_subtype": {"include": [], "prefix": "submen"},
                    #"numerus": {"include": [], "prefix": "num"},
                    #"specificity": {"include": [], "prefix": "spec"},
                    }, 
                "Attribute": {
                    "tag": "att",
                    #"mention_type": {"include": [], "prefix": "men"}, 
                    "entity_type": {"include": [], "prefix": "ent"}, 
                    #"mention_subtype": {"include": [], "prefix": "submen"},
                    #"numerus": {"include": [], "prefix": "num"},
                    #"specificity": {"include": [], "prefix": "spec"},
                    }, 
                "Value": {"tag": "val", "value_type": {"include": [], "prefix": "val"}}, 
                "Descriptor": {"tag": "desc", "desc_type": {"include": [], "prefix": "desc"}}
            },
            "merge_overlapping_desc_tags": False,  # if a desc tag covers the same span as another tag (Reference or Attribute usually), we put the desc tag as a mention subtype info to the entity annotation instead.
            "depth_anno": None,  # annotate the depth, options: "None", "Binary" (doc vs ent level), "Ordinal"
            "tag_anno": None, # annotate the parent tag, options: "None" or list of attributes that should be annotated (e.g. ["entity_type"])  
            "tag_granularity": 2,  # how granular should the label info be (TODO: Move to the instructions per tag type)
            "require_parent": None # only add a span to the annotations if the parent of that span fits one or more requirements fits a key-value pair in the dict or give "doc" if flat annotations are wanted, "doc" may be included as a key in the dict so base spans are also included, None to disable filter TODO: Explain this better. It's now a list of OR-conditions
        }

if __name__ == "__main__":
    pathlib.Path(OUTFOLDER).mkdir(parents=True, exist_ok=True) 

    infiles = sorted(glob(INFOLDER + "*.xml"))

    trainfile = open(os.path.join(OUTFOLDER, "train.txt"), mode="w", encoding="utf8")
    devfile = open(os.path.join(OUTFOLDER, "dev.txt"), mode="w", encoding="utf8")
    testfile = open(os.path.join(OUTFOLDER, "test.txt"), mode="w", encoding="utf8")

    trainwriter = csv.writer(trainfile, delimiter="\t", lineterminator="\n")
    devwriter = csv.writer(devfile, delimiter="\t", lineterminator="\n")
    testwriter = csv.writer(testfile, delimiter="\t", lineterminator="\n")

    # for each file
    for infile in infiles:
        print(f"Processing {infile}...")
        annotations = process_document(infile, ORDER)

        with open(CONSISTENT_DATA, mode="r", encoding="utf8") as cons:
            consistent_data = json.load(cons)

        basename = os.path.basename(infile)
        
        if basename in consistent_data["test"]:
            writer = testwriter
        elif basename in consistent_data["dev"]:
            writer = devwriter
        elif basename in consistent_data["train"]:
            writer = trainwriter
        else:
            print(f"WARNING! {infile} was not found in consistent training registry!")
            continue

        # write the filename as a comment (flair ignores these in ColumnCorpus)
        writer.writerow([f"# {os.path.basename(infile)}"])
        for anno in annotations:
            for token, tag in anno:
                writer.writerow([token] + [tag])
            writer.writerow([])

    trainfile.close()
    devfile.close()
    testfile.close()
