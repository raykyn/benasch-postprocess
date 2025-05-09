# Read CAS XMI 1.1 files and enrich them with postprocessing. Output XMI files which can be exported back to Inception.

from xml.dom.minidom import Attr
from lxml import etree as et
from utils.text_modification import modify_text
import os
import copy
import re
import pathlib


OUTFOLDER = ""

# XMI specifications (TODO: move all this to a config file (best keep as python file, load as module))
# we assume all projects contain a single span and a single relation layer
CONFIG = {
    "span_layer": "Span",  # if this is not "Span", issues may appear with some of the more project-speficic stuff like htr-corrections
    "relation_layer": "Relation",  # the name of the relation layer in the XMI file
    "priorities": {  # higher priority means nested deeper
        "desc": 0,
        "head": 2,
        "default": 1
    },
    "span_features": {
        "label": {
            "field": "label", 
            "required": True,  # due to some role-only-elements
            "process_instructions": {
                "lst": {  # NOTE: lists dont have an entity type anymore here, this may be controversial?
                    "new_features": {  # create a new feature with the given value
                        "element": "list",  # TODO: keep subclasses of the mention class (needs fixing periods to _)
                    },
                    "copy_features": {  # NOTE: maybe not necessary as roles are with the list members anyways
                        #"role": "role"
                    },
                    "add_all_other_fields_as": "class"  # NOTE: we do this for the moment, so no information gets lost
                },
                "head": {
                    "new_features": {  # create a new feature with the given value
                        "element": "head",
                    },
                    "get_features_from_parent": True  # meaning: the head-class is defined by the instruction 'add feature to head' of the parent span
                },
                "nam": {
                    "new_features": {  # create a new feature with the given value
                        "element": "reference",
                    },
                    "copy_features": {  # copy the given features from work tree to out tree
                        #"role": "role"
                    },
                    "add_features_to_head": {  # needed to go from old format to new
                        "class": "nam"
                    },
                    "add_feature_by_index": {
                        1: "class",
                    },
                    "add_remaining_fields_by_schema_info": 2,  # int is the first index to start from
                    "requires_head": True
                },
                "nom": {
                    "new_features": {
                        "element": "reference",
                    },
                    "copy_features": {
                        #"role": "role"
                    },
                    "add_feature_by_index": {
                        1: "class",
                    },
                    "copy_by_index_to_head": {
                        "class": 2  # meaning: copy the third element in the list after splitting and add it as class
                    },
                    "add_remaining_fields_by_schema_info": 3,
                    "requires_head": True
                },
                "pro": {
                    "new_features": {
                        "element": "reference",
                        "class": "pro"  # gets overwritten anyways, but required for an in between step
                    },
                    "copy_features": {
                        #"role": "role"
                    },
                    "add_features_to_head": {  # needed to go from old format to new
                        "class": "pro"
                    },
                    "add_optional_feature_by_index": {
                        1: "class",
                    },
                    "add_remaining_fields_by_schema_info": 2,
                    "requires_head": True
                },
                "self": {
                    "new_features": {
                        "element": "reference",
                    },
                    "copy_features": {
                        #"role": "role"
                    },
                    "add_features_to_head": {  # needed to go from old format to new
                        "class": "self"
                    },
                    "add_feature_by_index": {
                        1: "class",
                    },
                    "add_remaining_fields_by_schema_info": 2,
                    "requires_head": True
                },
                "unk": {  # NOTE: We assume unk are always replacing references, usually noms (likely untrue)
                    "new_features": {
                        "element": "reference",
                    },
                    "copy_features": {
                        #"role": "role"
                    },
                    "add_feature_by_index": {
                        1: "class",
                    },
                    "copy_by_index_to_head": {
                        "class": 0
                    },
                    "add_remaining_fields_by_schema_info": 2,
                    "print_warning_to_check": True,
                    "requires_head": True
                },
                "att": {
                    "new_features": {
                        "element": "appo",
                    },
                    "copy_by_index_to_head": {
                        "class": 1
                    },
                    "add_remaining_fields_by_schema_info": 2,
                    "requires_head": True
                },
                "desc": {
                    "new_features": {
                        "element": "attr",
                    },
                    "add_feature_by_index": {
                        1: "class",
                    },
                    "add_remaining_fields_by_schema_info": 2,
                },
                "money": {
                    "new_features": {
                        "element": "value",
                        "class": "money",
                    },
                    # "add_all_other_fields_as": "",
                },
                "date": {
                    "new_features": {
                        "element": "value",
                        "class": "date",
                    },
                },
                "time": {
                    "new_features": {
                        "element": "value",
                    },
                    "add_feature_by_index": {
                        0: "class",
                    },
                },
                "other": {
                    "new_features": {
                        "element": "other",
                    },
                    "copy_features": {
                        #"role": "role"
                    },
                    "add_all_other_fields_as": "class",
                },
                r"evspan\d*?": {
                    "new_features": {
                        "element": "eventspan",
                    },
                    "copy_features": {
                    },
                    "process_eventelement": ("eventinfo", "eventspan"),
                    "add_feature_by_index": {
                        1: "class",
                    },
                    "add_remaining_fields_by_event_info": 2
                },
                r"ev\d*?": {
                    "new_features": {
                        "element": "trigger",
                    },
                    "copy_features": {
                    },
                    "process_eventelement": ("eventinfo", "trigger"),
                    "add_feature_by_index": {
                        1: "class",
                    },
                    "add_remaining_fields_by_event_info": 2
                },
                "trigger": {
                    "new_features": {
                        "element": "trigger",
                    },
                    "copy_features": {
                    },
                    "process_eventelement": ("eventinfo", "trigger"),
                    "add_all_other_fields_as": "class",
                },
                "unclear": {
                    "new_features": {
                        "element": "unclear",
                    },
                    "print_warning_to_check": True,
                    "add_all_other_fields_as": "class",
                }
            }
        },
        "role": {
            "field": "Role", 
            "required": False,
            "process_instructions": {
            }
        },
    },
    "relation_features": {
        "label": {
            "field": "label", 
            "required": True,
            "process_instructions": {
                "role": {
                    "new_features": {
                        "class": "role",
                    },
                    "add_all_other_fields_as": "detail",
                    "add_remaining_fields_by_event_info": 2,
                },
                r".*?": {  # all remaining labels are handled like this, so always put this last
                    "add_feature_by_index": {
                        0: "class",
                    },
                    "add_remaining_fields_by_event_info": 1,
                }
            }
        },
    },
    "schema_info": {  # additional tags and where to put them. first option is default choice.
        "other_fields": {
            "numerus": ["sgl", "grp", "neg"],
            "specificity": ["spc", "uspc"],
            "tense": ["pres", "past", "fut", "unspec"],
            "polarity": ["pos", "neg"],
            "modality": [
                "ass", 
                "claim", 
                "hypo",
                "requ",
                "prop",
                "desi",
                "prom",
                "other",
                ],
        },
        "event_fields": {
            "tense": ["pres", "past", "fut", "unspec"],
            "polarity": ["pos", "neg"],
            "modality": [
                "ass", 
                "claim", 
                "hypo",
                "requ",
                "prop",
                "desi",
                "prom",
                "other",
                ],
        }
    },
    "conversions": {
        "entity_types": {
            "^fac(.*)": "loc_fac\\1"
        },
        "role_names": {
            "date_interval": "date-interval",
            "date_missing": "date-missing",
            "date_due": "date-due",
            "payer_prev": "payer-prev",
            "interest_redeemable": "interest-redeemable",
            "interest_conv": "interest-conv"
        }
    },
    "special_processing": [
        "hgb"
    ],
    "implicit_event_processing": {  # this contains the rules for all events which are created by references, appositions and attributes where roles are only "source" and "target"
        
    }
}
SPAN_LAYER = CONFIG["span_layer"]  # the name of the span layer in the XMI file
RELATION_LAYER = CONFIG["relation_layer"]  # the name of the relation layer in the XMI file

DEBUG = True  # True writes the work trees to files
DEBUGFOLDER = "./data/debug/"


def write_marked_for_deletion(out_root):
    """
    In this behavior, spans that are errors in the text due to layout recognition
    errors are not deleted, but instead marked with annotations.
    This can be helpful e.g. if a sequence tagger is to be trained to recognize errors.
    """
    # depreciated, but might get reimplemented later
    text_errors = et.SubElement(out_root, "ERRORS")
    for del_node in out_root.findall("./Spans/Span[@span_type='htr_delete']"):
        error = et.SubElement(text_errors, "Error")
        error.set("type", "bad_text")
        error.set("start", del_node.get("start"))
        error.set("end", del_node.get("end"))


def delete_marked(work_root, text, remove_empty_lines=True):
    """
    We remove htr.delete marked spans, and shift all ids to keep the correct spans in place.
    """
    # depreciated
    for del_node in work_root.findall("./Spans/Span[@span_type='htr_delete']"):
        del_start = int(del_node.get("start"))
        del_end = int(del_node.get("end"))
        del_len = del_end - del_start

        # delete tokens
        for t in range(del_start, del_end):
            token = text.find(f".//T[@token_id='{str(t)}']")
            token.getparent().remove(token)
        
        # shift all annotation ids
        for span in work_root.findall("./Spans/Span"):
            if span.get("span_type") == "htr_delete":
                pass
            if int(span.get("start")) <= del_start and int(span.get("end")) >= del_end:
                span.set("end", str(int(span.get("end")) - del_len))
                if "head_start" in span.attrib:
                    span.set("head_end", str(int(span.get("head_end")) - del_len))
            elif int(span.get("start")) >= del_end:
                span.set("start", str(int(span.get("start")) - del_len))
                span.set("end", str(int(span.get("end")) - del_len))
                if "head_start" in span.attrib:
                    span.set("head_start", str(int(span.get("head_start")) - del_len))
                    span.set("head_end", str(int(span.get("head_end")) - del_len))

        # reset token ids
        for i, token in enumerate(text.findall("./L/T")):
            token.set("token_id", str(i))
            
        # delete the htr.delete element and all its children
        del_node.getparent().remove(del_node)

    # remove empty lines
    if remove_empty_lines:
        for line in text.findall("./L"):
            if not len(line):
                text.remove(line)
        # reset line ids
        for i, line in enumerate(text.findall("./L")):
            line.set("line_id", str(i))


def write_text(text_elem, text, in_root):
    """
    Text string is transformed into single token elements.
    We use line elements to keep some of the original document structure intact.
    We also return start and end dictionaries to make matching the tokens
    to the annotations easier in the next steps.

    NOTE: THIS DOES NOT PERFORM ANY "PROPER" PREPROCESSING!

    TODO: How to represent sentences and line breaks in this new system? should we even keep doing it like this?
    """
    current_index = 0
    start_index_dict = {}
    end_index_dict = {}

    tokens = in_root.findall(".//type5:Token", namespaces={"type5":"http:///de/tudarmstadt/ukp/dkpro/core/api/segmentation/type.ecore"})
    for token in sorted(tokens, key=lambda x: int(x.get("begin"))):
        start = int(token.get("begin"))
        end = int(token.get("end"))
        token_elem = et.SubElement(text_elem, "T", token_id=str(current_index))
        token_elem.text = text[start:end]
        start_index_dict[start] = current_index
        end_index_dict[end] = current_index
        current_index += 1

    return start_index_dict, end_index_dict


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
        return CONFIG["priorities"]["default"]
    if l in CONFIG["priorities"]:
        return CONFIG["priorities"][l]
    else:
        return CONFIG["priorities"]["default"]
    

def convert_char_to_token_idx(start_index_dict, end_index_dict, start, end, entity):
    # transform character index to token index
    token_start = start_index_dict[start]
    #try:
    token_end = end_index_dict[end]
    """
    except KeyError:
        # Inception performs an implicit tokenization, which allows annotations
        # to be set outside our own preprocessing. This can lead to annotations
        # ending inside tokens as defined by our preprocessing/system
        # to circumvent this problem, we simply stretch the tag to the end of the token
        guard = 10000
        while end not in end_index_dict and guard > 0:
            end += 1
            guard -= 1
        token_end = end_index_dict[end]
        
        print(f"WARNING: An annotation ended inside a token. Check this error manually for annotation with id {entity.get('{http://www.omg.org/XMI}id')}!")
    """
    return token_start, token_end


def check_overlaps(spans):
    """
    overlaps are not allowed in this system as they will lead to unexpected behavious 
    when building the tree. 
    We check for overlaps and:
    - if overlap is length 1, fix it and print a warning.
    - if overlap is longer, print an error.
    """
    for i, span in enumerate(spans):
        begin = int(span.get("begin"))
        end = int(span.get("end"))
        for other_span in spans[i+1:]:
            if span == other_span:
                continue
            other_begin = int(other_span.get("begin"))
            other_end = int(other_span.get("end"))
            # check if spans overlap
            #print(begin, other_begin, end, other_end)
            if begin > other_begin and begin <= other_end:
                if end > other_end:
                    # overlap detected, check length
                    if begin - other_begin == 1:
                        span.set("begin", str(other_begin))
                        print(f"WARNING: Overlap detected between spans {span.get('{http://www.omg.org/XMI}id')} and {other_span.get('{http://www.omg.org/XMI}id')}. Overlap is only length 1, trying to fix it.")
                    elif end - other_end == 1:
                        span.set("end", str(other_end))
                        print(f"WARNING: Overlap detected between spans {span.get('{http://www.omg.org/XMI}id')} and {other_span.get('{http://www.omg.org/XMI}id')}. Overlap is only length 1, trying to fix it.")
                    else:
                        print(f"ERROR: Overlap detected between spans {span.get('{http://www.omg.org/XMI}id')} and {other_span.get('{http://www.omg.org/XMI}id')}. This will likely lead to unexpected behaviour down the line.")
            elif other_begin > begin and other_begin <= end:
                if other_end > end:
                    # overlap detected, check length
                    if other_begin - begin == 1:
                        other_span.set("begin", str(begin))
                        print(f"WARNING: Overlap detected between spans {span.get('{http://www.omg.org/XMI}id')} and {other_span.get('{http://www.omg.org/XMI}id')}. Overlap is only length 1, trying to fix it.")
                    elif other_end - end == 1:
                        other_span.set("end", str(end))
                        print(f"WARNING: Overlap detected between spans {span.get('{http://www.omg.org/XMI}id')} and {other_span.get('{http://www.omg.org/XMI}id')}. Overlap is only length 1, trying to fix it.")
                    else:
                        print(f"ERROR: Overlap detected between spans {span.get('{http://www.omg.org/XMI}id')} and {other_span.get('{http://www.omg.org/XMI}id')}. This will likely lead to unexpected behaviour down the line.")


def create_work_tree(in_root, out_root, document_text, start_index_dict, end_index_dict):
    """
    Build a hierarchical tree from all spans in the XMI.
    """
    spans = in_root.findall(f"./custom:{SPAN_LAYER}", namespaces={"custom":"http:///custom.ecore"})

    # check for and fix overlapping tags
    check_overlaps(spans)

    sorted_spans = []
    for ent in spans:
        sorted_spans.append((ent, int(ent.get("begin")), int(ent.get("end")), get_node_priority(ent)))
    sorted_spans.sort(key=lambda x: (x[1], -x[2], x[3]))
    work_root = out_root

    spans_node = et.SubElement(work_root, "Spans")
    parent_node = spans_node

    for entity, start, end, _ in sorted_spans:
        text_content = document_text[start:end]
        start, end = convert_char_to_token_idx(start_index_dict, end_index_dict, start, end, entity)

        while(parent_node != spans_node):
            if end <= int(parent_node.get("end")):
                current_node = et.SubElement(parent_node, "Span", id=entity.get("{http://www.omg.org/XMI}id"), start=str(start), end=str(end), text=text_content)
                for fo, fn in CONFIG["span_features"].items():
                    field, required = fn["field"], fn["required"]
                    if entity.get(field) is None:
                        if required:
                            print(f"WARNING: Missing required field {field} for entity {entity.get('{http://www.omg.org/XMI}id')}!")
                            current_node.set(fo, "other")
                    else:
                        current_node.set(fo, entity.get(field).lower())
                break
            else:
                parent_node = parent_node.getparent()
        else:
            current_node = et.SubElement(parent_node, "Span", id=entity.get("{http://www.omg.org/XMI}id"), start=str(start), end=str(end), text=text_content)
            for fo, fn in CONFIG["span_features"].items():
                field, required = fn["field"], fn["required"]
                if entity.get(field) is None:
                    if required:
                        print(f"WARNING: Missing required field {field} for entity {entity.get('{http://www.omg.org/XMI}id')}!")
                        current_node.set(fo, "other")
                else:
                    current_node.set(fo, entity.get(field).lower())
        parent_node = current_node

    # We get relations from three sources: relation layer, att and desc
    relations = in_root.findall(f".//custom:{RELATION_LAYER}", namespaces={"custom":"http:///custom.ecore"})
    relation_node = et.SubElement(work_root, "Relations")
    for relation in relations:
        current_node = et.SubElement(
            relation_node, 
            "Relation", 
            {
            "id":relation.get("{http://www.omg.org/XMI}id"), 
            "from":relation.get("Governor"),
            "to":relation.get("Dependent"),
            }
            )
        for fo, fn in CONFIG["relation_features"].items():
            field, required = fn["field"], fn["required"]
            if relation.get(field) is None:
                if required:
                    print(f"WARNING: Missing required field {field} for relation {relation.get('{http://www.omg.org/XMI}id')}!")
                    current_node.set(fo, relation.get("other"))
            else:
                current_node.set(fo, relation.get(field).lower())


def process_remaining_fields(fields, remaining_fields, debug_id):
    other_info = CONFIG["schema_info"][fields]
    out_dict = {}
    for feature, possible_values in other_info.items():
        for rf in remaining_fields:
            if rf in possible_values:
                out_dict[feature] = rf
                remaining_fields.remove(rf)
                break
        else:
            out_dict[feature] = possible_values[0]  # default value
    if remaining_fields and not (len(remaining_fields) == 1 and remaining_fields[0] == ""):
        print(f"ERROR: Unrecognized information {remaining_fields} in Span {debug_id}. Ignoring it.")
    return out_dict


def process_spans(out_root):
    """
    Process the spans and write them to the output XML tree.
    :param work_root: The root element of the work XML tree.
    :param out_root: The root element of the output XML tree.
    """

    def do_parent_head_instructions(parent, child, instructions):
        parent_value = parent.get(feature).split(".")
        if parent_value[0] in instructions:
            parent_instruction = instructions[parent_value[0]]
            if "add_features_to_head" in parent_instruction:
                actions = parent_instruction["add_features_to_head"]
                for new_feature, new_value in actions.items():
                    child.set(new_feature, new_value)
            if "copy_by_index_to_head" in parent_instruction:
                actions = parent_instruction["copy_by_index_to_head"]
                for new_feature, copy_idx in actions.items():
                    if copy_idx < len(parent_value):
                        new_value = parent_value[copy_idx]
                    else:
                        new_value = ""  # NOTE: possibly implement using a default value here (also defined in config)
                    child.set(new_feature, new_value)
        else:
            return
    
    def get_feature_by_coreference(span):
        """
        For pronouns, we can input some of their classes by looking at the entities that they're linked with.
        """
        guard = 10000
        target = span
        while True and guard > 0:
            coref_relation = out_root.find(f"./Relations/Relation[@from='{target.get('id')}']")
            if coref_relation is None:
                # no coreference relation found
                # supply a unk class instead
                # print a warning (TODO: put this in the settings as an option)
                span.set("class", "unk")
                span.set("numerus", "unk")
                print(f"WARNING: No coreference relation found for pronoun class in span {span.get('id')}!")
                break
            target = out_root.find(f"./Spans//Span[@id='{coref_relation.get('to')}']")
            # is the target a pronoun too?
            if target.get("class") != "pro":
                if target.get("element") == "list":
                    span.set("class", target.get("class"))
                    span.set("numerus", "grp")  # all lists are groups?
                elif target.get("element") == "appo":
                    # if the coref targets an apposition
                    # print a warning, but pass class and numerus of the parent
                    print(f"WARNING: Coreference relation targetting apposition in span {span.get('id')}!")
                    span.set("class", target.getparent().get("class"))
                    span.set("numerus", target.getparent().get("numerus"))
                else:
                    span.set("class", target.get("class"))
                    span.set("numerus", target.get("numerus"))
                break
            guard -= 1

    for span in out_root.findall("./Spans//Span"):
        for feature, instructions in CONFIG["span_features"].items():
            instructions = instructions["process_instructions"]
            if not instructions:  # this signifies to ignore the feature
                continue
            feature_value = span.get(feature).split(".")
            for regex_key in instructions:
                if re.match(regex_key, feature_value[0]):
                    instruction = instructions[regex_key]
                    new_span = span  # TODO: unify variables
                    # process the feature according to the instructions
                    for instr_name, instr_value in instruction.items():
                        if instr_name == "new_features":
                            for new_feature, new_value in instr_value.items():
                                new_span.set(new_feature, new_value)
                        elif instr_name == "copy_features":
                            for copy_feature, copy_value in instr_value.items():
                                if span.get(copy_value) is not None:
                                    new_span.set(copy_feature, span.get(copy_value))
                        elif instr_name == "add_features_to_head":
                            pass  # probably easier to do this as we process the head
                        elif instr_name == "copy_by_index_to_head":
                            pass  # probably easier to do this as we process the head
                        elif instr_name == "add_feature_by_index":
                            for idx, new_feature in instr_value.items():
                                new_span.set(new_feature, feature_value[idx])
                        elif instr_name == "add_optional_feature_by_index":
                            for idx, new_feature in instr_value.items():
                                # only adds the feature if the label is long enough to support it
                                if len(feature_value) > idx:
                                    new_span.set(new_feature, feature_value[idx])
                        elif instr_name == "add_remaining_fields_by_schema_info":
                            out_dict = process_remaining_fields("other_fields", feature_value[instr_value:], span.get("id"))
                            for f, v in out_dict.items():
                                new_span.set(f, v)
                        elif instr_name == "add_remaining_fields_by_event_info":
                            out_dict = process_remaining_fields("event_fields", feature_value[instr_value:], span.get("id"))
                            for f, v in out_dict.items():
                                new_span.set(f, v)
                        elif instr_name == "add_all_other_fields_as":
                            remaining_class = ".".join(feature_value[1:])
                            new_span.set(instruction["add_all_other_fields_as"], remaining_class)
                        elif instr_name == "get_features_from_parent" and instr_value:
                            parent = span.getparent()
                            if parent.tag != "Spans":
                                do_parent_head_instructions(parent, new_span, instructions)
                            else:
                                print(f"WARNING: Parent of span {span.get('id')} not found!")
                                continue
                        elif instr_name == "requires_head" and instr_value:
                            # if no head is present, try to add one
                            for child in span:
                                child_value = child.get(feature).split(".")
                                if child_value[0] == "head":
                                    break
                            else:
                                # No head is present, handle the case here
                                # easy case: no other children exist, simply make the whole span the head
                                if len(span) == 0:
                                    start = span.get("start")
                                    end = span.get("end")
                                # complex case: other children exist, supplement the head with all text till the first child,
                                # or if that would yield a span of 0, from last child to end. also print a warning when this happens.
                                else:
                                    # print warning message
                                    print(f"WARNING: No head found for span {span.get('id')}, other children present! Trying to supplement a head before first or after last child.")
                                    # get the first child
                                    first_child = span[0]
                                    # get the start and end of the first child
                                    first_child_start = int(first_child.get("start"))
                                    # check if the head would be empty
                                    if first_child_start - int(span.get("start")) > 0:
                                        start = span.get("start")
                                        end = str(first_child_start - 1)
                                    elif int(span.get("end")) - (int(span[-1].get("end"))) > 0:
                                        start = str(int(span[-1].get("end"))+1)
                                        end = span.get("end")
                                    else:
                                        print(f"ERROR: No head found for span {span.get('id')}, other children present! Failed to find space to supplement a head.")
                                        continue
                                new_head_span = et.SubElement(new_span, "Span", {
                                    "id": span.get("id") + "_head",
                                    "start": start,
                                    "end": end,
                                    "element": "head",
                                })
                                do_parent_head_instructions(span, new_head_span, instructions)
                                # getting the text is somewhat difficult
                                new_head_span.set("text", " ".join([out_root.find(f"./Text//T[@token_id='{x}']").text for x in range(int(start), int(end)+1)]))
                        elif instr_name == "process_eventelement":
                            # if the span is an event element like an event span or a trigger
                            # we prepare their information here and add it to their role field
                            match = re.match(r'^(.*?)(\d+)$', feature_value[0])
                            if match:
                                elem_id = match.group(2)
                            else:
                                elem_id = ""
                            old_roles = span.get(instr_value[0])
                            if old_roles is not None:
                                new_span.set(f"{instr_value[0]}", f"{old_roles};{instr_value[1]}.{elem_id}")
                            else:
                                new_span.set(f"{instr_value[0]}", f"{instr_value[1]}.{elem_id}")
                        elif instr_name == "print_warning_to_check":
                            print(f"WARNING: span {span.get('id')} is marked as {feature_value[0]}! Please check the annotation.")
                        else:
                            print(f"WARNING: Unknown instruction {instr_name} for feature {feature} in span {span.get('id')}!")
                            continue
                    # set the text of the new span
                    new_span.set("text", span.get("text"))
                    break
            else:
                print(f"WARNING: Unknown {feature} value {feature_value[0]} for span {span.get('id')}!")
                continue

    def get_class_from_children(span):
        """
        Hardcoded for now!
        """
        all_classes = set()
        for child in span:
            if child.get("element") == "reference":
                designated_class = child.get("class").split("_")[0]
                if designated_class != "pro":
                    all_classes.add(designated_class)
        return ";".join(sorted(all_classes))

    # NOTE: process lists after everything else has been processed, but before pronouns try to find their class
    for span in out_root.findall("./Spans//Span"):
        if span.get("element") == "list":
            new_class = get_class_from_children(span)
            span.set("class", new_class)

    # NOTE: worth considering if this should be in a separate function AFTER relations and events have been processed
    for span in out_root.findall("./Spans//Span"):
        if span.get("element") == "reference" and span.get("class") == "pro":
            # some info requires other info to already have been processed, so we add those instructions in a second loop
            get_feature_by_coreference(span)


def process_relations(out_root):
    relations = out_root.findall("./Relations/Relation")
    for relation in relations:
        for feature, instructions in CONFIG["relation_features"].items():
            instructions = instructions["process_instructions"]
            if not instructions:  # no special operations
                continue
            feature_value = relation.get(feature).split(".")
            for regex_key in instructions:
                if re.match(regex_key, feature_value[0]):
                    instruction = instructions[regex_key]
                    for instr_name, instr_value in instruction.items():
                        if instr_name == "new_features":
                            for new_feature, new_value in instr_value.items():
                                relation.set(new_feature, new_value)
                        elif instr_name == "add_feature_by_index":
                            for idx, new_feature in instr_value.items():
                                relation.set(new_feature, feature_value[idx])
                        elif instr_name == "add_remaining_fields_by_event_info":
                            out_dict = process_remaining_fields("event_fields", feature_value[instr_value:], relation.get("id"))
                            for f, v in out_dict.items():
                                relation.set(f, v)
                        elif instr_name == "add_all_other_fields_as":
                            remaining_class = ".".join(feature_value[1:])
                            relation.set(instruction["add_all_other_fields_as"], remaining_class)
                    break


def write_events(out_root):
    """
    We write events and situations here.
    - the trigger is not the important part, but instead the event-span
    - if no eventspan is annotated, but a trigger is, the evspan is extrapolated
    - event-spans, trigger and roles do not necessarily need an id if only 1 event with no subevents is in that annotation level
    """

    def get_roles(role_field):
        if role_field is None:
            return {}
        roles = []
        rolefields = role_field.split(";")
        for rf in rolefields:
            rf = rf.split(".")
            if len(rf) == 1 or (len(rf) == 2 and rf[1] == ""):
                roles.append({"role": rf[0], "id": [""]})
            elif len(rf) == 2:
                if ":" in rf[1]:
                    roleid = rf[1].split(":")
                    roles.append({"role": rf[0], "id": roleid})
                else:    
                    roleid = list(rf[1])
                    roles.append({"role": rf[0], "id": roleid})
            else:
                roles.append({"role": rf[0], "id": list(rf[1:])})
        return roles
    
    def apply_role_name_conversions(entity_type):
        for o, r in CONFIG["conversions"]["role_names"].items():
            entity_type = re.sub(o, r, entity_type)
        return entity_type
    
    def create_event(event, event_node, event_triggers, participants, running_ids):
        running_ids += 1
        for event_trigger in event_triggers:
            trigger_node = et.SubElement(event_node, "Trigger", start=event_trigger.get("start"), end=event_trigger.get("end"), text=event_trigger.get("text"), ref=event_trigger.get("id"))
        # write list of Subevents
        # first identify distinct subevent ids
        subevent_ids = set([".".join(roleinfo["id"]) for _, roleinfo in participants])
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
        for num, di in enumerate(sorted(dictinct_ids)):
            subevent_node = et.SubElement(event_node, "Event", event_id=event_node.get("event_id")+"."+str(num))
            for role_elem, roleinfo in participants:
                roleid = ".".join(roleinfo["id"])
                if di.startswith(roleid):
                    if role_elem.tag == "Spans":
                        print(f"ERROR: Describing Element (e.g. Apposition, Attribute) without List or Reference to nest it! See {event.get('id')}")
                        continue
                    # TODO: Implement handling of appositions inside lists (project role to all members of the list instead)
                    #print(role_elem.tag, role_elem.attrib)
                    role_node = et.SubElement(subevent_node, "Role", role=apply_role_name_conversions(roleinfo["role"].strip()), ref=role_elem.get("id"))
                    role_node.set("text", role_elem.get("text"))
                    if role_elem in elems_with_roles:
                        # check first if it's in there,
                        # because one role elem can be in multiple subevents
                        elems_with_roles.remove(role_elem)
        return running_ids
    
    # update span lengths after other events have been added
    def update_eventspan_length(event, events_node, already_processed):
        already_processed.append(event)
        for subevent in event.findall("./Event"):
            for role in subevent.findall("./Role"):
                ref = role.get("ref")
                corr = events_node.find("./EventGroup[@event_id='" + ref + "']")
                if corr is not None:
                    if corr not in already_processed:
                        update_eventspan_length(corr, events_node, already_processed)
                    event.set("start", str(min([int(event.get("start")), int(corr.get("start"))])))
                    event.set("end", str(max([int(event.get("end")), int(corr.get("end"))])))

    def solve_list(list_elem, collector, prev_roles, transfer_roles=False):
        """
        spans inside lists may have relevant roles
        so we need to also look through lists and return all their children
        recursively. Also give all roles of a list to all its children
        """
        if list_elem.get("role"):
            prev_roles.append(list_elem.get("role")) 
        for child in list_elem:
            if child.get("element") in ["reference", "trigger", "eventspan", "value"]:
                if transfer_roles and prev_roles:
                    if child.get("role"):
                        child.set("role", child.get("role") + ";" + ";".join(prev_roles))
                    else:
                        child.set("role", ";".join(prev_roles))
                collector.append(child)
            elif child.get("element") == "list":
                solve_list(child, collector, prev_roles=prev_roles.copy(), transfer_roles=transfer_roles)

    def get_participants_from_relations(prefix, event, event_id):
        """
        All relations that have an event-spawning element as a source and a prefix "role" (or any other passed prefix) will cause
        the target element to be added as a participant in the event.
        This is a workaround to enable overlapping events even when the work tree system wouldn't allow it.
        """
        matching_relations = out_root.xpath("./Relations/Relation[@from='{0}' and starts-with(@label, '{1}')]".format(event.get("id"), prefix + "."))
        for relation in matching_relations:
            # get the target element
            target = out_root.find(f"./Spans//Span[@id='{relation.get('to')}']")
            role = relation.get("label").split(".")[1]
            yield (target, {"id": event_id, "role": role})

    # move all roles from list elements to their children
    for list_elem in out_root.xpath("./Spans//Span[@element='list' and not(parent::Span[@element='list'])]"):
        solve_list(list_elem, [], [], transfer_roles=True)

    # collect all elements with roles so we can later detect which ones didnt get an event
    elems_with_roles = out_root.xpath("./Spans//Span[string-length(@role) > 0]")

    events_node = et.SubElement(out_root, "Events")
    
    previously_used_triggers = []

    # eventspan handling
    running_ids = 0
    eventspans = out_root.xpath("./Spans//Span[@element='eventspan']")
    for event in eventspans:
        event_id = next(role for role in get_roles(event.get("eventinfo")) if role["role"] == "eventspan")["id"]  # TODO: as we're not using the role field anymore we can simplify this
        # find a trigger if present
        triggers = event.findall("./Span[@element='trigger']")
        event_triggers = []
        for trigger in triggers:
            # only add this trigger if it has no or same event id
            trigger_id = next(role for role in get_roles(trigger.get("eventinfo")) if role["role"] == "trigger")["id"]
            if trigger_id == event_id:
                event_triggers.append(trigger)
                previously_used_triggers.append(trigger)
        # collect participants
        candidates = []
        for child in event:
            if child in event_triggers:
                continue
            if child.get("element") == "list":
                collector = []
                solve_list(child, collector, [])
                candidates.extend(collector)
            else:
                candidates.append(child)
        # print(event.get("id"), [c.get("id") for c in candidates])
        participants = []
        for candidate in candidates:
            roles = get_roles(candidate.get("role"))
            for role in roles:
                # if no event_id was given, we assume only one event in the span,
                # so all children with roles are part of it.
                if not event_id[0] or role["id"][0] == event_id[0]:
                    participants.append((candidate, role))
        # get participants from role.X relations (this is currently hardcoded)
        participants.extend(get_participants_from_relations("role", event, event_id))

        event_node = et.SubElement(events_node, "EventGroup", 
            {
                "event_id": str(running_ids), 
                "class": event.get("class"),
                "polarity": event.get("polarity"),
                "tense": event.get("tense"),
                "modality": event.get("modality"),
                "start": event.get("start"), 
                "end": event.get("end"), 
                "ref": event.get("id")
            })
        running_ids = create_event(event, event_node, event_triggers, participants, running_ids)

    # events based on references
    # self is always participant in the event
    # don't write events if only one entity (self) is present
    reference_spans = out_root.xpath("./Spans//Span[@element='reference']")
    for event in reference_spans:
        event_id = [""]  # more complex events need to be presented as eventspans in the current system
        head = event.find("./Span[@element='head']")
        if head is None:
            continue  # a missing head is an error and needs to be fixed, otherwise the event won't be generated
        # collect participants
        candidates = []
        for child in event:
            if child.get("element") in ["head", "appo", "att"]:  # TODO: create list in config for all describing spans (or only allow references to be added?)
                continue
            if child.get("element") == "list":
                collector = []
                solve_list(child, collector, [])
                candidates.extend(collector)
            else:
                candidates.append(child)
        participants = [(event, {"id": [""], "role": "source"})]  # TODO: better behaviour needs to be implemented
        for candidate in candidates:
            roles = get_roles(candidate.get("role"))
            for role in roles:
                # if no event_id was given, we assume only one event in the span,
                # so all children with roles are part of it.
                if not event_id[0] or role["id"][0] == event_id[0]:
                    participants.append((candidate, role))
        # get participants from role.X relations (this is currently hardcoded)
        participants.extend(get_participants_from_relations("role", event, event_id))
        if len(participants) == 1:
            # no additional roles found, so look for elements without explicit role assignments
            candidates = []
            for child in event:
                if child.get("element") not in ["list", "reference", "value"]:  # TODO: create list in config which contains all elements like that
                    continue
                if child.get("element") == "list":
                    collector = []
                    solve_list(child, collector, [])
                    candidates.extend(collector)
                else:
                    candidates.append(child)
            participants = [(event, {"id": [""], "role": "source"})]  # TODO: better behaviour needs to be implemented
            for candidate in candidates:
                participants.append((candidate, {"id": [""], "role": "target"}))
            if len(participants) == 1:
                continue
        event_node = et.SubElement(events_node, "EventGroup", 
            {
                "event_id": str(running_ids), 
                "class": head.get("class"), 
                "polarity": event.get("polarity"),
                "tense": event.get("tense"),
                "modality": event.get("modality"),
                "start": event.get("start"), 
                "end": event.get("end"), 
                "ref": event.get("id")
            })
        running_ids = create_event(event, event_node, [head], participants, running_ids)

    
    # events based on appositions
    appo_spans = out_root.xpath("./Spans//Span[@element='appo']")
    for event in appo_spans:
        event_id = [""]  # more complex events need to be presented as eventspans in the current system
        head = event.find("./Span[@element='head']")
        if head is None:
            continue  # a missing head is an error and needs to be fixed, otherwise the event won't be generated
        reference = event.getparent()
        # collect participants
        candidates = []
        for child in event:
            if child.get("element") in ["head", "appo", "att"]:  # TODO: create list in config for all describing spans (or only allow references to be added?)
                continue
            if child.get("element") == "list":
                collector = []
                solve_list(child, collector, [])
                candidates.extend(collector)
            else:
                candidates.append(child)
        participants = [(reference, {"id": [""], "role": "source"})]  # TODO: better behaviour needs to be implemented
        for candidate in candidates:
            roles = get_roles(candidate.get("role"))
            for role in roles:
                # if no event_id was given, we assume only one event in the span,
                # so all children with roles are part of it.
                if not event_id[0] or role["id"][0] == event_id[0]:
                    participants.append((candidate, role))
        # get participants from role.X relations (this is currently hardcoded)
        participants.extend(get_participants_from_relations("role", event, event_id))
        if len(participants) == 1:
            # no additional roles found, so look for elements without explicit role assignments
            candidates = []
            for child in event:
                if child.get("element") not in ["list", "reference", "value"]:  # TODO: create list in config which contains all elements like that
                    continue
                if child.get("element") == "list":
                    collector = []
                    solve_list(child, collector, [])
                    candidates.extend(collector)
                else:
                    candidates.append(child)
            participants = [(reference, {"id": [""], "role": "source"})]  # TODO: better behaviour needs to be implemented
            for candidate in candidates:
                participants.append((candidate, {"id": [""], "role": "target"}))
            if len(participants) == 1:
                continue
        event_node = et.SubElement(events_node, "EventGroup", 
            {
                "event_id": str(running_ids), 
                "class": head.get("class"), 
                "polarity": event.get("polarity"),
                "tense": event.get("tense"),
                "modality": event.get("modality"),
                "start": event.get("start"), 
                "end": event.get("end"), 
                "ref": event.get("id")
            })
        running_ids = create_event(event, event_node, [head], participants, running_ids)


    # events based on attributes
    attr_spans = out_root.xpath("./Spans//Span[@element='attr']")
    for event in attr_spans:
        event_id = [""]  # more complex events need to be presented as eventspans in the current system
        triggers = event.findall("./Span[@element='trigger']")
        event_triggers = []
        for trigger in triggers:
            # only add this trigger if it has no event id (TODO: this behaviour needs some improvement, e.g. any trigger can be used to be part of the attribute event)
            trigger_id = next(role for role in get_roles(trigger.get("eventinfo")) if role["role"] == "trigger")["id"]
            if trigger_id == [""]:
                event_triggers.append(trigger)
                previously_used_triggers.append(trigger)
        if triggers != event_triggers:
            # if some triggers were not added, it means they had an event id, and we better let the triggers handle the 
            # event instead of the attribute
            if len(event_triggers) > 0:
                print("ERROR: Multiple triggers, some without ids, were found in a single Attribute Span. See ID {0}.".format(event.get("id")))
            continue
        reference = event.getparent()
        # collect participants
        candidates = []
        for child in event:
            if child in event_triggers:
                continue
            if child.get("element") == "list":
                collector = []
                solve_list(child, collector, [])
                candidates.extend(collector)
            else:
                candidates.append(child)
        participants = [(reference, {"id": [""], "role": "source"})]  # TODO: better behaviour needs to be implemented
        for candidate in candidates:
            roles = get_roles(candidate.get("role"))
            for role in roles:
                # if no event_id was given, we assume only one event in the span,
                # so all children with roles are part of it.
                if not event_id[0] or role["id"][0] == event_id[0]:
                    participants.append((candidate, role))
        # get participants from role.X relations (this is currently hardcoded)
        participants.extend(get_participants_from_relations("role", event, event_id))
        if len(participants) == 1:
            # no additional roles found, so look for elements without explicit role assignments
            candidates = []
            for child in event:
                if child in event_triggers:
                    continue
                if child.get("element") == "list":
                    collector = []
                    solve_list(child, collector, [])
                    candidates.extend(collector)
                else:
                    candidates.append(child)
            participants = [(reference, {"id": [""], "role": "source"})]  # TODO: better behaviour needs to be implemented
            for candidate in candidates:
                participants.append((candidate, {"id": [""], "role": "target"}))
            if len(participants) == 1:
                continue
        event_node = et.SubElement(events_node, "EventGroup", 
            {
                "event_id": str(running_ids), 
                "class": event.get("class"), 
                "polarity": event.get("polarity"),
                "tense": event.get("tense"),
                "modality": event.get("modality"),
                "start": event.get("start"), 
                "end": event.get("end"), 
                "ref": event.get("id")
            })
        running_ids = create_event(event, event_node, event_triggers, participants, running_ids)

    # event based on trigger handling
    trigger_spans = out_root.xpath("./Spans//Span[@element='trigger']")
    for trigger in trigger_spans:
        # make sure that you don't belong to an event span
        if trigger in previously_used_triggers:
            continue
        trigger_id = next(role for role in get_roles(trigger.get("eventinfo")) if role["role"] == "trigger")["id"]
        # find parent span
        parent = trigger.getparent()
        # collect participants
        candidates = []
        for child in parent:
            if child == trigger:
                continue
            if child.get("element") == "list":
                collector = []
                solve_list(child, collector, [])
                candidates.extend(collector)
            else:
                candidates.append(child)
        participants = []
        for candidate in candidates:
            roles = get_roles(candidate.get("role"))
            for role in roles:
                # if no event_id was given, we assume only one event in the span,
                # so all children with roles are part of it.
                if not trigger_id[0] or role["id"][0] == trigger_id[0]:
                    participants.append((candidate, role))
        # get participants from role.X relations (this is currently hardcoded)
        participants.extend(get_participants_from_relations("role", trigger, trigger_id))
        event_node = et.SubElement(events_node, "EventGroup", 
            {
                "event_id": str(running_ids), 
                "class": trigger.get("class"), 
                "polarity": trigger.get("polarity"),
                "tense": trigger.get("tense"),
                "modality": trigger.get("modality"),
                "start": min(min(participants, key=lambda x: int(x[0].get("start")))[0].get("start"), trigger.get("start")) if participants else trigger.get("start"), 
                "end": max(max(participants, key=lambda x: int(x[0].get("end")))[0].get("end"), trigger.get("end")) if participants else trigger.get("end"),
            })
        running_ids = create_event(trigger, event_node, [trigger], participants, running_ids)

    # events based on relations
    relations = out_root.findall("./Relations/Relation")
    for relation in relations:
        # corefs should be processed separately
        if relation.get("label").split(".")[0] in ["coref", "role"]:  # TODO: define this in CONFIG instead of hardcoding
            continue
        # TODO: If one of the arrows points to a list, add each child as participant instead of the list
        participants = [
            (
                out_root.find(f"./Spans//Span[@id='{relation.get('from')}']"),
                {"id": [""], "role": "source"}
            ),
            (
                out_root.find(f"./Spans//Span[@id='{relation.get('to')}']"),
                {"id": [""], "role": "target"}
            )
        ]
        event_node = et.SubElement(events_node, "EventGroup", 
            {
                "event_id": str(running_ids), 
                "class": relation.get("class"),
                "polarity": relation.get("polarity"),
                "tense": relation.get("tense"),
                "modality": relation.get("modality"),
            })
        running_ids = create_event(relation, event_node, [], participants, running_ids)

    # fit all event span start and ends
    already_processed = []
    for event in events_node:
        try:
            update_eventspan_length(event, events_node, already_processed)
        except RecursionError:
            print(f"ERROR: During event postprocessing, a recursion error occured while the event with id {event.get('event_id')} was processed. This should not be happening and is indicating an error in the code.")

    # check if all roles were assigned to events. Throw error if they weren't assigned
    for role_elem in elems_with_roles:
        if role_elem.get("element") == "list":
            continue
        if "trigger" in role_elem.get("role"):
            continue
        print(f"ERROR: The span {role_elem.get('id')} with a role annotation {role_elem.get('role')} couldn't be matched to an event.")


def write_coref(out_root):
    """
    Write the coreference information to the output XML tree.
    corefs are usually annotated as relations with the coref-label.
    :param out_root: The root element of the output XML tree.

    NOTE: I'm not sure how we want to handle this currently.
    One way would be to simply write an entity registry where we 
    aggregate all information about each noted entity with all its
    mentions by using the coref information.
    Simply writing corefs again would duplicate the information in
    the Relations node without adding much to it.
    """
    pass


def apply_special_operations_before_processing(out_root):
    """
    Apply special operations to the XML tree before processing.
    :param out_root: The root element of the output XML tree.
    """
    if "hgb" in CONFIG["special_processing"]:
        # transform att.X.pro to desc.X and delete a possible head child
        for span in out_root.findall("./Spans//Span"):
            label = span.get("label").split(".")
            if len(label) > 2 and label[0] == "att":
                if label[2] == "pro":
                    span.set("label", ".".join(["desc", label[1], *label[3:]]))
                    # delete the head child
                    head = span.find("./Span[@label='head']")
                    if head is not None:
                        span.remove(head)
                elif label[2] == "nam":
                    span.set("label", ".".join(label[:2] + label[3:]))
        # remove list.contra elements
        for span in out_root.findall("./Spans//Span[@label='lst.contra']"):
            parent = span.getparent()
            index = parent.index(span)
            for i, child in enumerate(list(span)):
                parent.insert(index + i, child)
            parent.remove(span)
        # if a pronoun has a "same" in its label, remove the "same"
        # but create a coref-relation between pronoun and grandparent element
        for span in out_root.findall("./Spans//Span"):
            label = span.get("label").split(".")
            if label[0] == "pro" and "same" in label:
                label.remove("same")
                span.set("label", ".".join(label))
                new_relation = et.SubElement(out_root.find("Relations"), "Relation", {"id": span.get("id") + "_rel", "label": "coref", "from": span.get("id"), "to": span.getparent().getparent().get("id")})
        # when an event-trigger in form of evX is a child of a descriptor
        # and contains an id, add the facility parent of the desc via a relation
        # as an additional role in the event
        for span in out_root.findall("./Spans//Span"):
            label = span.get("label").split(".")
            if label[0] == "desc":
                for i, child in enumerate(span):
                    child_label = child.get("label").split(".")
                    match = re.match(r'^(.*?)(\d+)$', child_label[0])
                    if match:
                        if match.group(1) == "ev" and match.group(2):
                            et.SubElement(out_root.find("Relations"), "Relation", {"id": child.get("id") + "_role", "label": "role.source", "from": child.get("id"), "to": span.getparent().get("id")})
        # all nom.fac.comp.grp tags are modified
        # with a desc.comp as child after their head
        # which covers the text from all after head to end of tag
        # append all children of that part to the comp
        for span in out_root.findall("./Spans//Span[@label='nom.fac.comp.grp']"):
            span.set("label", 'nom.fac..grp')
            non_head_children = sorted(span.xpath("./Span[not(@label='head')]"), key=lambda x: int(x.get("start")))
            new_desc = et.SubElement(span, "Span", {"id": span.get("id") + "_comp", "label": "desc.comp", "start": non_head_children[0].get("start"), "end": non_head_children[-1].get("end"), "text": span.get("text")[int(non_head_children[0].get("start"))-int(span.get("start")):int(non_head_children[-1].get("end"))-int(span.get("end"))]})
            for head in non_head_children:
                new_desc.append(head)
        # replace all desc.org-job with desc.org-aff (betrifft nur 'des Raths')
        for span in out_root.findall("./Spans//Span[@label='desc.org-job']"):
            span.set("label", "desc.org-aff")
        # fix the nom.fac.grp to nom.fac..grp
        for span in out_root.findall("./Spans//Span[@label='nom.fac.grp']"):
            span.set("label", 'nom.fac..grp')
        # origin => loc.past
        for span in out_root.findall("./Spans//Span[@label='desc.origin']"):
            span.set("label", 'desc.loc.past')
        # delete desc.quant
        for span in out_root.findall("./Spans//Span[@label='desc.quant']"):
            span.getparent().remove(span)
        # time.rec => time_rec
        for span in out_root.findall("./Spans//Span[@label='time.rec']"):
            span.set("label", 'time_rec')
        # if there is a owner in head of a facility, remove it, look for a preceding child
        # and cover it with a desc.owner. append the child to the desc.owner
        for span in out_root.findall("./Spans//Span"):
            if span.get("label").startswith("nom.fac.owner"):
                span.set("label", span.get("label").replace("owner", ""))
                first_child = span[0]
                desc_owner = et.SubElement(span, "Span", {"id": span.get("id") + "_desc_owner", "label": "desc.owner", "start": first_child.get("start"), "end": first_child.get("end"), "text": first_child.get("text")})
                desc_owner.append(first_child)
                span.insert(0, desc_owner)
        # try to fix forgotten desc.owner tags. if a pronoun is first child of a facility reference
        # put a desc.owner around it.
        for span in out_root.findall("./Spans//Span"):
            if span.get("label").startswith("nom.fac"):
                if len(span) > 0 and (span[0].get("label").startswith("pro") or span[0].get("label").startswith("nam.per") or span[0].get("label").startswith("nom.per") or span[0].get("label").startswith("nam.org")):
                    desc_owner = et.SubElement(span, "Span", {"id": span.get("id") + "_desc_owner", "label": "desc.owner", "start": span[0].get("start"), "end": span[0].get("end"), "text": span[0].get("text")})
                    desc_owner.append(span[0])
                    span.insert(0, desc_owner)

        # debugging
        for span in out_root.findall("./Spans//Span"):
            #if len(span.get("label").split(".")) > 1 and span.get("label").split(".")[1] == "fac_part":
            if "desc" not in span.get("label") and "part-of" in span.get("label"):
                print("PART OF")
                #print(span.getparent().get("text").encode("utf8"))
                print(span.get("text").encode("utf8"))


def apply_special_operations_after_processing(out_root):
    if "hgb" in CONFIG["special_processing"]:
        merge = {
            "facstreet": "fac_street",
            "fac_?vorstadt": "fac_district",
            "loc_?vorstadt": "fac_district",
            "loc_vorstadt": "fac_district",
            "fac_vortsadt": "fac_district",
            "fac_place": "fac_square",
            "fac_def": "fac_defense",
            "fac_river": "loc_river",
            "fac_wall": "fac_part",
            "same": "type",
            "": "type",
            "loc_to": "loc",
            "alias": "nam",
            "tax": "dues",
            "org-job": "occ_org-job",
            "org-repr": "occ_org-repr",
            "comp": "includes",
            "org-affil": "org-aff",
            "per-repr": "repr",
            "other_sale": "sale",
            "unknown": "unk",
            "gpe_gpe": "gpe-gpe",
            "gpe_loc": "gpe-loc",
            "gpe_org": "gpe-org",
        }
        for span in out_root.findall("./Spans//Span"):
            span_class = span.get("class")
            if span_class is None:
                continue
            # merge or rename classes of nodes
            if span_class in merge:
                span_class = merge[span_class]

            # split classes and subclasses
            span_class = span_class.split("_")
            if len(span_class) > 1:
                span.set("class", span_class[0])
                span.set("subclass", span_class[1])
            else:
                span.set("class", span_class[0])
                span.set("subclass", "")

            


def cleanup(out_root):
    """
    Remove unwanted elements, attributes, etc.
    """
    pass # TODO: Remove date lists, or lists in general? (and keep the children)

        
def process(in_root, outname, write_deletions=False):
    """
    Process the XMI file and write the output to a new file.
    :param in_root: The root element of the input XML tree.
    :param outname: The name of the output file.
    :param write_deletions: Flag to determine if deletions should be written.
    """

    #print(et.tostring(in_root, encoding='unicode', pretty_print=True))

    # Modify the CAS XMI according to htr.xy tags
    in_root = modify_text(in_root, delete_marked=(not write_deletions))

    #print(et.tostring(in_root, encoding='unicode', pretty_print=True))

    text_node = in_root.find("./cas:Sofa", namespaces={"cas":"http:///uima/cas.ecore"})
    document_text = text_node.get("sofaString")

    out_root = et.Element("XML")
    out_text = et.SubElement(out_root, "Text")
    start_index_dict, end_index_dict = write_text(out_text, document_text, in_root)

    create_work_tree(in_root, out_root, document_text, start_index_dict, end_index_dict)

    # delete or write all htr.delete spans
    #if not write_deletions:  currently depreciated
    #    delete_marked(out_root, out_text)

    apply_special_operations_before_processing(out_root)

    process_spans(out_root)
    process_relations(out_root)
    write_events(out_root)
    write_coref(out_root)

    apply_special_operations_after_processing(out_root)

    # delete or write all htr.delete spans
    #if write_deletions:  currently depreciated
    #    write_marked_for_deletion(out_root)

    cleanup(out_root)

    # write debug info
    print(f"See processed file at {os.path.abspath(os.path.join(OUTFOLDER, os.path.basename(outname)))}")

    # write xml
    out_tree = et.ElementTree(out_root)
    pathlib.Path(OUTFOLDER).mkdir(parents=True, exist_ok=True) 
    out_tree.write(os.path.join(OUTFOLDER, os.path.basename(outname)), xml_declaration=True, pretty_print=True, encoding="utf8")
    
    #print(et.tostring(out_root, encoding='unicode', pretty_print=True))
    

def process_xmi(infile, write_deletions=False):
    in_root = et.parse(infile).getroot()

    at_least_one_span = in_root.find(f"./custom:{SPAN_LAYER}", namespaces={"custom":"http:///custom.ecore"})
    if at_least_one_span is None:
        # stop processing if document doesn't contain annotations
        return

    print("="*80)
    print(f"Processing {os.path.abspath(infile)}.")

    outname = infile.replace(".xmi", ".xml")

    process(in_root, outname, write_deletions=write_deletions)


if __name__ == "__main__":
    # implement a test case with a single file
    import zipfile
    path = "./data/hgb_2025_04_03/exports/hgb_21113301359897783216/annotation/HGB_Exp_12_199_HGB_1_229_037_015.txt/admin.zip"
    archive = zipfile.ZipFile(path, 'r')
    xmi = archive.read("admin.xmi")
    process_xmi("debug.xmi", xmi)
    