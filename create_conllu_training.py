import json
import csv
import os
from glob import glob
from transformation.to_conllu import process_document, construct_metadata, write_outstring

### SETTINGS ###
INFOLDER = "outfiles/"  # The folder where all the standoff xml are
USER_RANKING = ["kfuchs", "admin", "bhitz"]  # left is preferred
OUTFOLDER = "trainingdata_conllu/A/"
CONFIG = {
            "mode": "heads",
            "filter": {
            },
            "tags": {
                "entity_type": []
            },
            "depth": 1,
            "tag_granularity": 1
        }


if __name__ == "__main__":
    infiles = glob(INFOLDER + "*.xml")

    trainfile = open(OUTFOLDER + "train.txt", mode="w", encoding="utf8")
    trainfile.write("# global.columns = id form ner\n")
    devfile = open(OUTFOLDER + "dev.txt", mode="w", encoding="utf8")
    devfile.write("# global.columns = id form ner\n")
    testfile = open(OUTFOLDER + "test.txt", mode="w", encoding="utf8")
    testfile.write("# global.columns = id form ner\n")
    
    # for each file
    for i, infile in enumerate(infiles):
        print(f"Processing {infile}...")
        token_list, annotations = process_document(infile, CONFIG)
        metadata = construct_metadata(infile, i)

        with open("consistent_data.json", mode="r", encoding="utf8") as cons:
            consistent_data = json.load(cons)

        basename = os.path.basename(infile)
        
        if basename in consistent_data["test"]:
            writer = testfile
        elif basename in consistent_data["dev"]:
            writer = devfile
        elif basename in consistent_data["train"]:
            writer = trainfile
        else:
            print(f"WARNING! {infile} was not found in consistent training registry!")
            continue

        writer.write(write_outstring(token_list, annotations, metadata))
        writer.write("\n")

    trainfile.close()
    devfile.close()
    testfile.close()
