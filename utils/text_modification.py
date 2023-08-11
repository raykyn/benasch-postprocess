"""
The functions provided in this script serve to modify the CAS XMI
in a way to fix errors that were caused by erreanous layout analysis.
A full list of possible tags can be found in the annotation manual of BeNASch.
(and probably in the code documentation at some point)

Other tags may cover an htr.xy tag and will then be shortened by that amount.
An htr.xy tag which is not for deletion may contain tags which will be kept and for example moved with the marked span.
You may not overlap a tag into an htr.xy tag! There also should never be a reason you'd want to do that!
"""

import re


def find_textnode(in_root):
    text_node = in_root.find("./cas:Sofa", namespaces={"cas":"http:///uima/cas.ecore"})

    return text_node


def fit_annotations(in_root, node, begin, end, length):
    # modify the other tags to fit the new string
    for other in in_root.findall(".//custom:Span", namespaces={"custom":"http:///custom.ecore"}):
        if other == node:
            continue
        other_begin = int(other.get("begin"))
        other_end = int(other.get("end"))
        if other_begin >= end:
            new_begin = other_begin - length
            other.set("begin", str(new_begin))
        if other_end > end:
            new_begin = other_end - length
            other.set("end", str(new_begin))
        if other_begin >= begin and other_end <= end:
            # tag is inside deleted part, delete tag as well
            other.getparent().remove(other)

    for other in in_root.findall(".//custom:Relation", namespaces={"custom":"http:///custom.ecore"}):
        if other == node:
            continue
        other_begin = int(other.get("begin"))
        other_end = int(other.get("end"))
        if other_begin >= end:
            new_begin = other_begin - length
            other.set("begin", str(new_begin))
        if other_end > end:
            new_begin = other_end - length
            other.set("end", str(new_begin))
        if other_begin >= begin and other_end <= end:
            # tag is inside deleted part, delete tag as well
            other.getparent().remove(other)


def delete_text(in_root):
    htr_nodes = in_root.findall(".//custom:Span[@label='htr.delete']", namespaces={"custom":"http:///custom.ecore"})

    for node in htr_nodes:
        begin = int(node.get("begin"))
        end = int(node.get("end")) + 1
        length = end - begin
        
        # remove text
        text_node = find_textnode(in_root)
        document_text = text_node.get("sofaString")
        document_text = document_text[:begin] + document_text[end:]
        text_node.set("sofaString", document_text)

        fit_annotations(in_root, node, begin, end, length)

    return in_root


def move_line_end(in_root):
    """
    Move a certain string to a different position.
    Retain all tags that are included inside the htr string (move them with the htr string)
    """

    htr_nodes = in_root.findall(".//custom:Span[@label='htr.move-to-end']", namespaces={"custom":"http:///custom.ecore"})

    for node in htr_nodes:
        begin = int(node.get("begin"))
        end = int(node.get("end")) + 1  # the +1 let's us include the trailing whitespace
        length = end - begin

        # move text
        text_node = find_textnode(in_root)
        document_text = text_node.get("sofaString")
        tagged_text = document_text[begin:end]
        new_document_text = document_text[:begin] + document_text[end:] + tagged_text
        text_node.set("sofaString", new_document_text)

        # modify the other tags to fit the new string
        for other in in_root.findall(".//custom:Span", namespaces={"custom":"http:///custom.ecore"}):
            if other == node:
                continue
            other_begin = int(other.get("begin"))
            other_end = int(other.get("end"))
            if other_begin >= end and other_end >= end:
                # if tag is behind moved tag, it must shift forward
                new_begin = other_begin - length
                other.set("begin", str(new_begin))
                new_end = other_end - length
                other.set("end", str(new_end))
            elif other_begin >= begin and other_end <= end:
                # if a tag is contained inside the shifted part, it must move with the shifted path
                # NOT YET TESTED!
                relative_begin = other_begin - begin
                other_length = other_end - other_begin
                new_begin = len(document_text[:begin] + document_text[end:]) + relative_begin
                new_end = new_begin + other_length
                other.set("begin", str(new_begin))
                other.set("end", str(new_end))

        for other in in_root.findall(".//custom:Relation", namespaces={"custom":"http:///custom.ecore"}):
            if other == node:
                continue
            other_begin = int(other.get("begin"))
            other_end = int(other.get("end"))
            if other_begin > end and other_end > end:
                # if tag is behind moved tag, it must shift forward
                new_begin = other_begin - length
                other.set("begin", str(new_begin))
                new_begin = other_end - length
                other.set("end", str(new_begin))
            elif other_begin >= begin and other_end <= end:
                # if a tag is contained inside the shifted part, it must move with the shifted path
                # NOT YET TESTED!
                relative_begin = other_begin - begin
                other_length = other_end - other_begin
                new_begin = len(document_text[:begin] + document_text[end:]) + relative_begin
                new_end = new_begin + other_length
                other.set("begin", str(new_begin))
                other.set("end", str(new_end))

    return in_root


def move_line_top(in_root):
    htr_nodes = in_root.findall(".//custom:Span[@label='htr.move-to-top']", namespaces={"custom":"http:///custom.ecore"})

    if htr_nodes:
        print("WARNING: MOVING LINES TO TOP NOT YET IMPLEMENTED. IGNORING HTR ANNOTATION.")

    return in_root


def move_line_up(in_root):
    htr_nodes = in_root.findall(".//custom:Span[@label='htr.move-line-up']", namespaces={"custom":"http:///custom.ecore"})

    for node in htr_nodes:
        begin = int(node.get("begin"))
        end = int(node.get("end")) + 1  # the +1 let's us include the trailing whitespace
        length = end - begin

        # get line to swap with
        # TODO: instead of an exact match, we could simply look for the sentence element that matches most closely
        # which would be a bit more robust against misplaced annotations
        swap_line = in_root.find(f".//type5:Sentence[@end='{begin-1}']", namespaces={"type5":"http:///de/tudarmstadt/ukp/dkpro/core/api/segmentation/type.ecore"})
        if swap_line is None:
            print("WARNING: When trying to move a line up, no previous line matched the boundary. Did you mark the whole line?")
            continue
        swap_begin = int(swap_line.get("begin"))
        swap_end = int(swap_line.get("end")) + 1
        swap_length = swap_end - swap_begin

        # move text
        text_node = find_textnode(in_root)
        document_text = text_node.get("sofaString")
        tagged_text = document_text[begin:end]
        swap_text = document_text[swap_begin:swap_end]
        new_document_text = document_text[:swap_begin] + tagged_text + swap_text + document_text[end:]
        text_node.set("sofaString", new_document_text)

        

        # modify the other tags to fit the new string
        for other in in_root.findall(".//custom:Span", namespaces={"custom":"http:///custom.ecore"}):
            if other == node:
                continue
            other_begin = int(other.get("begin"))
            other_end = int(other.get("end"))
            if other_begin >= swap_begin and other_end <= swap_end:
                new_begin = other_begin + length
                other.set("begin", str(new_begin))
                new_end = other_end + length
                other.set("end", str(new_end))
            elif other_begin >= begin and other_end <= end:
                new_begin = other_begin - swap_length
                other.set("begin", str(new_begin))
                new_end = other_end - swap_length
                other.set("end", str(new_end))

        for other in in_root.findall(".//custom:Relation", namespaces={"custom":"http:///custom.ecore"}):
            if other == node:
                continue
            other_begin = int(other.get("begin"))
            other_end = int(other.get("end"))
            if other_begin >= swap_begin and other_end <= swap_end:
                new_begin = other_begin + length
                other.set("begin", str(new_begin))
                new_end = other_end + length
                other.set("end", str(new_end))
            elif other_begin >= begin and other_end <= end:
                new_begin = other_begin - swap_length
                other.set("begin", str(new_begin))
                new_end = other_end - swap_length
                other.set("end", str(new_end))

    return in_root


def move_line_down(in_root):
    htr_nodes = in_root.findall(".//custom:Span[@label='htr.move-line-down']", namespaces={"custom":"http:///custom.ecore"})

    if htr_nodes:
        print("WARNING: MOVING LINES DOWN NOT YET IMPLEMENTED. IGNORING HTR ANNOTATION.")
        # this should be pretty easy, just take the above function and tweak it so it works.

    return in_root


def remove_headers(in_root):
    """
    Very project-specific. We marked document headers with STARTDATE and ENDDATE.
    This function removes lines that are marked with these strings.
    We also need to remove all tags that are inside these strings.
    """
    text_node = find_textnode(in_root)
    document_text = text_node.get("sofaString")
    to_remove = re.finditer(r"(STARTDATE(.*?)ENDDATE)", document_text)
    for r in reversed(list(to_remove)):
        #print(r)
        start = r.start()
        end = r.end() + 1
        length = end - start
        #print(length)

        document_text = text_node.get("sofaString")
        document_text = document_text[:start] + document_text[end:]
        text_node.set("sofaString", document_text)

        # modify the other tags to fit the new string
        # TO TEST: Not sure if the sentence movement will work perfect in some edge cases.
        for other in in_root.findall(".//type5:Sentence", namespaces={"type5":"http:///de/tudarmstadt/ukp/dkpro/core/api/segmentation/type.ecore"}):
            other_begin = int(other.get("begin"))
            other_end = int(other.get("end"))
            if other_begin >= end:
                new_begin = other_begin - length
                other.set("begin", str(new_begin))
                new_end = other_end - length
                other.set("end", str(new_end))

        for other in in_root.findall(".//custom:Span", namespaces={"custom":"http:///custom.ecore"}):
            other_begin = int(other.get("begin"))
            other_end = int(other.get("end"))
            """
            if other_begin >= end:
                new_begin = other_begin - length
                other.set("begin", str(new_begin))
                new_end = other_end - length
                other.set("end", str(new_end))
            """
            if other_begin >= end:
                new_begin = other_begin - length
                other.set("begin", str(new_begin))
            if other_end > end:
                new_end = other_end - length
                other.set("end", str(new_end))
            if other_begin >= start and other_end <= end:
                # tag is inside deleted part, delete tag as well
                other.getparent().remove(other)

        for other in in_root.findall(".//custom:Relation", namespaces={"custom":"http:///custom.ecore"}):
            other_begin = int(other.get("begin"))
            other_end = int(other.get("end"))
            if other_begin >= end:
                new_begin = other_begin - length
                other.set("begin", str(new_begin))
            if other_end > end:
                new_begin = other_end - length
                other.set("end", str(new_begin))
            if other_begin >= start and other_end <= end:
                # tag is inside deleted part, delete tag as well
                other.getparent().remove(other)

    return in_root


def modify_text(in_root):
    in_root = delete_text(in_root)

    in_root = remove_headers(in_root)
    in_root = move_line_end(in_root)
    in_root = move_line_top(in_root)
    in_root = move_line_up(in_root)
    in_root = move_line_down(in_root)

    return in_root