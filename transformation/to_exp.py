"""
Experimental transformation, not for general use.
Will probably also frequently change what it does.
"""

import csv
try:
    from . import to_inline
except ImportError:
    import to_inline
from lxml import etree as et
import pprint as pp


def write_outfile(docpath, token_list, annotation_cols):
    """
    Horribly convoluted, I'm sorry for whoever looks at this code.
    """
    with open(docpath, mode="w", encoding="utf8") as out:
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        annotation_rows = []
        for i in range(len(token_list)):
            row = [token_list[i]]
            for col in annotation_cols:
                row.append(col[i])
            annotation_rows.append(row)
        writer.writerows(annotation_rows)


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


def get_ancestors(node):
    """
    We build a list with all ancestors of the token.
    We ignore head elements for that purpose!
    """
    ancestors = []
    parent = node.getparent()
    while parent.tag != "Body":
        #if parent.tag != "Head":
        ancestors.append(parent)
        parent = parent.getparent()
    
    return list(reversed(ancestors))


def check_if_first(node, ancestor, is_head=False):
    """
    Check if this is the first token of a full span
    """
    if not is_head:
        first_child = ancestor[0]
        while first_child.tag != "T":
            first_child = first_child[0]
        
        if node == first_child:
            return True
        else:
            return False
    else:
        # heads are easy to check
        return node.getparent().index(node) == 0
    

def check_parent(filter, annotation):
    """
    Filter is a dict where the key references an attribute of the annotation.
    "doc" is a special case, where spans without a parent are also included.
    The dict is considered an OR-construction for the moment, so only one condition must match.
    """

    for key, value in filter.items():
        for v in value:
            if key == "tag":
                if v == "ref" and annotation.tag == "Reference":
                    return True
                elif v == "att" and annotation.tag == "Attribute":
                    return True
                elif v == "val" and annotation.tag == "Value":
                    return True
                elif v == "lst" and annotation.tag == "List":
                    return True
                elif v == "desc" and annotation.tag == "Descriptor":
                    return True
            elif annotation.get(key).startswith(v):
                return True
    return False


def process_annotation(annotation, config, depth=1):
    more_annotations = []

    if annotation.tag in config["tags"] and filter_ancestors(annotation, config):
        if config["require_parent"] is None or check_parent(config["require_parent"], annotation): # ("entity_type" in annotation.attrib and "_".join(annotation.get("entity_type").split("_")[:config["tag_granularity"]]) in config["require_parent"]):
            new_tags = []
            tokens = annotation.findall(".//T")
            ancestors_list = [get_ancestors(token) for token in tokens]

            if config["depth_anno"] == "Binary":
                new_tags.append(("ENT", "B-ENT"))
            elif config["depth_anno"] == "Ordinal":
                new_tags.append((f"DEPTH-{depth}", "B-ENT"))

            if config["tag_anno"] is not None:
                pretag = []
                for val in config["tag_anno"]:
                    if val in annotation.attrib:
                        pretag.append("_".join(annotation.get(val).split("_")[:config["tag_granularity"]]))
                pretag = ".".join(pretag)
                new_tags.append((f"{pretag.upper()}", f"B-PRETAG-{pretag.upper()}"))


            for t, ancestors in zip(tokens, ancestors_list):
                ancestors = [a for a in ancestors if filter_ancestors(a, config, allow_heads=True)]
                if depth < len(ancestors):
                    first_ancestor = ancestors[depth]
                    if first_ancestor.get("skip") is not None:
                        if depth + int(first_ancestor.get("skip")) < len(ancestors):
                            first_ancestor = ancestors[depth + int(first_ancestor.get("skip"))]
                        else:
                            continue

                    if check_if_first(t, first_ancestor):
                        attach = "B-"
                    else:
                        attach = "I-"
                    if first_ancestor.tag == "Head":
                        tag = "head"
                    else:
                        tag = []
                        for k, v in config["tags"][first_ancestor.tag].items():
                            if k == "tag":
                                tag.append(f"tag:{v}")
                                continue
                            if first_ancestor.get(k):
                                prefix = ""
                                if v["prefix"]:
                                    prefix = v["prefix"] + ":"
                                value = "_".join(first_ancestor.get(k).split("_")[:config["tag_granularity"]])
                                if ":" in value or ";" in value:
                                    print("Warning: Disallowed character such as : or ; in label!")
                                    value = value.replace(":", "_").replace(";", "_")
                                tag.append(prefix + value)
                        tag = ";".join(tag)
                    tag = attach + tag
                else:
                    tag = "O"
                new_tags.append((t.text, tag))

            if config["tag_anno"] is not None:
                new_tags.append((f"{pretag.upper()}", f"B-PRETAG-{pretag.upper()}"))

            if config["depth_anno"] == "Binary":
                new_tags.append(("ENT", "B-ENT"))
            elif config["depth_anno"] == "Ordinal":
                new_tags.append((f"DEPTH-{depth}", "B-ENT"))
            
            if new_tags:
                more_annotations.append(new_tags)
            depth += 1
        else:
            depth += 1
    
    for anno in annotation.findall("./*"):
        more_annotations.extend(process_annotation(anno, config, depth))
    return more_annotations

def add_skips(elem, num):
    elem.set("skip", str(num))
    for child in elem:
        add_skips(child, num)

def filter_ancestors(ancestor, config, allow_heads=False):
    if allow_heads and ancestor.tag == "Head":
        return True
    if ancestor.tag not in config["tags"]:
        return False
    
    if config["merge_overlapping_desc_tags"]:
        # this code currently doesn't work if we have more than one tag of the same span in the hierarchy
        # should not happen anyway with out data
        # this is hacky as hell anyways so, stuff like this should be solved first in postprocessing anyways
        parent = ancestor.getparent()
        if parent.tag == "Descriptor" and parent.findall(".//T") == ancestor.findall(".//T"):
            parent.getparent().set("mention_subtype", parent.get("desc_type"))
            parent.set("skip", str(1))
            add_skips(ancestor, 1)

    for key, value in config["tags"][ancestor.tag].items():
        if key == "tag":
            return True
        # value is a dict with "include" where all tags to read are contained, an empty "include" means to include the tag
        # "exclude" where all tags not to include are kept
        include = value["include"]
        exclude = []
        if "exclude" in value:
            exclude = value["exclude"]
        if key not in ancestor.attrib:
            return False
        if "_".join(ancestor.get(key).split("_")[:config["tag_granularity"]]) in exclude:
            return False
        if include and "_".join(ancestor.get(key).split("_")[:config["tag_granularity"]]) not in include:
            return False
    return True

def process_document(docpath, config):
    # first transform it to inline xml so we have an easy to process hierarchy
    texttree = to_inline.process_document(docpath)

    to_inline.ATTRIBUTES_TO_INCLUDE = ["_ALL_"]

    tokens = texttree.findall(".//T")
    ancestors_list = [get_ancestors(token) for token in tokens]

    annotations = []

    if config["require_parent"] is None or "doc" in config["require_parent"]:
        first_layer_annotation = []

        if config["depth_anno"] == "Binary":
            first_layer_annotation.append(("DOC", "B-DOC"))
        elif config["depth_anno"] == "Ordinal":
            first_layer_annotation.append(("DEPTH-0", "B-DOC"))
        elif config["tag_anno"] is not None:
            ## we only put a doc thing here if tag anno is activated
            first_layer_annotation.append(("DOC", "B-DOC"))

        for t, ancestors in zip(tokens, ancestors_list):
            # filter to only keep the annotations we're interested in
            ancestors = [a for a in ancestors if filter_ancestors(a, config)]
            
            if ancestors:
                first_ancestor = ancestors[0]
                if check_if_first(t, first_ancestor):
                    attach = "B-"
                else:
                    attach = "I-"
                tag = []
                for k, v in config["tags"][first_ancestor.tag].items():
                    if k == "tag":
                        tag.append(f"tag:{v}")
                        continue
                    if first_ancestor.get(k):
                        prefix = ""
                        if v["prefix"]:
                            prefix = v["prefix"] + ":"
                        value = "_".join(first_ancestor.get(k).split("_")[:config["tag_granularity"]])
                        if ":" in value or ";" in value:
                            print("Warning: Disallowed character such as : or ; in label!")
                            value = value.replace(":", "_").replace(";", "_")
                        tag.append(prefix + value)
                tag = ";".join(tag)
                tag = attach + tag
            else:
                tag = "O"
            first_layer_annotation.append((t.text, tag))

        if config["depth_anno"] == "Binary":
            first_layer_annotation.append(("DOC", "B-DOC"))
        elif config["depth_anno"] == "Ordinal":
            first_layer_annotation.append(("DEPTH-0", "B-DOC"))
        elif config["tag_anno"] is not None:
            ## we only put a doc thing here if tag anno is activated
            first_layer_annotation.append(("DOC", "B-DOC"))

        annotations.append(first_layer_annotation)

    if config["require_parent"] is None or "doc" not in config["require_parent"]:
        for annotation in texttree.findall("./*"):
            annotations.extend(process_annotation(annotation, config))

    return annotations


if __name__ == "__main__":
    # example config
    tags_to_include = ["date", "per", "loc", "money", "gpe", "org"]
    config = {
            "tags": {
                "List": {
                    "tag": "list",
                    "entity_types": {"include": [], "prefix": "ent"},
                    "subtype": {"include": [], "prefix": "stype"}, 
                },
                "Reference": {
                    "tag": "ref",
                    "mention_type": {"include": [], "prefix": "men"}, 
                    "entity_type": {"include": [], "prefix": "ent"}, 
                    "mention_subtype": {"include": [], "prefix": "submen"},
                    "numerus": {"include": [], "prefix": "num"},
                    "specificity": {"include": [], "prefix": "spec"},
                    }, 
                "Attribute": {
                    "tag": "att",
                    "mention_type": {"include": [], "prefix": "men"}, 
                    "entity_type": {"include": [], "prefix": "ent"}, 
                    "mention_subtype": {"include": [], "prefix": "submen"},
                    "numerus": {"include": [], "prefix": "num"},
                    "specificity": {"include": [], "prefix": "spec"},
                    }, 
                "Value": {"tag": "val", "value_type": {"include": [], "prefix": "val"}}, 
                #"Descriptor": {"desc_type": {"include": [], "prefix": "desc.desc"}}
            },
            "merge_overlapping_desc_tags": False,  # if a desc tag covers the same span as another tag (Reference or Attribute usually), we put the desc tag as a mention subtype info to the entity annotation instead.
            "depth_anno": None,  # annotate the depth, options: "None", "Binary" (doc vs ent level), "Ordinal"
            "tag_anno": None, # annotate the parent tag, options: "None" or list of attributes that should be annotated (e.g. ["entity_type"])  
            "tag_granularity": 2,  # how granular should the label info be (TODO: Move to the instructions per tag type)
            "require_parent": None  # only add a sequence to the annotations if the parent of that sequence is one of the given entity_type, or give "doc" if flat annotations are wanted, None to disable filter
        }
    annotations = process_document("./outfolder_24_02_22/bhitz_HGB_Exp_9_183_HGB_1_215_063_015.xml", config)

    #annotations = process_document("../outfiles/admin_HGB_Exp_11_112_HGB_1_154_040_010.xml", config)
    
    #annotations = process_document("../outfiles/admin_008_HGB_1_024_074_020.xml", config)
    pp.pprint(annotations)

    #write_outfile("test.tsv", token_list, annotation_cols)