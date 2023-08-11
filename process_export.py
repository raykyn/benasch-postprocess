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
INFOLDER = "data/hgb_2"

# Which annotators to process, leave empty for all
ANNOTATORS = ["bhitz"]


if __name__ == "__main__":
    annotation_folder = os.path.join(INFOLDER, "annotation")

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

            postprocess.process_xmi_zip(username + "_" + os.path.basename(filefolder), xmi)
    
    """
    pp.pprint("Finished processing all files.")
    pp.pprint(postprocess.mention_subtypes)
    pp.pprint(postprocess.desc_types)
    pp.pprint(postprocess.relation_types)
    """
