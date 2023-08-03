"""
Convert custom XML to a pseudo-TEI format.
Important is that the tags are featured inside the text.
From this format, it should be particularly easy to further transform the format into other formats, such as IOB2.

For a future TEI conversion script we can largely use the same script with some simple tag conversion added on.
"""

import os
import re
from lxml import etree as et

# Put in this list all nodes by xpath syntax to be converted (from root)
# a node must contain a start and end attribute to be valid for conversion
TO_CONVERT = ["./Mentions/*", "./Descriptors/*", "./Values/*"]

# Write "_ALL_" to include all attributes
ATTRIBUTES_TO_INCLUDE = ["_ALL_"]
#ATTRIBUTES_TO_INCLUDE = []
#ATTRIBUTES_TO_INCLUDE = ["mention_type", "entity_type", "desc_type", "value_type"]

# if including all attributes, those in here will be excluded
ATTRIBUTES_TO_EXCLUDE = ["head_text", "text", "start", "end", "head_start", "head_end"]


def get_node_priority(node, is_head):
    if node.tag == "Descriptor":
        return 1
    elif is_head:
        return -1
    else:
        return 0
    

def get_attribute_string(node):
    if "_ALL_" in ATTRIBUTES_TO_INCLUDE:
        attributes = node.attrib
        for att in ATTRIBUTES_TO_EXCLUDE:
            if att in attributes:
                del attributes[att]
        attributes = [f'{att}="{value}"' for att, value in attributes.items()]
    elif not ATTRIBUTES_TO_INCLUDE:
        return ""
    else:
        attributes = []
        for att in ATTRIBUTES_TO_INCLUDE:
            value = node.get(att)
            if value != None:
                attributes.append(f'{att}="{value}"')

    if not attributes:
        return ""

    return " " + " ".join(attributes)

    
def convert_tag(node, position, is_head):
    if is_head:
        if position == "head_end":
            newstring = "</Head>"
        else:
            newstring = "<Head>"
        return newstring

    if position == "end":
        newstring = "</" + node.tag + ">"
    else:
        newstring = "<" + node.tag + get_attribute_string(node) + ">"

    return newstring


def write_document(docpath, node):
    tree = et.ElementTree(node)
    tree.write(docpath, xml_declaration=True, pretty_print=True, encoding="utf8")


def sort_function(elem):
    node, pos, is_head = elem
    if is_head:
        start = "head_start"
        end = "head_end"
    else:
        start = "start"
        end = "end"

    if pos == "end":
        return (-int(node.get(end)), int(node.get(start)), -get_node_priority(node, is_head))
    else:
        return (-int(node.get(start)), int(node.get(end)), get_node_priority(node, is_head))


def process_document(docpath):
    oldroot = et.parse(docpath).getroot()
    oldtext = oldroot.find("Text").text

    # sort all valid elements by their position, then priority (1. end index, 2. start index, 3. tag)
    nodes = []
    for c in TO_CONVERT:
        no = oldroot.findall(c)
        for n in no:
            # add two elements, one for opening the bracket, one for closing it
            nodes.append((n, "start", False))
            nodes.append((n, "end", False))

            # if there's heads, we also need to add those
            if "head_start" in n.attrib:
                nodes.append((n, "start", True))
                nodes.append((n, "end", True))

    nodes = sorted(nodes, key=lambda x: sort_function(x))
    #for n in nodes:
    #    print(n[0].get("head_text"), n[1])

    for node, position, is_head in nodes:
        if is_head:
            position = "head_" + position
        index = int(node.get(position))
        oldtext = oldtext[:index] + convert_tag(node, position, is_head) + oldtext[index:]

    oldtext = "<Text>" + oldtext + "</Text>"

    oldtext = oldtext.replace("&", "&amp;")

    #print(oldtext)

    #textnode = et.fromstring(oldtext, parser=et.XMLParser(recover=True))
    textnode = et.fromstring(oldtext)

    return textnode


if __name__ == "__main__":
    textnode = process_document("../outfiles/admin_001_HGB_1_002_096_007.xml")
    write_document("text.xml", textnode)