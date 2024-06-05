# Read XMI standoff annotation file and convert it into a XML file similar to TEI with standoff annotation for relationships
# Export the files from Inception as UIMA CAS XMI (XML 1.1) and put them (unzipped!) in the folder named unter "infiles"
# Important: This code assumes no intersecting entities!

import glob
import json
import os
import re
from lxml import etree as et
from utils.text_modification import modify_text
from utils.small_corrections import small_corrects
import pathlib
import pprint as pp
from collections import defaultdict


def get_node_priority(node):
    """
    This makes sure that when sorting the spans, desc-Spans will be processed BEFORE 
    mentions, values, etc. 
    This is relevant especially for desc-spans that completely overlap with an
    entity mention or value, such as is often the case for desc.owner.

    This function may need expansion later on if more such cases exist.
    """
    try:
        l = node.get("label").lower().split(".")[0]
    except:
        return 1
    if l == "desc":
        return 0
    #elif l == "head":
    #    return 2
    else:
        return 1
    

def convert_char_to_token_idx(start_index_dict, end_index_dict, start, end, entity):
    # transform character index to token index
    token_start = start_index_dict[start]
    try:
        token_end = end_index_dict[end]
    except KeyError:
        # Inception performs an implicit tokenization, which allows annotations
        # to be set outside our own preprocessing. This can lead to annotations
        # ending inside tokens as defined by our preprocessing/system
        # to circumvent this problem, we simply stretch the tag to the end of the token
        while end not in end_index_dict:
            end += 1
        token_end = end_index_dict[end]
        
        print(f"WARNING: An annotation ended inside a token. Check this error manually for annotation with id {entity.get('{http://www.omg.org/XMI}id')}!")
    return token_start, token_end


def create_node_tree(in_root, document_text, start_index_dict, end_index_dict):
    """
    This node tree is mostly just as a help, but the code may probably easily be adopted to port everything to a TEI-format.
    """
    spans = in_root.findall(".//custom:Span", namespaces={"custom":"http:///custom.ecore"})
    # note which entity and which tag, start or end, needs to be inserted at this point
    sorted_spans = []
    for ent in spans:
        sorted_spans.append((ent, int(ent.get("begin")), int(ent.get("end")), get_node_priority(ent)))
    sorted_spans.sort(key=lambda x: (x[1], -x[2], x[3]))
    work_root = et.Element("XML", nsmap={"custom":"http:///custom.ecore", "cas":"http:///uima/cas.ecore"})
    parent_node = work_root
    for entity, start, end, _ in sorted_spans:
        # classify if span is entity, attribute or description
        label = entity.get('label')
        if label == None:
            if entity.get("Role"):
                # is a freetext role argument, no need to report that in the log
                pass
            else:
                print(f"WARNING: Empty Label in node with id {entity.get('{http://www.omg.org/XMI}id')}!")
            label = ""
        label = label.lower().split(".")
        span_type = ""
        if label[0] in SCHEMA_INFO["mention_classes"]:
            span_type = "ent"
            if label[0] == "unk":
                label = ["unk", "unk"]
        elif label[0] == "lst":
            span_type = "lst"
        elif label[0] == "att":
            span_type = "att"
        elif label[0] == "desc":
            span_type = "desc"
        elif label[0] == "head":
            span_type = "head"
        elif label[0] in SCHEMA_INFO["value_tags"]:
            span_type = "value"
        elif label[0] in SCHEMA_INFO["other_tags"]:
            # TODO: Implement deletion and moving by htr tags
            if label[0] == "unclear":
                print(f"WARNING: Unclear Label encountered in node with id {entity.get('{http://www.omg.org/XMI}id')}!")
            span_type = ""
            continue
        elif label[0].startswith("evspan"):
            span_type = "evspan"
        elif label[0].startswith("ev"):
            span_type = "evtrigger"
        elif label[0] == "" and entity.get("Role"):
            span_type = "freetext"
        else:
            print(f"ERROR: Unrecognized Span Label '{label[0]}' in annotation with id {entity.get('{http://www.omg.org/XMI}id')}!")
            continue
        label = ".".join(label)

        if entity.get("Role") is not None:
            role = entity.get("Role")
        elif entity.get("role") is not None:
            role = entity.get("Role")
        else:
            role = ""

        token_start, token_end = convert_char_to_token_idx(start_index_dict, end_index_dict, start, end, entity)

        # We need to check all parent nodes above if they contain the current node
        # NOTE: We increase token_end by 1 to match common span annotation schemes (which usually mark a span of length 1 as x to x+1)
        while(parent_node != work_root):
            if token_end <= int(parent_node.get("end"))-1:
                current_node = et.SubElement(parent_node, "Entity", id=entity.get("{http://www.omg.org/XMI}id"), span_type=span_type, label=label, role=role, start=str(token_start), end=str(token_end+1), text=document_text[start:end])
                break
            else:
                parent_node = parent_node.getparent()
        else:
            current_node = et.SubElement(work_root, "Entity", id=entity.get("{http://www.omg.org/XMI}id"), span_type=span_type, label=label, role=role, start=str(token_start), end=str(token_end+1), text=document_text[start:end])
        parent_node = current_node

    # We get relations from three sources: relation layer, att and desc
    relations = in_root.findall(".//custom:Relation", namespaces={"custom":"http:///custom.ecore"})
    for relation in relations:
        if relation.get("label") is None:
            print(f"ERROR: Missing label for a relation {relation.get('{http://www.omg.org/XMI}id')}!")
            continue
        else:
            label = relation.get("label")
        current_node = et.SubElement(
            work_root, 
            "Relation", 
            id=relation.get("{http://www.omg.org/XMI}id"), 
            label=label,
            from_entity=relation.get("Governor"),
            to_entity=relation.get("Dependent"),
            )

    return work_root


def process_others(other_info, mention_id):
    numerus = SCHEMA_INFO["other_fields"]["numerus"][0]
    spec = SCHEMA_INFO["other_fields"]["specificity"][0]
    tempus = SCHEMA_INFO["other_fields"]["tense"][0]

    for o in other_info:
        if o in SCHEMA_INFO["other_fields"]["numerus"]:
            numerus = o
        elif o in SCHEMA_INFO["other_fields"]["specificity"]:
            spec = o
        elif o in SCHEMA_INFO["other_fields"]["tense"]:
            tempus = o
        elif o == "":
            # someone put two dots by mistake instead of one
            pass
        elif o not in SCHEMA_INFO["other_fields"]["other"]:
            print(f"ERROR: Unrecognized information {o} in Mention Debug Id {mention_id}. Ignoring it.")

    return numerus, spec, tempus

def apply_conversions(entity_type):
    for o, r in SCHEMA_INFO["conversions"]["entity_types"].items():
        entity_type = re.sub(o, r, entity_type)

    return entity_type

old_to_new_ids = {}
mention_subtypes = set()
desc_types = set()

def get_and_validate_parent_entity_type(parent, entity):
    # inherit entity type from parent
    try:
        label = parent.get('label').lower()
    except AttributeError as e:
        if parent.tag == "XML":
            print(f"ERROR: Found Attribute with mention id {entity.get('id')} that is not child of another mention. Ignoring the attribute...")
            return None
        else:
            raise e
    label = label.split(".")
    if label[0] == "lst":
        # if parent is a list, we need to get the entity classification
        # from one of the REF-child elements
        child = parent.find("./Entity[@span_type='ent']")
        if child == None:
            print("WARNING: Could not get entity class for attribute because LST-Element did not contain any REF-Elements! Setting entity class to UNK.")
            entity_type = "unk"
        else:
            entity_type = child.get('label').lower().split(".")[1]
    elif label[0] == "head":
        print(f"ERROR: Attribute with id {entity.get('id')} has a head-Element as parent. \
Using parent of head instead as parent of Attribute. Make sure to fix this as heads should contain further spans!")
        entity_type = get_and_validate_parent_entity_type(parent.getparent(), entity)
    else:
        entity_type = label[1]

    entity_type = apply_conversions(entity_type)
    return entity_type


def pro_coref_get_entity_type(work_root, coref, mention_type):
    parent = work_root.find(f".//Entity[@id='{coref.get('to_entity')}']")
    if parent.get("span_type") == "head":
        parent = parent.getparent()
    while parent.get("label").split(".")[0] in ["pro", "self"] and len(parent.get("label").split(".")) == 1:
        # we keep searching until we find a non-abbreviated or non-PRO mention
        coref = work_root.find(f".//Relation[@from_entity='{parent.get('id')}'][@label='coref']")
        parent = work_root.find(f".//Entity[@id='{coref.get('to_entity')}']")
        # a catch in case a coref was placed to a head instead of the parent tag
        if parent.get("span_type") == "head":
            parent = parent.getparent()
    # when we find the parent, we copy its entity type and ordinality, if necessary
    parentlabel = parent.get("label").split(".")
    if parentlabel[0] == "lst":
        first_child_label = parent.find("./Entity[@span_type='ent']").get("label").split(".")
        mention_type = mention_type
        other_types = ["grp"]  # lists are always groups of entities
        if first_child_label[0] in ["pro", "self"] and len(first_child_label) == 1:
            children = [c for c in parent.findall("./Entity[@span_type='ent']") if len(c.get("label").split(".")) > 1]
            if children:
                entity_type = children[0].get("label").split(".")[1]
            else:
                firstchild = parent.find('./Entity[@span_type="ent"]')
                coref = work_root.find(f".//Relation[@from_entity='{firstchild.get('id')}'][@label='coref']")
                if coref is None:
                    entity_type = "unk"
                else:
                    _, entity_type, _ = pro_coref_get_entity_type(work_root, coref, mention_type)
                # TODO: Test if this works, if we ever need this usecase
                #print("WARNING: A coreference to a list was encountered only containing PROs with coreferences. The resolution of this is yet to be implemented. Entity type of the list will be set to UNK.")
        else:
            entity_type = first_child_label[1]
    else:
        mention_type, entity_type = mention_type, parentlabel[1]
        parent_other = parentlabel[2:] if parentlabel[0] == "nam" else parentlabel[3:]
        other_types = []
        for el in parent_other:
            if el in SCHEMA_INFO["other_fields"]["numerus"]:
                other_types = [el]
                break
    
    entity_type = apply_conversions(entity_type)
    return mention_type, entity_type, other_types


def check_and_resolve_head_conflicts(entity, head, mention_id):
    """
    Check if a head overlaps with other child elements of an entity.
    I'll work through specific error scenarios as they come up:

    1) head contains an attribute that should actually be appended to the parent.
        => Shorten head to not contain the attribute anymore
        (this assumes also that the attribute is at the beginning or end of the head)

    Maybe we move these to a separate error correction script at some point
    """
    if head is None:
        return
    # Scenario 1
    if len(head) > 0:
        # heads should not contain children!
        for child in head:
            # Possibly limit to specific children?
            if child.get("start") == head.get("start") and int(child.get("end")) < int(head.get("end")):
                head.set("start", child.get("end"))
            elif child.get("end") == head.get("end") and int(child.get("start")) > int(head.get("start")):
                head.set("end", child.get("start"))
            print(f"Warning! Shortened head of mention with id {mention_id} to make space for other spans.")


def write_entities(out_root, work_root):
    """
    Write all entity mentions for Lists, References and Attributes.

    Adds hierarchical relations (which mentions are contained in which other mentions) to the Hierarchy element.
    """

    global old_to_new_ids

    old_to_new_ids = {}

    entities_node = et.SubElement(out_root, "Mentions")
    token_list = out_root.findall(".//T")

    ### LISTS ###
    for entity in work_root.findall(".//Entity[@span_type='lst']"):

        mention_id = len(old_to_new_ids)
        old_to_new_ids[entity.get("id")] = mention_id

        label = entity.get("label").lower().split(".")
        if len(label) > 1:
            subtype = label[1]
        else:
            subtype = ""

        # get all child entity types
        child_entities = entity.findall("./Entity[@span_type='ent']")
        entity_types = []
        for child in child_entities:
            label = child.get("label").split(".")
            if label[0] not in ["pro", "self"] or len(label) > 1:
                entity_types.append(label[1])
            else:
                coref = work_root.find(f".//Relation[@from_entity='{child.get('id')}'][@label='coref']")
                if coref is None:
                    entity_types.append("unk")
                else:
                    mention_type, entity_type, other_types = pro_coref_get_entity_type(work_root, coref, label[0])
                    entity_type = apply_conversions(entity_type)
                    entity_types.append(entity_type)
        entity_types = ",".join(entity_types)

        et.SubElement(entities_node, 
            "List",
            mention_id=str(mention_id), 
            subtype=subtype,
            entity_types=entity_types,
            start=entity.get("start"),
            end=entity.get("end"),
            )
    
    ### REFERENCES ###
    for entity in work_root.findall(".//Entity[@span_type='ent']"):
        label = entity.get('label').lower()
        label = label.split(".")

        mention_subtype = ""

        if label[0] == "nam":
            mention_type, entity_type = label[:2]
            other_types = label[2:]
        elif label[0] in ["pro", "self"] and len(label) == 1:
            # this is the shortcut to get the information from a coreference.
            # first find the relevant relation/coref, then the relevant mention
            coref = work_root.find(f".//Relation[@from_entity='{entity.get('id')}'][@label='coref']")
            if coref is None:
                print(f"ERROR: PRO mention with id {entity.get('id')} encountered with no further tags, maybe a forgotten coreference is the problem? Setting entity_type to UNK to skip.")
                mention_type, entity_type = label[0], "unk"
            else:
                mention_type, entity_type, other_types = pro_coref_get_entity_type(work_root, coref, label[0])
        else:
            mention_type, entity_type = label[:2]
            if len(label) > 2:
                mention_subtype = label[2]
                other_types = label[3:]
            else:
                other_types = []

        if mention_subtype:
            mention_subtypes.add((
                mention_subtype,
                entity_type
            ))

        # Process other types
        numerus, spec, _ = process_others(other_types, entity.get("id"))
        entity_type = apply_conversions(entity_type)

         # TODO: Decide if this reference is new or carries a coreference to a previous entity
        mention_id = len(old_to_new_ids)
        old_to_new_ids[entity.get("id")] = mention_id

        head_elem = entity.find("Entity[@label='head']")
        check_and_resolve_head_conflicts(entity, head_elem, mention_id)
        if head_elem == None and len(entity) == 0:
            # Implizierter Head
            # is added for the full span if no children exist in the span
            # print(f"Warning: Implizierter Head bei {entity.get('id')}.")
            head_start = entity.get("start")
            head_end = entity.get("end")
        elif head_elem == None:
            # Implizierter Head - Unsicher
            # is added at the first token which is not part of another span
            print(f"Warning: Unsicherer implizierter Head bei Mention ID {mention_id}.")
            for token in range(int(entity.get("start")), int(entity.get("end"))):
                for child in entity:
                    if token in list(range(int(child.get("start")), int(child.get("end")))):
                        break
                else:
                    head_start = str(token)
                    head_end = str(token + 1)
                    break
            else: # no space for a implicit head bc filled with sub-spans
                head_start = ""
                head_end = ""
        else:
            head_start = head_elem.get("start")
            head_end = head_elem.get("end")

        

        et.SubElement(entities_node, 
            "Reference",
            mention_id=str(mention_id), 
            mention_type=mention_type,
            mention_subtype=mention_subtype,
            entity_type=entity_type,
            numerus=numerus,
            specificity=spec,
            start=entity.get("start"),
            end=entity.get("end"),
            head_start=head_start,
            head_end=head_end,
            head_text=" ".join([t.text for t in token_list[int(head_start):int(head_end)]]) if head_start else ""
            )
    
    for entity in work_root.findall(".//Entity[@span_type='att']"):

        parent = entity.getparent()
        entity_type = get_and_validate_parent_entity_type(parent, entity)
        if entity_type == None:
            continue

        # get own information
        label = entity.get('label').lower()
        label = label.split(".")

        mention_type = "nom" if "pro" not in label[2:] else "pro"
        mention_subtype = label[1]
        if mention_subtype == "alias":
            mention_type = "nam"
        numerus, spec, _ = process_others(label[2:], entity.get("id"))
        entity_type = apply_conversions(entity_type)

        mention_subtypes.add((
            mention_subtype,
            entity_type
        ))

        head_elem = entity.find("Entity[@label='head']")
        check_and_resolve_head_conflicts(entity, head_elem, mention_id)
        if head_elem == None and len(entity) == 0:
            # Implizierter Head
            # is added for the full span if no children exist in the span
            # print(f"Warning: Implizierter Head bei {entity.get('id')}.")
            head_start = entity.get("start")
            head_end = entity.get("end")
        elif head_elem == None:
            # Implizierter Head - Unsicher
            # is added at the first token which is not part of another span
            print(f"Warning: Unsicherer implizierter Head bei Mention ID {mention_id}.")
            for token in range(int(entity.get("start")), int(entity.get("end"))):
                for child in entity:
                    if token in list(range(int(child.get("start")), int(child.get("end")))):
                        break
                else:
                    head_start = str(token)
                    head_end = str(token + 1)
                    break
            else: # no space for a implicit head bc filled with sub-spans
                head_start = ""
                head_end = ""
        else:
            head_start = head_elem.get("start")
            head_end = head_elem.get("end")

        # TODO: Give this the reference id of the parent element
        mention_id = len(old_to_new_ids)
        old_to_new_ids[entity.get("id")] = mention_id

        et.SubElement(entities_node, 
            "Attribute",
            mention_id=str(mention_id), 
            mention_type=mention_type,
            mention_subtype=mention_subtype,
            entity_type=entity_type,
            numerus=numerus,
            specificity=spec,
            start=entity.get("start"),
            end=entity.get("end"),
            head_start=head_start,
            head_end=head_end,
            head_text=" ".join([t.text for t in token_list[int(head_start):int(head_end)]]) if head_start else ""
            )
        
    description_node = et.SubElement(out_root, "Descriptors")    
    for desc in work_root.findall(".//Entity[@span_type='desc']"):
        label = desc.get('label').lower()
        label = label.split(".")
        try:
            desc_type = label[1]
        except IndexError as e:
            if len(label) == 1:
                print(f"WARNING: Missing desc-Categorization in description with id {desc.get('id')}.\
                     Setting it as UNK for the moment.")
                desc_type = "unk"
                desc.set('label', desc_type + ".unk")

        desc_id = len(old_to_new_ids)
        old_to_new_ids[desc.get("id")] = desc_id

        desc_types.add((
            desc_type,
        ))
        et.SubElement(description_node, 
            "Descriptor",
            desc_id=str(desc_id), 
            desc_type=desc_type,
            start=desc.get("start"),
            end=desc.get("end"),
            text=" ".join([t.text for t in token_list[int(desc.get("start")):int(desc.get("end"))]])
            )
        

def write_values(out_root, work_root):
    global old_to_new_ids

    value_node = et.SubElement(out_root, "Values")
    token_list = out_root.findall(".//T")
    for value in work_root.findall(".//Entity[@span_type='value']"):
        value_id = len(old_to_new_ids)
        old_to_new_ids[value.get("id")] = value_id
        et.SubElement(value_node, 
            "Value",
            value_id=str(value_id),
            value_type=value.get("label"),
            start=value.get("start"),
            end=value.get("end"),
            text=" ".join([t.text for t in token_list[int(value.get("start")):int(value.get("end"))]])
            )


def write_relations(out_root, work_root):
    relations_node = et.SubElement(out_root, "Relations") 

    # First, the easy ones that were tagged as relations
    for relation in work_root.findall(".//Relation"):
        label = relation.get("label").lower().split(".")
        rel_type = label[0]
        _, _, tense = process_others(label[1:], relation.get("id"))
        try:
            et.SubElement(relations_node, 
                "Relation",
                rel_type=rel_type,
                tense=tense,
                from_mention=str(old_to_new_ids[relation.get("from_entity")]),
                to_mention=str(old_to_new_ids[relation.get("to_entity")]),
                )
        except KeyError as e:
            print(f"ERROR: When trying to write a relation, a mention id could not be found: {e}. Maybe the relation was connected to an invalid annotation such as a 'desc.xy'?")
        
    for entity in work_root.findall(".//Entity[@span_type='ent']"):
        label = entity.get('label').lower()
        label = label.split(".")
        if label[0] == "nam" or len(label) < 3:
            continue
        rel_type = label[2]
        _, _, tense = process_others(label[3:], entity.get("id"))

        # check if an entity is included in this span, then this is what the relationship refers to
        # if there is no entity included, it's not a relationship
        child_entities = entity.findall("./Entity[@span_type='ent']")
        child_entities.extend(entity.findall("./Entity[@span_type='lst']"))
        
        for child_entity in child_entities:
            try:
                et.SubElement(relations_node, 
                    "Relation",
                    rel_type=rel_type,
                    tense=tense,
                    from_mention=str(old_to_new_ids[entity.get("id")]),
                    to_mention=str(old_to_new_ids[child_entity.get("id")]),
                    )
            except KeyError as e:
                print(f"ERROR: When trying to write a relation, a mention id could not be found: {e}. Maybe the relation was connected to an invalid annotation such as a 'desc.xy'?")
    
    # now the implied relations from att and desc (and entities which are PRO and NOM possibly!)
    # basically, if there is another mention inside an att or a desc, we have a relation between the original mention and the one inside
    for entity in work_root.findall(".//Entity[@span_type='att']"):
        label = entity.get('label').lower()
        label = label.split(".")
        rel_type = label[1]
        _, _, tense = process_others(label[2:], entity.get("id"))

        # check if an entity is included in this span, then this is what the relationship refers to
        # if there is no entity included, it's not a relationship
        child_entities = entity.findall("./Entity[@span_type='ent']")
        child_entities.extend(entity.findall("./Entity[@span_type='lst']"))

        for child_entity in child_entities:
            try:
                et.SubElement(relations_node, 
                    "Relation",
                    rel_type=rel_type,
                    tense=tense,
                    from_mention=str(old_to_new_ids[entity.get("id")]),
                    to_mention=str(old_to_new_ids[child_entity.get("id")]),
                    )
            except KeyError as e:
                print(f"ERROR: When trying to write a relation, a mention id could not be found: {e}. Maybe the relation was connected to an invalid annotation such as a 'desc.xy'?")
    
        # also, an attribute always features a coreference with its parent element
        # while this is also represented in the Hierarchy element, we add this redundancy for clearness
        try:
            et.SubElement(relations_node, 
                "Relation",
                rel_type="att-coref",
                tense="pres",
                from_mention=str(old_to_new_ids[entity.get("id")]),
                to_mention=str(old_to_new_ids[entity.getparent().get("id")]),
                )
        except KeyError as e:
            print(f"ERROR: When trying to write a relation, a mention id could not be found: {e}. Maybe the relation was connected to an invalid annotation such as a 'desc.xy'?")

    # desc work almost the same as att, but the connected id is that of the parent element instead
    for descriptor in work_root.findall(".//Entity[@span_type='desc']"):
        parent = descriptor.getparent()
        if parent.tag == "XML":
            print(f"ERROR: A Desc-Span is standing independently. Check span id {descriptor.get('id')}. Skipping this potential relation.")
            continue
        label = descriptor.get('label').lower()
        label = label.split(".")
        rel_type = label[1]
        _, _, tense = process_others(label[2:], descriptor.get("id"))

        # check if an entity is included in this span, then this is what the relationship refers to
        # if there is no entity included, it's not a relationship
        child_entities = descriptor.findall("./Entity[@span_type='ent']")
        child_entities.extend(descriptor.findall("./Entity[@span_type='lst']"))
        
        for child_entity in child_entities:
            try:
                et.SubElement(relations_node, 
                    "Relation",
                    rel_type=rel_type,
                    tense=tense,
                    from_mention=str(old_to_new_ids[parent.get("id")]),
                    to_mention=str(old_to_new_ids[child_entity.get("id")]),
                    )
            except KeyError as e:
                print(f"ERROR: When trying to write a relation, a mention id could not be found: {e}. Maybe the relation was connected to an invalid annotation such as a 'desc.xy'?")


def extract_role_field(node):
    """
    At the moment, we accept . and : to separate
    role ids. This behaviour will likely change in
    the future.
    Semikolons split multiple roles!
    """
    rolefield = node.get("role")
    if not rolefield:
        return None
    out = []
    for role in rolefield.split(";"):
        role = role.split(".")
        if len(role) == 1:
            out.append({"type": role[0], "id": [""]})
        elif len(role) == 2:
            if ":" in role[1]:
                roleid = role[1].split(":")
                out.append({"type": role[0], "id": roleid})
            else:    
                roleid = list(role[1])
                out.append({"type": role[0], "id": roleid})
        else:
            out.append({"type": role[0], "id": role[1:]})
    return out


def update_eventspan_length(event, events_node):
    for subevent in event.findall("./Subevent"):
        for role in subevent.findall("./Role"):
            ref = role.get("ref")
            corr = events_node.find("./Event[@event_id='" + ref + "']")
            if corr is not None:
                update_eventspan_length(corr, events_node)
                event.set("start", str(min([int(event.get("start")), int(corr.get("start"))])))
                event.set("end", str(max([int(event.get("end")), int(corr.get("end"))])))


def write_events(out_root, work_root, document_text, start_index_dict, end_index_dict):
    """
    Rewrite this code, but important changes:
    - the trigger is not the important part, but instead the event-span
    - if no eventspan is annotated, but a trigger is, the evspan is extrapolated
    - event-spans, trigger and roles do not necessarily need an id if only 1 event with no subevents is in that annotation level
    """

    def solve_list(list_elem, collector, prev_roles, transfer_roles=False):
        """
        spans inside lists may have relevant roles
        so we need to also look through lists and return all their children
        recursively. Also give all roles of a list to all its children
        """
        if list_elem.get("role"):
            prev_roles.append(list_elem.get("role")) 
        for child in list_elem:
            if child.get("span_type") in ["ent", "val"]:
                if transfer_roles and list_elem.get("role"):
                    if child.get("role"):
                        child.set("role", child.get("role") + ";".join(prev_roles))
                    else:
                        child.set("role", ";".join(prev_roles))
                collector.append(child)
            elif child.get("span_type") == "lst":
                solve_list(child, collector, prev_roles=prev_roles.copy())

    # move all roles from list elements to their children
    for list_elem in work_root.xpath(".//Entity[@span_type='lst']"):
        solve_list(list_elem, [], [], transfer_roles=True)

    global old_to_new_ids

    events_node = et.SubElement(out_root, "Events")

    events = []

    # an event is either indicated by an eventspan or a trigger
    evspans = work_root.xpath(".//Entity[@span_type='evspan']")
    events.extend(evspans)

    # evspans may be indicated by a Enity mentions, we need to check those too, together with a settings file
    # to define their exact behaviour TODO LATER
    # if a trigger is inside a desc, it always implies that the desc is the eventspan?
    possible_evspans = work_root.xpath(".//Entity[@span_type='ent' or @span_type='att' or @span_type='desc']")
    for possible in possible_evspans:
        # this only works for desc and att-pro. For refs and att-nom the trigger is usually the head.
        # so those will only work with a settings file.
        triggers = possible.findall("./Entity[@span_type='evtrigger']")
        # backup if multiple triggers are in the same desc-span
        valid_triggers = [tr for tr in triggers if tr.get("role") == ""]
        if len(valid_triggers) == 1:
            events.append(possible)
        elif len(valid_triggers) > 1:
            print("WARNING: Multiple event-trigger were inside an event-span or a span which can imply an event-span (e.g. desc). That span is likely not schema-valid.")

    # a trigger will only indicate its own event if an eventspan is not present
    possible_evtriggers = work_root.xpath(".//Entity[@span_type='evtrigger']")
    for tr in possible_evtriggers:
        parent = tr.getparent()
        # Falls das Parent-Elem kein evspan ist, darf es nicht auch in den Events sein! sonst muss angenommen werden, dass der
        # Trigger einfach dort zu gehört! (TODO: auch refs und att-nom haben keine Trigger und sollten so behandelt werden)
        if parent.get("span_type") != "evspan" and parent not in events:
            events.append(tr)
        # Falls das Parent-Elem eine evspan ist, müssen wir die event-id überprüfen und nur wenn es dieselbe ist,
        # handelt es sich um dasselbe event (und der Trigger wird nicht genommen)
        elif parent.get("span_type") == "evspan":
            if len(tr.get("label").split(".")[0]) < 3:
                if len(parent.get("label").split(".")[0]) >= 3:
                    events.append(tr)
                else:
                    # if both have no id, they belong together
                    continue
            else:
                parent_id = parent.get("label").split(".")[0][6:]
                trigger_id = tr.get("label").split(".")[0][2:]
                if parent_id != trigger_id:
                    events.append(tr)

    # we need already here to assign each event a unique id for the standard-xml
    old_to_new_event_ids = {}  # maybe merge with old_to_new_ids?
    for i, event in enumerate(events, len(old_to_new_ids)):
        old_to_new_ids[event.get("id")] = str(i)
        old_to_new_event_ids[event.get("id")] = str(i)

    # collect all elements with roles so we can later detect which ones didnt get an event
    elems_with_roles = work_root.xpath(".//*[string-length(@role) > 0]")

    for event in events:
        # if the event was indicated by a trigger, we need to first create the eventspan
        if event.get("span_type") == "evtrigger":
            event_info = event.get("label").split(".")
            event_id, event_type, other_info = event_info[0], event_info[1], event_info[2:]
            # look at all sibling nodes and check their role id (if present)
            # then set the event span ranging from the start of the first role to the end of the last role
            # or trigger
            if len(event_id) < 3:
                event_id = ""
            else:
                event_id = event_id[2:]  # ev0 ==> 0
            valid_siblings = [event]
            roles = []
            candidates = []
            for sibling in event.getparent():
                if sibling.get("span_type") == "lst":
                    collector = []
                    solve_list(sibling, collector, [])
                    candidates.extend(collector)
                else:
                    candidates.append(sibling)
            
            for sibling in candidates:
                roleinfos = extract_role_field(sibling)
                if roleinfos is not None:
                    for roleinfo in roleinfos:
                        if not event_id or roleinfo["id"][0] == event_id:
                            valid_siblings.append(sibling)
                            roles.append((sibling, roleinfo))
            # if no event_id was given and other triggers were present (which should not happen!)
            # we look for the other triggers and remove all of their roles from our valid siblings
            # and roles but we only do this if that other trigger has no role in our event!
            if not event_id:
                other_triggers = [s for s in event.getparent() if s.get("span_type") == "evtrigger" and extract_role_field(s) is None and s != event]
                for ot in other_triggers:
                    ot_info = ot.get("label").split(".")
                    ot_id, _, _ = ot_info[0], ot_info[1], ot_info[2:]
                    if len(ot_id) < 3:
                        print("ERROR: Multiple event triggers without ids were found inside the same parent span. Roles will not be assigned correctly!")
                        continue
                    else:
                        ot_id = ot_id[2:]  # ev0 ==> 0
                        print("WARNING: An event trigger without event-id was found with other event triggers in the same parent span. Corresponding roles are conferred as well as possible, but please check.")
                    clean_roles = []
                    for vs, roleinfo in roles:
                        if roleinfo["id"][0] == ot_id:
                            valid_siblings.remove(vs)
                        else:
                            clean_roles.append((vs, roleinfo))
                    roles = clean_roles

            # set role for parent span
            if event.getparent().get("span_type") == "desc":
                roles.append((event.getparent().getparent(), {"type": event.getparent().get("label").split(".")[1], "id": event_id}))
            elif event.getparent().get("span_type") == "att":
                # pretty sure this is wrong? => need test file for this
                roles.append((event.getparent(), {"type": event.get("label").split(".")[1], "id": event_id}))

            span_start = min(valid_siblings, key=lambda x: int(x.get("start"))).get("start")
            span_end = max(valid_siblings, key=lambda x: int(x.get("end"))).get("end")
            # assign self as trigger
            trigger = event
            anchor = event.getparent().get("id") if event.getparent().tag != "XML" else "doc"
        else:
            roles = []
            # if a trigger exists, write the trigger
            trigger = event.find("./Entity[@span_type='evtrigger']")
            # TODO: Only take this trigger if it A) has no event_id B) has no role in the event
            if event.get("span_type") != "evspan":
                # if we have an implied eventspan (e.g. from att-pro or desc)
                # we get the event info from the trigger instead
                # TODO: Implement behaviour if no trigger is present (probably take the mention subtype of the desc/att-span or use settings file)
                event_info = trigger.get("label").split(".")
                event_id, event_type, other_info = event_info[0], event_info[1], event_info[2:]
                if len(event_id) < 3:
                    event_id = ""
                else:
                    event_id = event_id[2:]  # ev0 ==> 0
                # also, the role is already implied by the mention_subtype (more likely needs to be solved by a settings file TODO)
                if event.get("span_type") == "desc":
                    roles.append((event.getparent(), {"type": event.get("label").split(".")[1], "id": event_id}))
                elif event.get("span_type") == "att":
                    # pretty sure this is wrong? => need test file for this
                    roles.append((event, {"type": event.get("label").split(".")[1], "id": event_id}))
                anchor = event.get("id")
            else:
                event_info = event.get("label").split(".")
                event_id, event_type, other_info = event_info[0], event_info[1], event_info[2:]
                if len(event_id) < 7:
                    event_id = ""
                else:
                    event_id = event_id[6:]  # evspan0 ==> 0
                anchor = event.getparent().get("id") if event.getparent().tag != "XML" else "doc"
            span_start = event.get("start")
            span_end = event.get("end")
            # get all roles that are part of the event
            candidates = []
            for child in event:
                if child.get("span_type") == "lst":
                    collector = []
                    solve_list(child, collector, [])
                    candidates.extend(collector)
                else:
                    candidates.append(child)
            
            for child in candidates:
                roleinfos = extract_role_field(child)
                if roleinfos is not None:
                    for roleinfo in roleinfos:
                        # if no event_id was given, we assume only one event in the span,
                        # so all children with roles are aprt of it.
                        if not event_id or roleinfo["id"][0] == event_id:
                            roles.append((child, roleinfo))
        # create Event node
        event_node = et.SubElement(events_node, "Event", event_id=old_to_new_event_ids[event.get("id")], type=event_type.strip(), start=span_start, end=span_end, anchor=str(old_to_new_ids[anchor]) if anchor != "doc" else "doc")
        # create the trigger node
        if trigger is not None:
            et.SubElement(event_node, "Trigger", start=trigger.get("start"), end=trigger.get("end"), text=trigger.get("text"))
        # write list of Subevents
        # first identify distinct subevent ids
        subevent_ids = set([".".join(roleinfo["id"]) for _, roleinfo in roles])
        dictinct_ids = []
        for si in subevent_ids:
            for si2 in subevent_ids:
                if si == si2:
                    continue
                if si2.startswith(si):
                    break
            else:
                dictinct_ids.append(si)
        # each distinct id spawns its own subevent
        for di in sorted(dictinct_ids):
            subevent_node = et.SubElement(event_node, "Subevent", subevent_id=di)
            # now we have to filter all roles to fit them to their subevent(s)
            for role_elem, roleinfo in roles:
                roleid = ".".join(roleinfo["id"])
                if di.startswith(roleid):
                    if role_elem.get("span_type") == "evtrigger":
                        ref_att = old_to_new_event_ids[role_elem.get("id")]
                    elif role_elem.get("span_type") != "freetext":
                        try:
                            ref_att = old_to_new_ids[role_elem.get("id")]
                        except:
                            print(f"ERROR: Role was given to an invalid annotation (such as a head-element) with id {role_elem.get('{http://www.omg.org/XMI}id')}.")
                            continue
                    else:
                        ref_att = "#freetext"
                    role_node = et.SubElement(subevent_node, "Role", type=roleinfo["type"].strip(), ref=str(ref_att))
                    if ref_att == "#freetext":
                        role_node.set("start", role_elem.get("start"))
                        role_node.set("end", role_elem.get("end"))
                        role_node.set("text", role_elem.get("text"))
                    else: # points to another entity
                        role_node.set("text", role_elem.get("text"))
                    
                    if role_elem in elems_with_roles:
                        # check first if it's in there,
                        # because one role elem can be in multiple subevents
                        elems_with_roles.remove(role_elem)

    # update span lengths after other events have been added
    for event in events_node:
        try:
            update_eventspan_length(event, events_node)
        except RecursionError:
            print(f"ERROR: During event postprocessing, a recursion error occured while the event with id {event.get('event_id')} was processed. This happens when a circular role-relation was assigned between one or more events. While the events can still be written, mind you that this implies that the annotation is not BeNASch-valid and the eventspans could not set correctly.")

    # check if all roles were assigned to events. Throw error if they weren't assigned
    for role_elem in elems_with_roles:
        if role_elem.get("span_type") == "lst":
            continue
        print(f"ERROR: The span {role_elem.get('id')} with a role annotation couldn't be matched to an event.")


def write_hierarchy(out_root, work_root):
    """
    We retain the hierarchical information from the work root in the form
    of parent-child-Elements. This makes further work with the data easier
    whenever the hierarchy is of relevance for the task (i.e. when creating training data for ML)
    """
    hierarchy_elem = et.SubElement(out_root, "Hierarchy")
    entity_elems = work_root.xpath(".//Entity[@span_type='lst' or @span_type='ent' or @span_type='att' or @span_type='value' or @span_type='desc']")
    for entity in entity_elems:
        parent = entity.getparent()
        while parent.tag != "XML":
            if parent.get("span_type") in ["lst", "ent", "att", "value", "desc"]:
                parent_id = str(old_to_new_ids[parent.get("id")])
                child_id = str(old_to_new_ids[entity.get("id")])
                et.SubElement(hierarchy_elem, "H", parent=parent_id, child=child_id)
                break
            parent = parent.getparent()  # we need to skip non-mentions
        else:
            child_id = str(old_to_new_ids[entity.get("id")])
            et.SubElement(hierarchy_elem, "H", parent="doc", child=child_id)


def write_text(text_elem, text):
    """
    Text string is transformed into single token elements.
    We use line elements to keep some of the original document structure intact.
    We also return start and end dictionaries to make matching the tokens
    to the annotations easier in the next steps.

    NOTE: THIS DOES NOT PERFORM ANY "PROPER" PREPROCESSING!
    """
    lines = text.split("\n")
    start_index_dict = {}
    end_index_dict = {}
    current_index = 0
    j = 0
    for i, line in enumerate(lines):
        if not line and i+1 == len(lines):  # remove empty trailing strings
            continue
        line_elem = et.SubElement(text_elem, "L", line_id=str(i))
        tokens = line.split(" ")
        for token in tokens:
            if not token:
                current_index += 1  # for the whitespace we removed earlier
                continue
            start_index_dict[current_index] = j
            token_elem = et.SubElement(line_elem, "T", token_id=str(j))
            token_elem.text = token
            current_index += len(token)
            end_index_dict[current_index] = j
            current_index += 1  # for the whitespace we removed earlier
            j += 1
    return start_index_dict, end_index_dict

def process_xmi_zip(filename, xmi_file):
    in_root = et.fromstring(xmi_file)

    at_least_one_span = in_root.find("./custom:Span", namespaces={"custom":"http:///custom.ecore"})
    if at_least_one_span is None:
        # stop processing if document doesn't contain annotations
        return

    print(f"Processing {filename}.")

    outname = filename.replace(".txt", ".xml")

    process_general(in_root, outname)


def process_xmi(xmi_file, debug=False):
    print(f"Processing {xmi_file}.")

    infile = et.parse(xmi_file)
    outname = os.path.basename(xmi_file).replace(".xmi", ".xml")
    in_root = infile.getroot()

    out_tree = process_general(in_root, outname, debug)

    return out_tree


def process_general(in_root, outname, debug=False):

    # Modify the CAS XMI according to htr.xy tags
    in_root = modify_text(in_root)

    # Small Corrections
    in_root = small_corrects(in_root)

    text_node = in_root.find("./cas:Sofa", namespaces={"cas":"http:///uima/cas.ecore"})
    document_text = text_node.get("sofaString")

    # TODO: Write DocumentMetaData
    out_root = et.Element("XML")
    out_text = et.SubElement(out_root, "Text")
    start_index_dict, end_index_dict = write_text(out_text, document_text)

    work_root = create_node_tree(in_root, document_text, start_index_dict, end_index_dict)
   
    if debug:
        # For debugging seeing the trees might be helpful, so we keep the option in to write them
        work_tree = et.ElementTree(work_root)
        work_tree.write(os.path.join(DEBUGFOLDER, outname), xml_declaration=True, pretty_print=True, encoding="utf8")

    write_entities(out_root, work_root)
    write_values(out_root, work_root)
    write_events(out_root, work_root, document_text, start_index_dict, end_index_dict)
    write_relations(out_root, work_root)
    write_hierarchy(out_root, work_root)

    out_tree = et.ElementTree(out_root)
    pathlib.Path(OUTFOLDER).mkdir(parents=True, exist_ok=True) 
    out_tree.write(os.path.join(OUTFOLDER, outname), xml_declaration=True, pretty_print=True, encoding="utf8")

    return out_tree

SCHEMA_INFO = None
def read_schema():
    global SCHEMA_INFO

    with open("schema_info.json", mode="r", encoding="utf8") as inf:
        SCHEMA_INFO = json.load(inf)

read_schema()
OUTFOLDER = "./data/outfiles/"
DEBUGFOLDER = "./data/debug/"

if __name__ == "__main__":

    infiles = sorted(glob.glob("./data/exported/due_tests/*/*.xmi"))
    OUTFOLDER = "./data/std_xml/due_tests/"

    for infile in infiles:
        out_tree = process_xmi(infile, debug=True)
        