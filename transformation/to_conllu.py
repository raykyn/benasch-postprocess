"""
This script is an expansion of the to_iob script and transforms
the data into a format that flair can read with their RE_ENGLISH_CONLL04 class.
In this format, each sentence is preceded by metadata comments with
the text, sentence id and relations.
Relations are represented in the format <start-subj>;<end-subj>;<start-obj>;<end-obj>;<class> and separated by |-symbols.

This system will use only the heads of entities to ensure all entities in the sentence can be connected.
(this also of course means every mention has to contain a head)

In theory, this algorithm should also work to extract events

WORK IN PROGRESS
"""

import csv
try:
    import to_inline
except:
    import transformation.to_inline as to_inline
from lxml import etree as et
import pprint as pp


NODES_WITHOUT_HEADS = ["Value"]


def write_outstring(token_list, annotations, metadata) -> str:
    """
    Writes a string in the conllu format which Flair expects.

    This function gets called by the script to create the training data.
    """
    relation_string = "|".join([";".join([str(y) for y in x]) for x in metadata["relations"]])
    if relation_string:
        out_string = f"""# sentence_id = {metadata["sentence_id"]}\n# text = {metadata["text"]}\n# relations = {relation_string}\n"""
    else:
        out_string = f"""# sentence_id = {metadata["sentence_id"]}\n# text = {metadata["text"]}\n"""
    for idx, (token, anno) in enumerate(zip(token_list, annotations), 1):
        out_string += f"{idx} {token} {anno}\n"

    return out_string
    
   
def get_ancestors(node):
    """
    We build a list with all ancestors of the token.
    We ignore head elements for that purpose!
    """
    ancestors = []
    parent = node.getparent()
    while parent.tag != "Body":
        if parent.tag != "Head":
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
    

def resolve_lists(root, mention, mentions):
    conns = root.xpath(f"./Hierarchy/H[@parent={mention.get('mention_id')}]")
    conns = [root.find(f"./Mentions/*[@mention_id='{x.get('child')}']") for x in conns]
    for conn in conns:
        if conn.tag == "List":
            resolve_lists(root, conn, mentions)
        else:
            mentions.append(conn)

    
def get_relations(root):
    relation_elems = root.findall("./Relations/Relation")
    relations = []
    for relation in relation_elems:
        from_mentions = []
        to_mentions = []

        from_mention = root.find(f"./Mentions/*[@mention_id='{relation.get('from_mention')}']")
        to_mention = root.find(f"./Mentions/*[@mention_id='{relation.get('to_mention')}']")

        if from_mention is None or to_mention is None:  # this filters event relations for the moment
            if from_mention is None:
                print(f"WARING: Couldn't find mention with id {relation.get('from_mention')}")
            else:
                print(f"WARING: Couldn't find mention with id {relation.get('to_mention')}")
            continue

        # resolve lists
        if from_mention.tag == "List":
            resolve_lists(root, from_mention, from_mentions)
        else:
            from_mentions = [from_mention]

        if to_mention.tag == "List":
            resolve_lists(root, to_mention, to_mentions)
        else:
            to_mentions = [to_mention]
        
        for from_mention in from_mentions:
            if not from_mention.get("head_start"):  # skip mentions without head
                continue
            for to_mention in to_mentions:
                if not to_mention.get("head_start"):  # skip mentions without head
                    continue
                relations.append((
                    int(from_mention.get("head_start")) + 1, 
                    int(from_mention.get("head_end")),
                    int(to_mention.get("head_start")) + 1, 
                    int(to_mention.get("head_end")),
                    relation.get("rel_type")  # NOTE: could include further info such as tense here
                    ))
    return relations
    

def construct_metadata(docpath, id):
    """
    Creates a dict with elements
    Text, Sentence Id, Relations
    """
    root = et.parse(docpath).getroot()
    text = " ".join([t.text for t in root.findall(".//T")])

    relations = get_relations(root)

    return {"sentence_id": id, "text": text, "relations": relations}


def process_document(docpath, order):
    # first transform it to inline xml so we have an easy to process hierarchy
    texttree = to_inline.process_document(docpath)

    tokens = texttree.findall(".//T")
    # print([t.text for t in tokens])
    token_list = [t.text for t in tokens]
    ancestors_list = [get_ancestors(token) for token in tokens]

    mode, depth, ordered_tags = order["mode"], order["depth"], order["tags"]
    if "filter" in order:
        filter = order["filter"]
    else:
        filter = {}
    if "filter_strict" in order:
        filter_strict = order["filter_strict"]
    else:
        filter_strict = {}
    if "ignore_lists" in order and not order["ignore_lists"]:
        ignore_lists = False
    else:
        ignore_lists = True
    if "tag_granularity" in order:
        # tag granularity controls to which level tags are used
        # later i'd like also the option to set this per tag
        tag_granularity = order["tag_granularity"]
    else:
        tag_granularity = -1
    annotations = []

    # mode: decide if text is taken from the full node or only the head node
    # tags: decide what attribute is used to generate the annotation, can be multiple, which will be connected by a .
    # depth: decide how deep we want the annotation to go, not sure how depth > 1 will work yet.

    # we can now get all parents from a token to build a tag if depth is > 1
    # if depth == 1 (flat tags) we simply take the top tag

    for t, ancestors in zip(tokens, ancestors_list):
        if ignore_lists:
            ancestors = [a for a in ancestors if a.tag != "List"]
        if mode == "heads":
            ancestors = list(reversed(ancestors))
        tags = []
        to_filter = []
        p = None
        if mode == "heads":
            is_head = True if t.getparent().tag == "Head" or t.getparent().tag in NODES_WITHOUT_HEADS else False
            if not is_head:
                tags = "O"
                annotations.append(tags)
                continue
        for i in range(depth):
            if i >= len(ancestors):
                continue
            p = ancestors[i]
            tag_dict = {}
            filter_dict = {}
            for o_t in ordered_tags:
                # check if any of the tags do return something
                split_o_t = o_t.split("|")
                for o in split_o_t:
                    tag = p.get(o)
                    if tag != None:
                        break
                if tag != None:
                    if tag_granularity != -1:
                        tag = "_".join(tag.split("_")[:tag_granularity])
                    if ordered_tags[o_t] and tag not in ordered_tags[o_t]:
                        # only include the tags in the included_tags list
                        continue
                    tag_dict[o] = tag
            for f_t in filter:
                # check if any of the tags do return something
                f_t = f_t.split("|")
                for o in f_t:
                    tag = p.get(o)
                    if tag != None:
                        break
                if tag != None:
                    filter_dict[o] = tag
            if len(tag_dict) > 0:
                to_filter.append(filter_dict)
                tags.append(tag_dict)
        is_filtered = False
        if tags:
            for f in filter_strict:
                if f not in to_filter[0] or to_filter[0][f] not in filter_strict[f]:
                    is_filtered = True
                    break
            for f in filter:
                # NOTE: We only filter the first level of depth currently
                if f in to_filter[0] and to_filter[0][f] not in filter[f]:
                    is_filtered = True
                    break
            if is_filtered:
                tags = "O"
                annotations.append(tags)
                continue
        # attach B or I
        if tags:
            if check_if_first(t, p, True if mode == "heads" else False):
                attach = "B-"
            else:
                attach = "I-"
            tags = attach + ".".join([va for tag_dict in tags for ta, va in tag_dict.items()])
        else:
            tags = "O"
        annotations.append(tags)

    return token_list, annotations


if __name__ == "__main__":
    # example orders
    CONFIG = {
            "mode": "heads",
            "filter": {
            },
            "tags": {
                "entity_type": []
            },
            "depth": 1,
            "tag_granularity": 1
        }
    token_list, annotations = process_document("../outfiles/admin_011_HGB_1_028_032_029.xml", CONFIG)
    metadata = construct_metadata("../outfiles/admin_011_HGB_1_028_032_029.xml", 42)
    
    out = write_outstring(token_list, annotations, metadata)
    pp.pprint(out)
    #pp.pprint(list(zip(token_list, annotations)))
    #process_document("../outfiles/admin_008_HGB_1_024_074_020.xml", orders)

    #write_outfile("test.tsv", token_list, annotation_cols)