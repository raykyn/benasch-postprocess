"""
This is a helper script working with postprocess.py to read the export folder provided by inception.
Important: 
We will skip any files which do not contain at least one <Span>-Node!
"""

import glob
import postprocess
import os
import zipfile
import pprint as pp


# Path Info
DATA = "./data/hgb_2025_04_03/"

# ACTIONS
ACTIONS = ["PROCESS"]

# FOLDER PATHS (best to keep like this)
EXPORT = os.path.join(DATA, "exports")
UNZIPPED = os.path.join(DATA, "unzipped")
OUTPUT = os.path.join(DATA, "processed")
postprocess.OUTFOLDER = OUTPUT

# Which annotators to process, leave empty for all
ANNOTATORS = []

# choose if elements annotated with "htr.delete" should be deleted (False) or written as annotations (True)
WRITE_DELETIONS = False


if __name__ == "__main__":
    if "UNZIP" in ACTIONS:
        for infolder in glob.glob(EXPORT + "/*"):
            if not os.path.isdir(infolder):  # don't process the zip files
                continue

            annotation_folder = os.path.join(infolder, "annotation")

            filefolders = sorted(glob.glob(os.path.join(annotation_folder, "*")))

            for filefolder in filefolders:
                userfolders = sorted(glob.glob(os.path.join(filefolder, "*.zip")))

                for userfolder in userfolders:
                    username = os.path.basename(userfolder).replace(".zip", "")
                    if username == "INITIAL_CAS":
                        continue
                    if ANNOTATORS and username not in ANNOTATORS:
                        continue
                    archive = zipfile.ZipFile(userfolder, 'r')
                    xmi = archive.read(username + ".xmi")

                    # write the xmi to the unzipped folder
                    if not os.path.exists(UNZIPPED):
                        os.makedirs(UNZIPPED)
                    with open(os.path.join(UNZIPPED, username + "_" + os.path.basename(filefolder)).replace(".txt", ".xmi"), 'wb') as f:
                        f.write(xmi)
    if "PROCESS" in ACTIONS:
        for infile in sorted(glob.glob(UNZIPPED + "/*.xmi")):
            postprocess.process_xmi(infile, write_deletions=WRITE_DELETIONS)