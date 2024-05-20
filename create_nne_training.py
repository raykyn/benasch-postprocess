import os
from collections import Counter
from glob import glob
import json
from transformation.to_nne import process_document
import pathlib

### SETTINGS ###
INFOLDER = "outfolder_24_04_30/"  # The folder where all the standoff xml are
OUTFOLDER = "trainingdata_nne/24_04_30/simple_fixed_4"
CONSISTENT_DATA = "persistent_data/persistent_data_24_04_30_4.json"

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
                    "tag": "ref",
                    #"mention_type": {"include": [], "prefix": "men"}, 
                    "entity_type": {"include": [], "prefix": "ent"}, 
                    #"mention_subtype": {"include": [], "prefix": "submen"},
                    #"numerus": {"include": [], "prefix": "num"},
                    #"specificity": {"include": [], "prefix": "spec"},
                    }, 
                "Value": {"tag": "val", "value_type": {"include": [], "prefix": "val"}}, 
                #"Descriptor": {"tag": "desc", "desc_type": {"include": [], "prefix": "desc"}}
            },
            #"merge_overlapping_desc_tags": False,  # if a desc tag covers the same span as another tag (Reference or Attribute usually), we put the desc tag as a mention subtype info to the entity annotation instead.
            #"depth_anno": None,  # annotate the depth, options: "None", "Binary" (doc vs ent level), "Ordinal"
            #"tag_anno": None, # annotate the parent tag, options: "None" or list of attributes that should be annotated (e.g. ["entity_type"])  
            "tag_granularity": 1,  # how granular should the label info be (TODO: Move to the instructions per tag type)
            #"require_parent": None # only add a span to the annotations if the parent of that span fits one or more requirements fits a key-value pair in the dict or give "doc" if flat annotations are wanted, "doc" may be included as a key in the dict so base spans are also included, None to disable filter TODO: Explain this better. It's now a list of OR-conditions
        }


if __name__ == "__main__":
    pathlib.Path(OUTFOLDER).mkdir(parents=True, exist_ok=True) 

    infiles = glob(INFOLDER + "*.xml")

    trainfile = open(os.path.join(OUTFOLDER, "train.txt"), mode="w", encoding="utf8")
    devfile = open(os.path.join(OUTFOLDER, "dev.txt"), mode="w", encoding="utf8")
    testfile = open(os.path.join(OUTFOLDER, "test.txt"), mode="w", encoding="utf8")

    for infile in infiles:
        print(f"Processing {infile}...")
        text, annotations = process_document(infile, ORDER)

        with open(CONSISTENT_DATA, mode="r", encoding="utf8") as cons:
            consistent_data = json.load(cons)

        basename = os.path.basename(infile)
        
        if basename in consistent_data["test"]:
            writer = testfile
        elif basename in consistent_data["dev"]:
            writer = devfile
        elif basename in consistent_data["train"]:
            writer = trainfile
        else:
            print(f"WARNING! {basename} was not found in consistent training registry!")
            continue

        writer.write(text + "\n")
        writer.write(annotations + "\n")
        writer.write("\n")

    trainfile.close()
    devfile.close()
    testfile.close()
