"""
Creates ground truth as required by the new evaluation algorithm.
"""

from transformation import to_anno_tree
import glob, os, json
from lxml import etree as et
import pathlib


INFILES = "./data/std_xml/24_07_01/*.xml"
OUTFILE = "./data/gt/gt_24_07_01.xml"
CONSISTENT_DATA = "./data/training_data_json/ner_rec/ner_rec_24_07_01.json"


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
    pathlib.Path(OUTFILE).parent.mkdir(parents=True, exist_ok=True)
    out_tree.write(OUTFILE, xml_declaration=True, pretty_print=True, encoding="utf8")