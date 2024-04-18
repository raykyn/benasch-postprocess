"""
Convert custom XML to a pseudo-TEI format.
Important is that the tags are featured inside the text.
From this format, it should be particularly easy to further transform the format into other formats, such as IOB2.

For a future TEI conversion script we can largely use the same script with some simple tag conversion added on.
"""

import os
import re
from lxml import etree as et

XML_VALIDATION_LINK = "https://dhbern.github.io/BeNASch/static/benasch.rng"
# Put in this list all nodes by xpath syntax to be converted (from root)
# a node must contain a start and end attribute to be valid for conversion
TO_CONVERT = ["./Mentions/*", "./Descriptors/*", "./Values/*"]

# Write "_ALL_" to include all attributes
ATTRIBUTES_TO_INCLUDE = ["_ALL_"]
#ATTRIBUTES_TO_INCLUDE = []
#ATTRIBUTES_TO_INCLUDE = ["mention_type", "entity_type", "desc_type", "value_type"]

# if including all attributes, those in here will be excluded
ATTRIBUTES_TO_EXCLUDE = ["head_text", "text", "start", "end", "head_start", "head_end"]


def fix_att_full_coverage(root):
    """
    If a att.xy covers exactly the same span as a reference in the same place,
    there must be an error, as at least one of the two has a head missing.
    Most likely, the att.xy should have been a desc.xy, but changing it now is too late,
    so just drop a warning, remove the Attribute that is problematic and move on.
    Also give the head positions to the reference.
    NOTE: Kind of depreciated as validation is done separately now?
    """
    ref_spans = root.findall("./Mentions/Reference")
    att_spans = root.findall("./Mentions/Attribute")
    for ref in ref_spans:
        for att in att_spans:
            if ref.get("start") == att.get("start") and ref.get("end") == att.get("end"):
                print("ERROR: A reference and an attribute cover each other fully, meaning a head is missing. Attribute will be deleted and Reference fixed, please investigate.")
                print(att.get("head_text"))
                ref.set("head_start", att.get("head_start"))
                ref.set("head_end", att.get("head_end"))
                att.getparent().remove(att)
    return root


def add_attributes(elem, node):
    if "_ALL_" in ATTRIBUTES_TO_INCLUDE:
        for att, value in node.attrib.items():
            if att in ATTRIBUTES_TO_EXCLUDE:
                continue
            elem.set(att, value)
    elif not ATTRIBUTES_TO_INCLUDE:
        return
    else:
        for att in ATTRIBUTES_TO_INCLUDE:
            value = node.get(att)
            if value != None:
                elem.set(att, value)


def write_document(docpath, node):
    tree = et.ElementTree(node)
    tree.write(docpath, xml_declaration=True, pretty_print=True, encoding="utf8")


def get_node_priority(node):
    if node.tag == "Descriptor":
        return 1
    else:
        return 0


def sort_function(elem):
    node_length = int(elem.get("end")) - int(elem.get("start"))
    return (node_length, get_node_priority(elem))


def process_document(docpath):
    oldroot = et.parse(docpath).getroot()
    tokens = oldroot.findall(".//T")

    # only for a debug thing, delete after!
    head_elems = oldroot.findall(".//Reference[@entity_type='head']")
    for elem in head_elems:
        del elem

    # Fix the attribute instead of desc error
    oldroot = fix_att_full_coverage(oldroot)

    # sort all valid elements by their position, then priority (1. end index, 2. start index, 3. tag)
    nodes = []
    for c in TO_CONVERT:
        no = oldroot.findall(c)
        nodes.extend(no)

    toproot = et.Element("XML")
    metadata = oldroot.find("Metadata")
    if metadata is not None:
        metadata.tag = "Header"
        toproot.append(metadata)

    root = et.SubElement(toproot, "Body")

    nodes = sorted(nodes, key=lambda x: sort_function(x))
    for token in tokens:
        root.append(token)

    for node in nodes:
        incl_tokens = tokens[int(node.get("start")):int(node.get("end"))]
        elem = et.SubElement(root, node.tag)
        add_attributes(elem, node)
        for token in incl_tokens:
            child = token
            parent = child.getparent()
            while parent.tag != "Body" and parent != elem:
                child = parent
                parent = child.getparent()
            if parent != elem:
                root.insert(root.index(child), elem)
                elem.append(child)
        
        # if element contains a head, we need to append that
        if "head_start" in node.attrib and node.get("head_start"):
            incl_tokens = tokens[int(node.get("head_start")):int(node.get("head_end"))]
            head_elem = et.SubElement(elem, "Head")
            # print(et.tostring(elem))
            # print(et.tostring(incl_tokens[0]))
            try:
                elem.insert(elem.index(incl_tokens[0]), head_elem)
                for token in incl_tokens:
                    head_elem.append(token)
            except ValueError as er:
                print(er)
                print("A Head element could not be inserted at the right position in the XML tree. This probably indicates an invalid annotation.")
                print(et.tostring(elem)) 

    # print(et.tostring(root, pretty_print=True))

    pi = et.ProcessingInstruction('xml-model', f'href="{XML_VALIDATION_LINK}" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"') 
    toproot.addprevious(pi)
    return toproot


if __name__ == "__main__":
    #textnode = process_document("../outfolder_24_02_22/bhitz_HGB_Exp_3_001_HGB_1_002_037_012.xml")
    #write_document("text.xml", textnode)

    import glob
    import os
    import pathlib

    outfolder = "./auto_tagged/hgb_corpus_full/"
    pathlib.Path(outfolder).mkdir(parents=True, exist_ok=True) 
    for infile in sorted(glob.glob("./from_inference/out/hgb_specific_full/*.xml")):
        print(infile)
        inline = process_document(infile)
        write_document(outfolder + os.path.basename(infile), inline)
