"""
Transforms Standard XML to an annotation tree, omitting token information.
Will probably be the base for a new to_inline script later on.
"""

from lxml import etree as et


def get_token_char_ids(root):
    tokens = root.findall("./Text/L/T")
    out_dict = {}
    start_id = 0
    document_text = []
    for token in tokens:
        end_id = start_id + len(token.text)
        out_dict[token.get("token_id")] = (str(start_id), str(end_id))
        start_id = end_id + 1
        document_text.append(token.text)
    return out_dict, " ".join(document_text)


def add_self_and_children(elem_id, parent, hierarchy, old_root, token_to_chars):
    elem = old_root.xpath(f".//*[@mention_id='{elem_id}' or @value_id='{elem_id}' or @desc_id='{elem_id}']")[0]

    # add char ids (additionally)
    try:
        elem.set("char_start", token_to_chars[elem.get("start")][0])
        elem.set("char_end", token_to_chars[str(int(elem.get("end"))-1)][1])
        if "head_start" in elem.attrib:
            elem.set("head_char_start", token_to_chars[elem.get("head_start")][0])
            elem.set("head_char_end", token_to_chars[str(int(elem.get("head_end"))-1)][1])
    except KeyError as e:
        print(e)
        print(et.tostring(elem))

    parent.append(elem)
    for h in hierarchy.findall(f"./H[@parent='{elem_id}']"):
        add_self_and_children(h.get("child"), elem, hierarchy, old_root, token_to_chars)


def transform(infile):
    old_root = et.parse(infile)
    hierarchy = old_root.find("./Hierarchy")
    token_to_chars, document_text = get_token_char_ids(old_root)

    new_root = et.Element("Document")
    new_root.set("document_text", document_text)
    for h in hierarchy.findall(f"./H[@parent='doc']"):
        add_self_and_children(h.get("child"), new_root, hierarchy, old_root, token_to_chars)

    return new_root


if __name__ == "__main__":
    import glob, pathlib, os

    infiles = "../outfiles/*.xml"
    outfolder = "../outfiles/anno_tree/"
    pathlib.Path(outfolder).mkdir(parents=True, exist_ok=True) 
    for infile in glob.glob(infiles):
        root = transform(infile)
        out_tree = et.ElementTree(root)
        outname = os.path.basename(infile)
        out_tree.write(os.path.join(outfolder, outname), xml_declaration=True, pretty_print=True, encoding="utf8")
        # print(et.tostring(root, pretty_print=True, encoding="utf8"))

