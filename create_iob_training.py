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

import csv
import os
from collections import defaultdict, Counter
from glob import glob
import random
from transformation.to_iob import process_document


### SETTINGS ###
INFOLDER = "outfiles/"  # The folder where all the standoff xml are
USER_RANKING = ["kfuchs", "admin", "bhitz"]  # left is preferred
DATA_RATIO = [0.8, 0.1, 0.1]  # Train, Dev, Test
OUTFOLDER = "trainingdata/"
ORDERS = [
        {
            "mode": "heads",
            "filter": {
                "mention_type": ["nam"],
            },
            "tags": {
                "entity_type|desc_type|value_type": []
            },
            "depth": 1
        },
    ]

"""
This order currently doesn't work, needs a more elaborate filtering algorithm
{
    "mode": "full",
    "filter_strict": {
        "mention_type": ["nom"],
    },
    "filter": {
        "mention_subtype": ["occ", "org-job"],
    },
    "tags": {
        "entity_type|desc_type|value_type": []
    },
    "depth": 1
},
"""


def sort_out_duplicates(infiles):
    filedict = {}
    for infile in infiles:
        basename = os.path.basename(infile)
        basename = basename.split("_")
        username, basename = basename[0], "_".join(basename[1:])
        if basename in filedict:
            filedict[basename][0].append(username)
        else:
             filedict[basename] = ([username], infile)
        
    
    for entry in filedict:
        if len(filedict[entry][0]) > 1:
            possible_users = ", ".join(filedict[entry][0])
            print(f"Resolving file {entry} between users {possible_users}.")
            for username in USER_RANKING:
                if username in filedict[entry][0]:
                    print(filedict[entry])
                    filedict[entry] = ([username], filedict[entry][1])
                    break
            print(f"User {filedict[entry][0][0]} was chosen.")
    
    return filedict


def check_for_duplicates(infiles):
    # this is a bit project specific and only relevant if you use the same
    # naming system, but you can of course fit this to your needs.
    infile_filenames = ["_".join(f.split("_")[-3:]) for f in infiles]
    counter = Counter(infile_filenames)
    duplicates = [f for f, c in counter.most_common() if c > 1]
    if duplicates:
        print("Duplicates found!")
        print(duplicates)



if __name__ == "__main__":
    infiles = glob(INFOLDER + "*.xml")

    # sort out duplicates
    infiles = sort_out_duplicates(infiles)

    # do a last check to weed out any possible duplicates that might skew training
    check_for_duplicates(infiles)

    trainfile = open(OUTFOLDER + "train.txt", mode="w", encoding="utf8")
    devfile = open(OUTFOLDER + "dev.txt", mode="w", encoding="utf8")
    testfile = open(OUTFOLDER + "test.txt", mode="w", encoding="utf8")

    trainwriter = csv.writer(trainfile, delimiter="\t", lineterminator="\n")
    devwriter = csv.writer(devfile, delimiter="\t", lineterminator="\n")
    testwriter = csv.writer(testfile, delimiter="\t", lineterminator="\n")

    # for each file
    for _, (_, infile) in infiles.items():
        print(f"Processing {infile}...")
        token_list, annotation_cols = process_document(infile, ORDERS)

        r = random.random()
        if r < DATA_RATIO[2]:
            writer = testwriter
        elif r < DATA_RATIO[1] + DATA_RATIO[2]:
            writer = devwriter
        else:
            writer = trainwriter

        # write the filename as a comment (flair ignores these in ColumnCorpus)
        writer.writerow([f"# {os.path.basename(infile)}"])
        for token, *order in zip(token_list, list(zip(*annotation_cols[::-1]))):
            writer.writerow([token] + list(order[0]))
        writer.writerow([])


    trainfile.close()
    devfile.close()
    testfile.close()
