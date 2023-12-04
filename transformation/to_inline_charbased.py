"""
Convert custom XML to a pseudo-TEI format.
Important is that the tags are featured inside the text.
From this format, it should be particularly easy to further transform the format into other formats, such as IOB2.

This is an old version of the to_inline script which was incompletely changed to use tokens and can very simply be
reverted to use characters. I keep this around in case a project would prefer to work character- instead of token-based.
Mind you other scripts such as to_iob will expect the output from the newer script, featuring token-elements.

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


def fix_att_full_coverage(root):
    """
    If a att.xy covers exactly the same span as a reference in the same place,
    there must be an error, as at least one of the two has a head missing.
    Most likely, the att.xy should have been a desc.xy, but changing it now is too late,
    so just drop a warning, remove the Attribute that is problematic and move on.
    Also give the head positions to the reference.
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
    # oldtext = oldroot.find("Text").text # DELETE
    oldtokens = oldroot.findall(".//T")

    # Fix the attribute instead of desc error
    oldroot = fix_att_full_coverage(oldroot)

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
        #print(node, position, is_head)
        if is_head:
            position = "head_" + position
        index = int(node.get(position))
        if index > len(oldtokens):
            print("WARNING: Tag index was outside text length. This can happen when a header was annotated and removed.")
            continue
        oldtokens = oldtokens[:index] + [convert_tag(node, position, is_head)] + oldtokens[index:]

    oldtokens = ["<Text>"] + oldtokens + ["</Text>"]
    oldtext = "".join(oldtokens)

    oldtext = oldtext.replace("&", "&amp;")

    try:
        textnode = et.fromstring(oldtext)
    except et.XMLSyntaxError as e:
        print(e)
        print(oldtext.encode("utf8"))
        textnode = et.fromstring(oldtext, parser=et.XMLParser(recover=True))

    return textnode


if __name__ == "__main__":
    textnode = process_document("../outfiles/admin_test_inc.xml")
    write_document("text.xml", textnode)