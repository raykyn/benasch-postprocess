"""
The idea of this script is to print a file
where each filename is made up in a way ready to be
copied into a json file with train, dev and test
keys which is then compatible with all the transformation
scripts.
This script also provides some options to filter for specific
documents.
"""

import os
from collections import Counter
from glob import glob
import json
from lxml import etree as et
import random

INFOLDER = "./data/std_xml/24_07_01/"  # The folder where all the standoff xml are
USER_RANKING = ["kfuchs", "bhitz", "admin"]  # left is preferred (should match process_export)
RULE_USER_DISTRO = {  # overwrites the USER_RANKING for certain corpora
    "HGB_Exp_6_": "admin"
}
EXCLUDE_DOCUMENTS = [
    #"HGB_Exp_11_",
    #"HGB_Exp_12_"
]
OUTFILE = "ner_rec_24_07_01.json"
# absolute_test => assign TEST_NUM to test, rest split between train and dev (should add up to 1)
# ratios => classic ratio splitting
TRAIN_TEST_SPLIT_MODE = "ratios"
TRAIN, DEV, TEST = 0.8, 0.1, 0.1

def filter_function(root):
    """
    Modify this function for whatever you'd like to filter for.
    """
    # only documents with specific event on doc level
    #return root.xpath(".//Event[@type='sale' and @anchor='doc']")
    # only documents with any event on doc level
    #return root.xpath(".//Event[@anchor='doc']")
    # accept all documents
    return True

def sort_out_duplicates(infiles):
    filedict = {}
    for infile in infiles:
        basename = os.path.basename(infile)
        basename = basename.split("_")
        username, basename = basename[0], "_".join(basename[1:])
        for excl in EXCLUDE_DOCUMENTS:
            if basename.startswith(excl):
                break
        else:
            if basename in filedict:
                filedict[basename][0].append(username)
            else:
                filedict[basename] = ([username], basename, infile)
    
    for entry in filedict:
        if len(filedict[entry][0]) > 1:
            possible_users = ", ".join(filedict[entry][0])
            print(f"Resolving file {entry} between users {possible_users}.")
            for rule in RULE_USER_DISTRO:
                if entry.startswith(rule):
                    filedict[entry] = ([RULE_USER_DISTRO[rule]], filedict[entry][1], filedict[entry][2])
                    print(f"User {RULE_USER_DISTRO[rule]} was chosen based on the defined rules for {rule}.")
                    break
            else:
                for username in USER_RANKING:
                    if username in filedict[entry][0]:
                        print(filedict[entry])
                        filedict[entry] = ([username], filedict[entry][1], filedict[entry][2])
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


def filter_documents(infiles, filter_function):
    clean = {}
    for infile in infiles:
        infile_path = infiles[infile][2]
        root = et.parse(infile_path).getroot() # type: ignore
        valid = bool(filter_function(root))
        if valid:
            clean[infile] = infiles[infile]
    return clean


if __name__ == "__main__":
    infiles = glob(INFOLDER + "*.xml")

    # sort out duplicates
    infiles = sort_out_duplicates(infiles)

    # do a last check to weed out any possible duplicates that might skew training
    check_for_duplicates(infiles)

    infiles = filter_documents(infiles, filter_function)
    print(len(infiles))

    outdict = {
        "train": [],
        "dev": [],
        "test": []
    }

    basenames = []
    for _, (username, infile, path) in infiles.items():
        basenames.append(os.path.basename("_".join([username[0], infile])))

    random.shuffle(basenames)
    if TRAIN_TEST_SPLIT_MODE == "ratios":
        split_1, split_2 = round(len(basenames) * TRAIN) - 1, round(len(basenames) * (TRAIN + DEV)) - 1
        outdict["train"], outdict["dev"], outdict["test"] = basenames[:split_1], basenames[split_1:split_2], basenames[split_2:]
    elif TRAIN_TEST_SPLIT_MODE == "absolute_test":
        outdict["test"], rest = basenames[:TEST], basenames[TEST:]
        split = (round(len(rest) * TRAIN) - 1)
        outdict["train"], outdict["dev"] = rest[:split], rest[split:]
    else:
        raise NotImplementedError
    
    with open(OUTFILE, mode="w", encoding="utf8") as writer:
        json.dump(outdict, writer)