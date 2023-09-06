import os
from collections import defaultdict, Counter
from glob import glob
import random
from transformation.to_nne import process_document, write_outstring

### SETTINGS ###
INFOLDER = "outfiles/"  # The folder where all the standoff xml are
USER_RANKING = ["kfuchs", "admin", "bhitz"]  # left is preferred
DATA_RATIO = [0.8, 0.1, 0.1]  # Train, Dev, Test
OUTFOLDER = "trainingdata_nne/"

CONFIG = {
        "add_span_type": True,  # add ref, att, val, desc ... as part of the labels
        "tags": ["Reference", "Attribute", "Value", "Descriptor"],  # which tags should be included
        # "attribs": ["mention_type", "entity_type", "value_type", "desc_type"],  # which info should be used in the labels
        "attribs": [],  # which info should be used in the labels
        "split_labels": True,  # if this is enabled, the info about span_type, attribs, and head/context is all put into separate labels
        "tag_granularity": 1,  # how granular should the label info be
        "add_heads": True,  # add heads as their own labels
        "add_heads2": False,  # add heads not as own labels, but instead as part of the official labels
        "add_lists": True,  # add lists as their own labels
        "assume_pretagged_heads": True
    }


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

    trainfile = open(OUTFOLDER + "train.data", mode="w", encoding="utf8")
    devfile = open(OUTFOLDER + "dev.data", mode="w", encoding="utf8")
    testfile = open(OUTFOLDER + "test.data", mode="w", encoding="utf8")

    for _, (_, infile) in infiles.items():
        print(f"Processing {infile}...")
        tokens, tags = process_document(infile, CONFIG)
        outstring = write_outstring(tokens, tags)

        r = random.random()
        if r < DATA_RATIO[2]:
            writer = testfile
        elif r < DATA_RATIO[1] + DATA_RATIO[2]:
            writer = devfile
        else:
            writer = trainfile

        writer.write(outstring)
        writer.write("\n")

    trainfile.close()
    devfile.close()
    testfile.close()
