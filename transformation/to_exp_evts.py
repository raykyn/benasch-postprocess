"""
Creates a sample for each span, with given tags.
Also enables adding event roles, triggers etc.
"""
from lxml import etree as et
import pprint as pp

from numpy import source


def get_id(elem):
    if elem.tag in ["Reference", "List", "Attribute"]:
        id = elem.get("id")
    elif elem.tag == "Descriptor":
        id = elem.get("id")
    elif elem.tag == "Value":
        id = elem.get("id")
    elif elem.tag == "Event":
        id = elem.get("id")
    else:
        print(elem.tag)
        raise NotImplementedError
    return id


class Token(object):
    def __init__(self, text, tags=None):
        self.text = text
        self.tags = {}  # col: tag
        if tags is not None:
            self.tags = tags
        self.head = {}  # col: is_head? (bool)

    def print_conllu(self, order):
        tags = []
        for o in order:
            tags.append(self.tags[o])
        return "\t".join([self.text] + tags) + "\n"
    
    def __str__(self):
        return self.text


class Span(object):
    """
    Holds all information for a specific sample.
    """
    def __init__(self, xml_obj, tokens, ref=None):
        self.tag = xml_obj.tag if xml_obj is not None else "doc"
        self.xml_obj = xml_obj
        self.tokens = [Token(t.text) for t in tokens]
        self.children = []
        self.parent = None
        self.ref = ref  # mainly for roles
        self.focus_trigger = None

        self.corr_event = None  # if the element is a role or trigger, reference to the event is here
        self.corr_subevents = set()

    def __repr__(self):
        return f"<Span {self.tag}: '{' '.join([str(t) for t in self.tokens])}'>"

    @property
    def start(self):
        if self.ref is None:
            if self.xml_obj is None:
                return None
            else:
                return self.xml_obj.get("start")
        else:
            return self.ref.start
    
    @property
    def end(self):
        if self.ref is None:
            if self.xml_obj is None:
                return None
            else:
                return self.xml_obj.get("end")
        else:
            return self.ref.end
        
    @property
    def head_start(self):
        if self.ref is None and self.xml_obj.get("head_start") is not None:
            return self.xml_obj.get("head_start")
        elif self.ref is None:
            return None
        else:
            return self.ref.head_start
    
    @property
    def head_end(self):
        if self.ref is None and self.xml_obj.get("head_end") is not None:
            return self.xml_obj.get("head_end")
        elif self.ref is None:
            return None
        else:
            return self.ref.head_end
        
    def get_event(self):
        return self.corr_event
    
    def get_subevents(self):
        return self.corr_subevents
            
    def add_child(self, child):
        self.children.append(child)
        child.parent = self

    def filter_child(self, child, column, filter, collector):
        if child.tag in filter:
            if "dont_annotate" in filter[child.tag]:
                # we ignore children below this, but don't annotate that tag
                return
            if "if_event_use_trigger_instead" in filter[child.tag] and filter[child.tag]["if_event_use_trigger_instead"]:
                if child.ref is not None and child.ref.tag == "Event":
                    new_ref = [c for c in child.ref.children if c.tag == "Trigger"]
                    if new_ref:
                        child.ref = new_ref[0]
            collector.append((column, child))
        else:
            for c in child.children:
                self.filter_child(c, column, filter, collector)

    def filter_children(self, filter):
        filtered_children = []
        for child in self.children:
            for col in filter:
                self.filter_child(child, col, filter[col], filtered_children)
        return filtered_children
    
    def get_child_relative_position(self, child, head_only=False):
        parent_start = self.start if self.xml_obj is not None else 0
        if not head_only or child.head_start is None:
            child_start, child_end = child.start, child.end
        else:
            child_start, child_end = child.head_start, child.head_end
        #print(child_start, child_end, parent_start)
        return int(child_start) - int(parent_start), int(child_end) - int(parent_start)

    
    def get_tag(self, child, column, config):
        """
        Can return an empty string to signify that the span was filtered out.
        """
        tag = []
        info = config["cols"][column][child.tag]
        tag_granularity = config["tag_granularity"][column]
        for key, settings in info.items():
            if key == "tag":
                if settings == "ignore":
                    return ""
                tag.append("tag:"+settings)
                continue
            elif key in ["if_event_use_trigger_instead"]:
                continue

            xml_obj = child.xml_obj
            if "use_xml_parent" in settings and settings["use_xml_parent"] is True:
                xml_obj = child.xml_obj.getparent()
            comp = "_".join(xml_obj.get(key).split("_")[:tag_granularity])
            if "convert" in settings:
                if "condition" in settings["convert"]:
                    fulfilled_all_conditions = False
                    for cond, val in settings["convert"]["condition"].items():
                        if cond == "event_type":
                            if child.corr_event.get("type") != val:
                                break
                    else:
                        fulfilled_all_conditions = True
                else:
                    fulfilled_all_conditions = True
                if fulfilled_all_conditions:
                    if comp in settings["convert"]["dict"]:
                        comp = settings["convert"]["dict"][comp]
            # a bit dirty, doing some filtering here as well
            if "only_freetext" in settings and settings["only_freetext"]:
                if child.xml_obj.get("ref") != "#freetext":
                    return ""
            if "include" in settings and settings["include"] and comp not in settings["include"]:
                return ""
            if "require_xml_grandparent" in settings and settings["require_xml_grandparent"]:
                # a simplified filtering for especially for roles based on their events
                grandparent = child.xml_obj.getparent().getparent()
                for k, v in settings["require_xml_grandparent"].items():
                    if not v:  # an empty list accepts all
                        continue
                    c = grandparent.get(k)
                    if c not in v:
                        return ""
            tag.append(settings["prefix"] + ":" + comp)
        return ";".join(tag)

    def create_conllu(self, filter, modifications):
        for col, child in self.children:
            head_only = True if "only_head" in filter["cols"][col] and filter["cols"][col]["only_head"] else False
            start, end = self.get_child_relative_position(child, head_only)
            if start < 0 and end >= len(self.tokens):
                print(f"Skipping child {child.tag} of tag {self.tag} because child is the outer span.")
                continue 
            tag = self.get_tag(child, col, filter)
            if not tag:
                continue
            self.tokens[start].tags[col] = ("B-" + tag)
            for token in range(start+1, end):
                self.tokens[token].tags[col] = ("I-" + tag)
            # TODO: complement settings for full BIOES scheme instead of BIO

        # add head annotation if wanted
        for col in filter["cols"]:
            if "add_heads" not in filter["cols"][col] or not filter["cols"][col]["add_heads"]:
                continue
            if self.xml_obj is not None and "head_text" in self.xml_obj.attrib and self.xml_obj.get("head_text"):
                start, end = int(self.xml_obj.get("head_start")) - int(self.start), int(self.xml_obj.get("head_end")) - int(self.start)
                tag = "head"
                self.tokens[start].tags[col] = ("B-" + tag)
                self.tokens[start].head[col] = ("B-head")
                for token in range(start+1, end):
                    self.tokens[token].tags[col] = ("I-" + tag)
                    self.tokens[token].head[col] = ("I-head")

        # perform span modifications
        for mod in convert_span_modifications(modifications):
            self.tokens = mod(self, self.tokens)
        # complement all tokens without tags with O
        for token in self.tokens:
            for col in filter["cols"]:
                if col not in token.tags:
                    token.tags[col] = "O"
        column_order = [key for key in filter["cols"].keys() if "dont_print" not in filter["cols"][key] or not filter["cols"][key]["dont_print"]]
        return "".join([t.print_conllu(column_order) for t in self.tokens])


def extract_spans(infile):
    """
    Returns a list of Span objects which hold all necessary sample information.
    Evspans should only be included if they're not already covered by another span
    """
    root = et.parse(infile).getroot() # type: ignore
    tokens = root.xpath("./Text/L/T")
    valid_nodes = root.xpath("./*[self::Mentions or self::Descriptors or self::Values or self::Events]/*")
    spans = {}

    # add document-level span
    id = "doc"
    spans[id] = Span(None, tokens)

    # add the other spans
    for node in valid_nodes:
        id = get_id(node)

        if node.tag == "Event" and node.get("anchor") != "self":
            continue
        
        spans[id] = Span(node, tokens[int(node.get("start")):int(node.get("end"))])

    # establish span hierarchy
    for span_id, span in spans.items():
        id = span_id
        children = root.xpath(f"./Hierarchy/H[@parent='{id}']")
        for child in children:
            child = child.get("child")
            child = root.xpath(f".//*[@id='{child}']")[0]
            id = get_id(child)
            child = spans[id]
            span.add_child(child)

    # add role information to spans
    for event in root.xpath("./Events/Event"):
        event_span_id = event.get("anchor")
        if event_span_id == "self":
            # self implies that the event has its own span in the text
            try:
                event_span = spans[event.get("id")]
            except KeyError:
                print(et.tostring(root, pretty_print=True))
        else:
            event_span = spans[event_span_id]
        trigger = event.find("Trigger")
        if trigger is not None:
            trigger_span = Span(trigger, tokens[int(trigger.get("start")):int(trigger.get("end"))])
            trigger_span.corr_event = event
            event_span.add_child(trigger_span)
        role_set = []
        for subevent in event.findall("Subevent"):
            for role in subevent.findall("Role"):
                if role.get("ref") != "#freetext":
                    ref = spans[role.get("ref")]
                    role_tokens = ref.tokens
                    # only create role if ref isn't in role_set yet
                    already_in = False
                    for x in role_set:
                        if x.ref == ref:
                            x.corr_subevents.add(subevent.get("id"))
                            already_in = True
                            break
                    if already_in:
                        continue
                else:
                    ref = None
                    role_tokens = tokens[int(role.get("start")):int(role.get("end"))]
                    # only create role if textspan isn't in role_set yet
                    already_in = False
                    for x in role_set:
                        if x.start == role.get("start") and x.end == role.get("end"):
                            x.corr_subevents.add(subevent.get("id"))
                            already_in = True
                            break
                    if already_in:
                        continue
                role_span = Span(role, role_tokens, ref=ref)
                role_span.corr_event = event
                role_span.corr_subevents.add(subevent.get("id"))
                event_span.add_child(role_span)
                
                role_set.append(role_span)

    return spans.values()


def filter_spans(spans, config):
    """
    Filter our spans accoring to some rules determined in the filter-dictionary.
    Rules have to be hardcoded in this function.

    When a span is removed because of a filter, all its child spans need to
    be moved to their parent element.
    """
    filtered_spans = []
    for span in spans:
        if span.xml_obj is not None and span.tag not in config["include_spans"]["tags"]:
            continue

        span.children = span.filter_children(config["include_tags"]["cols"])

        if "create_samples_based_on_" in config["include_spans"]:
            import copy
            valid_children = [c for c in span.children if c[0] == config["include_spans"]["create_samples_based_on_"]["column"]]
            
            for _, child in valid_children:
                if child.tag == config["include_spans"]["create_samples_based_on_"]["source"] and \
                    (child.get_event().get("type").split("_")[0] == config["include_spans"]["create_samples_based_on_"]["event_type"] or not config["include_spans"]["create_samples_based_on_"]["event_type"]) and \
                    (child.xml_obj.get("type").split("_")[0] if child.xml_obj.get("type") else "" == config["include_spans"]["create_samples_based_on_"]["type"] or not config["include_spans"]["create_samples_based_on_"]["type"]):
                    
                    span_copy = copy.copy(span)
                    span_copy.tokens = [copy.deepcopy(t) for t in span_copy.tokens]
                    span_copy.children = [c for c in span_copy.children]
                    # remove role children which are not of the same event as the trigger
                    for col, chi in copy.copy(span.children):
                        if col != config["include_spans"]["create_samples_based_on_"]["column"]:
                            continue
                        if chi.tag in ["Role", "Trigger"]:
                            if config["include_spans"]["create_samples_based_on_"]["use_subevent"]:
                                if not chi.get_subevents().intersection(child.get_subevents()):
                                    span_copy.children.remove((col, chi))
                            else:
                                if chi.get_event() != child.get_event():
                                    span_copy.children.remove((col, chi))
                    
                    filtered_spans.append(span_copy)
        else:
            filtered_spans.append(span)

    return filtered_spans


def shorten_annotations_to_heads(span_elem, full_column="ner", head_column="ner_only_head"):
    """
    Remove all tokens which are not part of the head of the entity span they're contained within.
    If a token was originally a B-tag, the next valid token must receive the B- instead
    """
    tokens = span_elem.tokens
    out = []
    beginning_tag_waiting = set()
    for token in tokens:
        if (full_column not in token.tags or token.tags[full_column] == "O") or full_column in token.head:
            out.append(token)
            for col in beginning_tag_waiting:
                token.tags[col] = "B-" + token.tags[col][2:]
            beginning_tag_waiting = set()
                
        else:
            if head_column in token.tags:
                out.append(token)
                for col in beginning_tag_waiting:
                    token.tags[col] = "B-" + token.tags[col][2:]
                beginning_tag_waiting = set()
            else:
                for col, tag in token.tags.items():
                    if tag[:2] == "B-":
                        beginning_tag_waiting.add(col)


    return out


def add_annotations(tokens, anno_col, specific_tag_conversion=None, include_anno_col=True, triggerfocus_col=None, sourcefocus_col=None):
    """
    Insert a special token in the token-list which marks the beginning
    or the end of an NER span.
    """
    current_tag = "O"
    previous_tags = None
    new_token_sequence = []
    for token in tokens:
        if anno_col in token.tags and token.tags[anno_col] != "O":
            prefix = token.tags[anno_col][:2]
            tag = token.tags[anno_col][2:]  # remove B- / I-

            if sourcefocus_col is not None and (sourcefocus_col in token.tags and token.tags[sourcefocus_col][2:].startswith("tag:role;r:beneficiary")):
                tag = "tag:role;r:source"

            if triggerfocus_col is not None and tag.startswith("tag:tr") and (triggerfocus_col not in token.tags or not token.tags[triggerfocus_col][2:].startswith("tag:tr")):
                #prefix = ""
                #tag = "O"
                tag = "tag:tr;t:inactive"
            #else:
            if specific_tag_conversion is not None:
                spec_tag = specific_tag_conversion(tag)
        else:
            prefix = ""
            tag = "O"
        if (tag != current_tag or prefix == "B-") and tag != "O" and current_tag != "O":
            # marks ending of a span
            spec_current_tag = current_tag if specific_tag_conversion is None else specific_tag_conversion(current_tag)
            new_token_sequence.append(
                Token(
                    "[E-" + spec_current_tag + "]",
                    tags=previous_tags.copy()  # TODO: implement settings for BIOES system # type: ignore
                )
            )
            new_token_sequence.append(
                Token(
                    "[B-" + spec_tag + "]",
                    tags=token.tags.copy()
                )
            )
            for col in token.tags:
                token.tags[col] = "I-" + token.tags[col][2:]
            new_token_sequence.append(token)
        elif tag != current_tag and tag != "O":
            # marks beginning of a span
            new_token_sequence.append(
                Token(
                    "[B-" + spec_tag + "]",
                    tags=token.tags.copy()
                )
            )
            for col in token.tags:
                token.tags[col] = "I-" + token.tags[col][2:]
            new_token_sequence.append(token)
        elif tag != current_tag and tag == "O":
            # marks ending of a span
            new_token_sequence.append(
                Token(
                    "[E-" + spec_tag + "]",
                    tags=previous_tags.copy()  # TODO: implement settings for BIOES system # type: ignore
                )
            )
            new_token_sequence.append(token)
        else:
            new_token_sequence.append(token)
        current_tag = tag
        previous_tags = token.tags

    if current_tag != "O":
        # we need to finish the last tag
        new_token_sequence.append(
                Token(
                    "[E-" + spec_tag + "]",
                    tags=previous_tags.copy()  # TODO: implement settings for BIOES system # type: ignore
                )
            )

    if not include_anno_col:
        for token in new_token_sequence:
            if anno_col in token.tags:
                del token.tags[anno_col]

    return new_token_sequence


def upper_case_tags(tag):
    if tag == "doc":
        return tag.upper()
    elif tag in ["Reference", "Attribute"]:
        return tag[:3].upper()
    elif tag in ["Descriptor"]:
        return tag[:4].upper()
    else:
        return tag.upper()
    
def upper_case_entity_values(tag):
    if tag == "O":
        return tag
    if tag == "head":
        return tag.upper()
    info = dict([t.split(":") for t in tag.split(";")])
    if info["tag"] in ["ref", "att"]:
        out = info["ent"]
    elif info["tag"] in ["val"]:
        out = info["val"]
    elif info["tag"] in ["desc"]:
        out = info["desc"]
    elif info["tag"] in ["tr"]:
        out = info["t"]
    elif info["tag"] in ["role"]:
        out = info["r"]
    else:
        print(info["tag"])
        raise NotImplementedError

    return out.upper()


def mod_only_beginning_tags(tokens, command):
    """
    Remove all tags which are not Beginnings (B-).
    We use this when we only want to categorize pretags.
    """
    column = command.split("_")[-1]
    for token in tokens:
        if column in token.tags and token.tags[column] != "O":
            prefix = token.tags[column][:2]
            tag = token.tags[column][2:]
            if prefix != "B-":
                token.tags[column] = "O"
    return tokens


def mod_add_parent_tag(span_obj):
    tag = "[" + upper_case_tags(span_obj.tag) + "]"
    token = Token(
        text=tag,
        tags={}
    )
    span_obj.tokens.insert(0, token)
    span_obj.tokens.append(token)
    return span_obj.tokens


def process_document(infile, config) -> str:
    spans = extract_spans(infile)
    spans = filter_spans(spans, config)
    out = []
    for span in sorted(spans, key=lambda x: (int(x.start), -int(x.end)) if x.xml_obj is not None else (0, 9999)):
        outstring = span.create_conllu(config["include_tags"], config["include_tags"]["span_modifications"])
        out.append(outstring)
    return "\n".join(out)


def convert_span_modifications(input):
    for i in input:
        if i == "add_parent_tag":
            yield lambda y, x: mod_add_parent_tag(y)
        elif i == "add_annotation_ner":
            yield lambda y, x: add_annotations(x, "ner", specific_tag_conversion=lambda x: upper_case_entity_values(x))
        elif i == "add_annotation_ner_only_head":
            yield lambda y, x: add_annotations(x, "ner_only_head", specific_tag_conversion=lambda x: upper_case_entity_values(x))
        elif i == "add_annotation_ner_only_head_triggerfocus":
            yield lambda y, x: add_annotations(x, "ner_only_head", specific_tag_conversion=lambda x: upper_case_entity_values(x), triggerfocus_col="evts")
        elif i == "add_annotation_ner_triggerfocus":
            yield lambda y, x: add_annotations(x, "ner", specific_tag_conversion=lambda x: upper_case_entity_values(x), triggerfocus_col="evts")
        elif i == "add_annotation_ner_sourcefocus":
            yield lambda y, x: add_annotations(x, "ner", specific_tag_conversion=lambda x: upper_case_entity_values(x), sourcefocus_col="evts")
        elif i == "add_annotation_sbevts_sourcefocus":
            yield lambda y, x: add_annotations(x, "evts", specific_tag_conversion=lambda x: upper_case_entity_values(x), sourcefocus_col="sbevts")
        elif i.startswith("only_beginning_tags_"):
            yield lambda y, x: mod_only_beginning_tags(x, i)
        elif i == "shorten_annotations_to_head":
            yield lambda y, x: shorten_annotations_to_heads(y)


if __name__ == "__main__":
    import json
    import glob
    config = json.load(open("./data/transformation_configs/ner_nested/ner_nested_plus_roles.json", mode="r", encoding="utf8"))

    infiles = glob.glob("./data/std_xml/test/*.xml")
    for infile in infiles:
        print("# " + infile)
        spans = extract_spans(infile)
        spans = filter_spans(spans, config)
        for span in sorted(spans, key=lambda x: (int(x.start), -int(x.end)) if x.xml_obj is not None else (0, 9999)):
            outstring = span.create_conllu(config["include_tags"], config["include_tags"]["span_modifications"])
            print(outstring)