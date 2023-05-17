# Read XMI standoff annotation file and convert it into a XML file similar to TEI with standoff annotation for relationships
# Export the files from Inception as UIMA CAS XMI (XML 1.1) and put them (unzipped!) in the folder named unter "infiles"
# Important: This code assumes no intersecting entities!

import glob

infiles = glob.glob("testfiles/*.xmi")

from lxml import etree as et
from xml.sax.saxutils import escape

ENTITY_TYPES = ["NAM", "NOM", "PRO", "UNK"]

DEFAULT_VALUES = {
    "ent_num_type": "SGL"
}

def create_node_tree(in_root, document_text):
    """
    This node tree is mostly just as a help, but the code may probably easily be adopted to port everything to a TEI-format.
    """
    spans = in_root.findall(".//custom:Span", namespaces={"custom":"http:///custom.ecore"})
    # note which entity and which tag, start or end, needs to be inserted at this point
    sorted_spans = []
    for ent in spans:
        sorted_spans.append((ent, int(ent.get("begin")), int(ent.get("end"))))
    sorted_spans.sort(key=lambda x: (x[1], -x[2]))
    work_root = et.Element("XML", nsmap={"custom":"http:///custom.ecore", "cas":"http:///uima/cas.ecore"})
    parent_node = work_root
    for entity, start, end in sorted_spans:
        # classify if span is entity, attribute or description
        label = entity.get('label')
        label = label.split(".")
        span_type = None
        if label[0] in ENTITY_TYPES:
            span_type = "ent"
        elif label[0] == "att":
            span_type = "att"
        elif label[0] == "desc":
            span_type = "desc"
        elif label[0] == "head":
            span_type = "head"
        else:
            print(f"WARNING: Unrecognized Span Label {label[0]}!")
        # we need to check all parent nodes above if they contain the current node
        while(parent_node != work_root):
            if end <= int(parent_node.get("end")):
                current_node = et.SubElement(parent_node, "Entity", id=entity.get("{http://www.omg.org/XMI}id"), span_type=span_type, label=entity.get('label'), start=str(start), end=str(end), text=document_text[start:end])
                break
            else:
                parent_node = parent_node.getparent()
        else:
            current_node = et.SubElement(work_root, "Entity", id=entity.get("{http://www.omg.org/XMI}id"), span_type=span_type, label=entity.get('label'), start=str(start), end=str(end), text=document_text[start:end])
        parent_node = current_node
    
    # We get relations from three sources: relation layer, att and desc
    relations = in_root.findall(".//custom:Relation", namespaces={"custom":"http:///custom.ecore"})
    for relation in relations:
        current_node = et.SubElement(
            work_root, 
            "Relation", 
            id=relation.get("{http://www.omg.org/XMI}id"), 
            label=relation.get("label"),
            from_entity=relation.get("Governor"),
            to_entity=relation.get("Dependent"),
            )

    return work_root

old_to_new_ids = {}

def write_entities(out_root, work_root, document_text):
    # I renamed Entity to Mention here as it's a more accurate descriptor
    entities_node = et.SubElement(out_root, "Mentions")

    for entity in work_root.findall(".//Entity[@span_type='ent']"):
        label = entity.get('label')
        label = label.split(".")
        if len(label) == 2:
            mention_type, entity_type = label
            num_type = DEFAULT_VALUES["ent_num_type"]  # default value
        elif len(label) == 3:
            mention_type, entity_type, num_type = label

        head_elem = entity.find("Entity[@label='head']")
        if head_elem == None:
            # Implizierter Head
            # print(f"Warning: Implizierter Head bei {entity.get('id')}.")
            head_start = entity.get("start")
            head_end = entity.get("end")
        else:
            head_start = head_elem.get("start")
            head_end = head_elem.get("end")

        # TODO: Decide if this reference is new or carries a coreference to a previous entity
        mention_id = len(old_to_new_ids)
        old_to_new_ids[entity.get("id")] = mention_id

        et.SubElement(entities_node, 
            "Reference",
            mention_id=str(mention_id), 
            mention_type=mention_type,
            entity_type=entity_type,
            num_type=num_type,
            start=entity.get("start"),
            end=entity.get("end"),
            head_start=head_start,
            head_end=head_end,
            head_text=document_text[int(head_start):int(head_end)]
            )
    
    for entity in work_root.findall(".//Entity[@span_type='att']"):
        # TODO: Können PRO auch ATT sein oder nicht? Oder dann immer als DESC taggen?
        parent = entity.getparent()
        label = parent.get('label')
        label = label.split(".")
        if len(label) == 2:
            mention_type, entity_type = label
            num_type = DEFAULT_VALUES["ent_num_type"]  # default value
        elif len(label) == 3:
            mention_type, entity_type, num_type = label
        # overwrite mention type
        mention_type = "NOM"

        head_elem = entity.find("Entity[@label='head']")
        if head_elem == None:
            # Implizierter Head
            print(f"Warning: Implizierter Head bei {entity.get('id')}.")
            head_start = entity.get("start")
            head_end = entity.get("end")
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
            entity_type=entity_type + "_" + entity.get("label").split(".")[1].upper(),
            num_type=num_type,
            start=entity.get("start"),
            end=entity.get("end"),
            head_start=head_start,
            head_end=head_end,
            head_text=document_text[int(head_start):int(head_end)]
            )
        
    # NOTE: Should we only add those descriptors that are NOT also relations?
    description_node = et.SubElement(out_root, "Descriptors")    
    for desc in work_root.findall(".//Entity[@span_type='desc']"):
        label = desc.get('label')
        label = label.split(".")
        desc_type = label[1]

        # TODO: Give this a reference to the entity that it describes

        et.SubElement(description_node, 
            "Descriptor",
            desc_type=desc_type,
            start=desc.get("start"),
            end=desc.get("end"),
            text=document_text[int(desc.get("start")):int(desc.get("end"))]
            )
        
    
def write_relations(out_root, work_root, document_text):
    relations_node = et.SubElement(out_root, "Relations") 

    # First, the easy ones that were tagged as relations
    for relation in work_root.findall(".//Relation"):
        et.SubElement(relations_node, 
            "Relation",
            rel_type=relation.get("label"),
            from_mention=str(old_to_new_ids[relation.get("from_entity")]),
            to_mention=str(old_to_new_ids[relation.get("to_entity")]),
            )
    
    # now the implied relations from att and desc (and entities which are PRO and NOM possibly!)
    # basically, if there is another mention inside an att or a desc, we have a relation between the original mention and the one inside
    for entity in work_root.findall(".//Entity[@span_type='att']"):
        label = entity.get('label')
        label = label.split(".")[1]

        # check if an entity is included in this span, then this is what the relationship refers to
        # if there is no entity included, it's not a relationship
        # NOTE: Depending on the implementation, we may want the option to have multiple entities included and then make a relation for each
        # NOTE: This implementation only works if we don't assume missing relationship partners
        child_entity = entity.find("./Entity[@span_type='ent']")
        if child_entity is None:
            continue
        
        et.SubElement(relations_node, 
            "Relation",
            rel_type=label,
            from_mention=str(old_to_new_ids[entity.get("id")]),
            to_mention=str(old_to_new_ids[child_entity.get("id")]),
            )
    
    # desc work almost the same as att, but the connected id is that of the parent element instead
    for descriptor in work_root.findall(".//Entity[@span_type='desc']"):
        parent = descriptor.getparent()
        label = descriptor.get('label')
        label = label.split(".")[1]

        # check if an entity is included in this span, then this is what the relationship refers to
        # if there is no entity included, it's not a relationship
        # NOTE: Depending on the implementation, we may want the option to have multiple entities included and then make a relation for each
        child_entity = descriptor.find("./Entity[@span_type='ent']")
        if child_entity is None:
            continue
        
        et.SubElement(relations_node, 
            "Relation",
            rel_type=label,
            from_mention=str(old_to_new_ids[parent.get("id")]),
            to_mention=str(old_to_new_ids[child_entity.get("id")]),
            )
        
    # finally, sometimes there are NOM and PRO elements which carry relationship information such as "sin frow" which would be a NOM.PER.REL
    # the problem here is the current annotation, which does not make it easy to distinguish these information from ordinality information


def process_xmi(xmi_file):
    infile = et.parse(xmi_file)
    in_root = infile.getroot()

    text_node = in_root.find("./cas:Sofa", namespaces={"cas":"http:///uima/cas.ecore"})
    document_text = text_node.get("sofaString")
    document_text_no_breaks = document_text.replace("\n", " ")

    work_root = create_node_tree(in_root, document_text)

    work_tree = et.ElementTree(work_root)
    work_tree.write('debug.xml', xml_declaration=True, pretty_print=True, encoding="utf8")

    out_root = et.Element("XML")

    # TODO: Write DocumentMetaData
    out_text = et.SubElement(out_root, "Text")
    out_text.text = document_text
    write_entities(out_root, work_root, document_text_no_breaks)
    # TODO: Write Value Annotations
    write_relations(out_root, work_root, document_text_no_breaks)
    # TODO: Write Events

    #document_text = document_text.replace("&", "&amp;")
    #work_root = et.fromstring("<XML>" + document_text + "</XML>")

    out_tree = et.ElementTree(out_root)
    out_tree.write('output.xml', xml_declaration=True, pretty_print=True, encoding="utf8")


for infile in infiles:
    xml_file = process_xmi(infile)
    break
    #write_xml(xml_file)