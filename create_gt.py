"""
Creates ground truth as required by the new evaluation algorithm.
"""

from transformation import to_anno_tree
import glob, os, json
from lxml import etree as et


INFILES = "./data/std_xml/outfiles_24_04_30/*.xml"
OUTFILE = "./data/gt/gt_24_04_30.xml"
CONSISTENT_DATA = "./data/persistent_data/persistent_data_24_04_30_0.json"


if __name__ == "__main__":
    with open(CONSISTENT_DATA, mode="r", encoding="utf8") as cons:
        consistent_data = json.load(cons)

    out = et.Element("Corpus")
    for infile in sorted(glob.glob(INFILES)):
        outname = os.path.basename(infile)
        if outname in consistent_data["test"]:
            print(infile)
            root = to_anno_tree.transform(infile)
            out.append(root)
    out_tree = et.ElementTree(out)
    out_tree.write(OUTFILE, xml_declaration=True, pretty_print=True, encoding="utf8")