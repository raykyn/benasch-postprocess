"""
This script converts custom standoff xml as produced by the postprocessing script to
a standoff annotation commonly used by standoff nested named entity annotation.

Example output:
This is a text !
3,4 text|0,1 this
"""

from lxml import etree as et
import pprint as pp


def process_document(docpath, config):
    root = et.parse(docpath).getroot()
    tokens = root.findall(".//T")
    text = " ".join([t.text for t in tokens])
    annotations = []
    for tag in config["tags"]:
        elems = root.findall(f".//{tag}")
        for elem in elems:
            tag_list = [("tag", config["tags"][tag]["tag"])]
            for attr in config["tags"][tag]:
                if attr == "tag":
                    continue
                tag_list.append((config["tags"][tag][attr]["prefix"], "_".join(elem.get(attr).split("_")[:config["tag_granularity"]])))
            start = elem.get("start")
            end = elem.get("end")
            definite_tag = ";".join([":".join(t) for t in tag_list])
            annotation = f"{start},{end} {definite_tag}"
            annotations.append(annotation)
            
            # add head if exists
            if "head_text" in elem.attrib:
                definite_tag = "head"
                start = elem.get("head_start")
                end = elem.get("head_end")
                annotation = f"{start},{end} {definite_tag}"
                annotations.append(annotation)

    return text, "|".join(annotations)


if __name__ == "__main__":
    # example config
    tags_to_include = ["date", "per", "loc", "money", "gpe", "org"]
    # currently most configs are not implemented anymore, as this script is rarely used.
    config = {
            "tags": {
                #"List": {
                #    "tag": "lst",
                #    "entity_types": {"include": [], "prefix": "ent"},
                #    "subtype": {"include": [], "prefix": "stype"}, 
                #},
                "Reference": {
                    "tag": "ref",
                    #"mention_type": {"include": [], "prefix": "men"}, 
                    "entity_type": {"include": [], "prefix": "ent"}, 
                    #"mention_subtype": {"include": [], "prefix": "submen"},
                    #"numerus": {"include": [], "prefix": "num"},
                    #"specificity": {"include": [], "prefix": "spec"},
                    }, 
                "Attribute": {
                    "tag": "att",
                    #"mention_type": {"include": [], "prefix": "men"}, 
                    "entity_type": {"include": [], "prefix": "ent"}, 
                    #"mention_subtype": {"include": [], "prefix": "submen"},
                    #"numerus": {"include": [], "prefix": "num"},
                    #"specificity": {"include": [], "prefix": "spec"},
                    }, 
                "Value": {"tag": "val", "value_type": {"include": [], "prefix": "val"}}, 
                #"Descriptor": {"tag": "desc", "desc_type": {"include": [], "prefix": "desc"}}
            },
            #"merge_overlapping_desc_tags": False,  # if a desc tag covers the same span as another tag (Reference or Attribute usually), we put the desc tag as a mention subtype info to the entity annotation instead.
            #"depth_anno": None,  # annotate the depth, options: "None", "Binary" (doc vs ent level), "Ordinal"
            #"tag_anno": None, # annotate the parent tag, options: "None" or list of attributes that should be annotated (e.g. ["entity_type"])  
            "tag_granularity": 1,  # how granular should the label info be (TODO: Move to the instructions per tag type)
            #"require_parent": None # only add a span to the annotations if the parent of that span fits one or more requirements fits a key-value pair in the dict or give "doc" if flat annotations are wanted, "doc" may be included as a key in the dict so base spans are also included, None to disable filter TODO: Explain this better. It's now a list of OR-conditions
        }
    text, annotations = process_document("./outfolder_24_04_30/bhitz_HGB_Exp_9_183_HGB_1_215_063_015.xml", config)

    #annotations = process_document("../outfiles/admin_HGB_Exp_11_112_HGB_1_154_040_010.xml", config)
    
    #annotations = process_document("../outfiles/admin_008_HGB_1_024_074_020.xml", config)
    pp.pprint(annotations)

    #write_outfile("test.tsv", token_list, annotation_cols)