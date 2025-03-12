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
from transformation.to_exp_evts import process_document


### SETTINGS ###
INFOLDER = "./data/std_xml/24_07_24/"  # The folder where all the standoff xml are
OUTFOLDER = "./data/rec_training/ner_rec/24_07_24_role_detect_fixed"
#OUTFOLDER = "./data/rec_training/ner_rec/ner_rec_24_07_01"
CONSISTENT_DATA = "./data/training_data_json/ner_rec/only_evts_24_07_01.json"
#CONSISTENT_DATA = "./data/training_data_json/ner_rec/ner_rec_24_07_01.json"
ORDER = json.load(open("./data/transformation_configs/ner_nested/ner_nested_plus_roles.json", mode="r", encoding="utf8"))

if __name__ == "__main__":
    pathlib.Path(OUTFOLDER).mkdir(parents=True, exist_ok=True) 

    infiles = sorted(glob(INFOLDER + "*.xml"))

    trainfile = open(os.path.join(OUTFOLDER, "train.txt"), mode="w", encoding="utf8")
    devfile = open(os.path.join(OUTFOLDER, "dev.txt"), mode="w", encoding="utf8")
    testfile = open(os.path.join(OUTFOLDER, "test.txt"), mode="w", encoding="utf8")

    #trainwriter = csv.writer(trainfile, delimiter="\t", lineterminator="\n")
    #devwriter = csv.writer(devfile, delimiter="\t", lineterminator="\n")
    #testwriter = csv.writer(testfile, delimiter="\t", lineterminator="\n")

    with open(CONSISTENT_DATA, mode="r", encoding="utf8") as cons:
        consistent_data = json.load(cons)

    # for each file
    for infile in infiles:
        print(f"Processing {infile}...")
        outstring = process_document(infile, ORDER)
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

        # write the filename as a comment (flair ignores these in ColumnCorpus)
        if outstring:
            writer.write(f"# {os.path.basename(infile)}\n")
            writer.write(outstring)
            writer.write("\n")
        """
        for anno in annotations:
            for token, tag in anno:
                writer.writerow([token] + [tag])
            writer.writerow([])
        """

    trainfile.close()
    devfile.close()
    testfile.close()
