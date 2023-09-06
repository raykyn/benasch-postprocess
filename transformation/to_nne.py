"""
This script converts custom standoff xml as produced by the postprocessing script to
a standoff annotation commonly used by standoff nested named entity annotation.

Example output:
This is a text !
3,4 text|0,1 this

If we change the custom standoff xml to be based on tokens instead of character indices at some point,
we could simplify this script a lot by not having to go over the inline script.
"""

try:
    from . import to_inline
except ImportError:
    import to_inline
from lxml import etree as et


def tokenize_tree(root, parent=None):
    """
    The process is easier if all text is included in token <T> elements.
    We can do this by iterating through all text and nodes and replacing
    it with text inside of the nodes instead.
    This would probably be easier if we just used <T> elements in the custom
    scheme. Definitely something to consider.
    """
    text = root.text
    if text != None:
        text = text.split()
        for i, t in enumerate(text):
            new_elem = et.Element("T")
            new_elem.text = t
            root.insert(i, new_elem)
        root.text = None

    tail = root.tail
    if tail != None:
        tail = tail.split()
        for i, t in enumerate(tail):
            new_elem = et.Element("T")
            new_elem.text = t
            # insert behind self to parent
            index = parent.index(root)
            parent.insert(index + i + 1, new_elem)
        root.tail = None

    children = list(root)
    for child in children:
        if child.tag != "T":
            tokenize_tree(child, root)

"""
def get_ancestors(node):
    We build a list with all ancestors of the token.
    We ignore head elements for that purpose!
    ancestors = []
    parent = node.getparent()
    while parent.tag != "Text":
        if parent.tag != "Head":
            ancestors.append(parent)
        parent = parent.getparent()
    
    return list(reversed(ancestors))
"""


def write_outstring(tokens, tags):
    token_string = " ".join(tokens)
    tag_string = "|".join([f"{start},{end} {label}" for start, end, label in tags])
    return token_string + "\n" + tag_string + "\n"


SPAN_TYPE_CONVERSION_DICT = {
    "Reference": "ref",
    "Attribute": "att",
    "Descriptor": "desc",
    "Value": "val",
    "Head": "head",
    "List": "list"
}


def process_document(docpath, config):
    # first transform it to inline xml so we have an easy to process hierarchy
    texttree = to_inline.process_document(docpath)

    to_inline.ATTRIBUTES_TO_INCLUDE = ["_ALL_"]
    tokenize_tree(texttree)

    if "assume_pretagged_heads" in config and config["assume_pretagged_heads"]:
        heads = texttree.findall(".//Head")
        for head in heads:
            starthead = et.Element("T")
            starthead.text = "<head>"
            endhead = et.Element("T")
            endhead.text = "</head>"
            head.insert(0, starthead)
            head.insert(len(head), endhead)

    tokens = texttree.findall(".//T")
    for i, token in enumerate(tokens):
        token.set("index", str(i))
    
    token_list = [t.text for t in tokens]

    out_tags = []

    if "split_labels" in config and config["split_labels"]:
        split_labels = True
    else:
        split_labels = False

    if "add_heads2" in config and config["add_heads2"]:
        spans = texttree.findall(f".//Head")
        for span in spans:
            parent = span.getparent()
            tokens = span.findall(".//T")
            start, end = int(tokens[0].get("index")), int(tokens[-1].get("index")) + 1
            label = ["head"]
            if split_labels:
                out_tags.append((start, end, "h:head"))
            if "add_span_type" in config and config["add_span_type"]:
                label.append(SPAN_TYPE_CONVERSION_DICT[parent.tag])
                if split_labels:
                    out_tags.append((start, end, f"span_type:{SPAN_TYPE_CONVERSION_DICT[parent.tag]}"))
            for attrib in config["attribs"]:
                if attrib in parent.attrib:
                    l = parent.get(attrib)
                    if config["tag_granularity"] != -1:
                        l = "_".join(l.split("_")[:config["tag_granularity"]])
                    label.append(l)
                    if split_labels:
                        out_tags.append((start, end, f"{attrib}:{l}"))
            label = ".".join(label)
            if not split_labels:
                out_tags.append((start, end, label))

    for tag in config["tags"]:
        spans = texttree.findall(f".//{tag}")
        for span in spans:
            tokens = span.findall(".//T")
            start, end = int(tokens[0].get("index")), int(tokens[-1].get("index")) + 1
            label = []
            if "add_heads2" in config and config["add_heads2"]:
                label.append("ctxt")
                if split_labels:
                    out_tags.append((start, end, "h:ctxt"))
            if "add_span_type" in config and config["add_span_type"]:
                label.append(SPAN_TYPE_CONVERSION_DICT[span.tag])
                if split_labels:
                    out_tags.append((start, end, f"span_type:{SPAN_TYPE_CONVERSION_DICT[span.tag]}"))
            for attrib in config["attribs"]:
                if attrib in span.attrib:
                    l = span.get(attrib)
                    if config["tag_granularity"] != -1:
                        l = "_".join(l.split("_")[:config["tag_granularity"]])
                    label.append(l)
                    if split_labels:
                        out_tags.append((start, end, f"{attrib}:{l}"))
            if not label:
                print("Warning: A tag was given but none of the given attributes could be found in the tag! Did you maybe forget to add the attribute?")
            label = ".".join(label)
            if not split_labels:
                out_tags.append((start, end, label))

    if "add_heads" in config and config["add_heads"]:
        spans = texttree.findall(f".//Head")
        for span in spans:
            tokens = span.findall(".//T")
            start, end = int(tokens[0].get("index")), int(tokens[-1].get("index")) + 1
            if not split_labels:
                out_tags.append((start, end, "head"))
            else:
                out_tags.append((start, end, "h:head"))

    if "add_lists" in config and config["add_lists"]:
        spans = texttree.findall(f".//List")
        for span in spans:
            tokens = span.findall(".//T")
            start, end = int(tokens[0].get("index")), int(tokens[-1].get("index")) + 1
            if not split_labels:
                out_tags.append((start, end, "list"))
            else:
                out_tags.append((start, end, "l:list"))


    return token_list, out_tags


if __name__ == "__main__":
    # example order
    config = {
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

    # tokens, tags = process_document("../outfiles/admin_008_HGB_1_024_074_020.xml", config)
    tokens, tags = process_document("../outfiles/admin_HGB_Exp_11_112_HGB_1_154_040_010.xml", config)

    # print(tokens, tags)

    print(write_outstring(tokens, tags))