"""
Create a json-file which splits our outfiles into a train, a dev and a test-share.

Probably this should just be produced as a result of process_export => TODO
"""

import os
from collections import Counter
from glob import glob
import random
import json

INFOLDER = "./data/std_xml/outfiles_24_04_30/"  # The folder where all the standoff xml are
USER_RANKING = ["kfuchs", "bhitz", "admin"]  # left is preferred (should match process_export)
RULE_USER_DISTRO = {  # overwrites the USER_RANKING for certain corpora
    "HGB_Exp_6": "admin"
}
DATA_RATIO = [0.8, 0.1, 0.1]  # Train, Dev, Test
OUTFILE = "consistent_data_24_04_03.json"

def sort_out_duplicates(infiles):
    filedict = {}
    for infile in infiles:
        basename = os.path.basename(infile)
        basename = basename.split("_")
        username, basename = basename[0], "_".join(basename[1:])
        if basename in filedict:
            filedict[basename][0].append(username)
        else:
            filedict[basename] = ([username], basename)
        
    
    for entry in filedict:
        if len(filedict[entry][0]) > 1:
            possible_users = ", ".join(filedict[entry][0])
            print(f"Resolving file {entry} between users {possible_users}.")
            for rule in RULE_USER_DISTRO:
                if entry.startswith(rule):
                    filedict[entry] = ([RULE_USER_DISTRO[rule]], filedict[entry][1])
                    print(f"User {RULE_USER_DISTRO[rule]} was chosen based on the defined rules for {rule}.")
                    break
            else:
                for username in USER_RANKING:
                    if username in filedict[entry][0]:
                        print(filedict[entry])
                        filedict[entry] = ([username], filedict[entry][1])
                        break
                print(f"User {username} was chosen.")
    
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

    basenames = []
    for _, (username, infile) in infiles.items():
        basenames.append(os.path.basename("_".join([username[0], infile])))

    random.shuffle(basenames)
    split_1, split_2 = round(len(basenames) * DATA_RATIO[0]) - 1, round(len(basenames) * (DATA_RATIO[0] + DATA_RATIO[1])) - 1
    outdict["train"], outdict["dev"], outdict["test"] = basenames[:split_1], basenames[split_1:split_2], basenames[split_2:]

    with open(OUTFILE, mode="w", encoding="utf8") as writer:
        json.dump(outdict, writer)


