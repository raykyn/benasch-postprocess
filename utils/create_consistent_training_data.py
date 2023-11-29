"""
Create a json-file which splits our outfiles into a train, a dev and a test-share.
"""

import os
from collections import Counter
from glob import glob
import random
import json

INFOLDER = "outfiles/"  # The folder where all the standoff xml are
USER_RANKING = ["kfuchs", "admin", "bhitz"]  # left is preferred
DATA_RATIO = [0.8, 0.1, 0.1]  # Train, Dev, Test
OUTFILE = "consistent_data.json"

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

    outdict = {
        "train": [],
        "dev": [],
        "test": []
    }

    # TODO: Shuffle documents instead of the random system
    # with the current system train can end up larger than it should be

    for _, (_, infile) in infiles.items():
        basename = os.path.basename(infile)

        r = random.random()
        if r < DATA_RATIO[2] and len(outdict["test"]) <= DATA_RATIO[2]*len(infiles):
            outdict["test"].append(basename)
        elif r < DATA_RATIO[1] + DATA_RATIO[2] and len(outdict["dev"]) <= DATA_RATIO[1]*len(infiles):
            outdict["dev"].append(basename)
        else:
            outdict["train"].append(basename)

    with open(OUTFILE, mode="w", encoding="utf8") as writer:
        json.dump(outdict, writer)


