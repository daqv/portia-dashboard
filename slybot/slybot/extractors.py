import re

from scrapely.extractors import htmlregion

from slybot.fieldtypes import FieldTypeManager
from slybot.item import SlybotFieldDescriptor


def create_regex_extractor(pattern):
    """Create extractor from a regular expression.
    Only groups from match are extracted and concatenated, so it
    is required to define at least one group. Ex:
    >>> extractor = create_regex_extractor("(\d+).*(\.\d+)")
    >>> extractor(u"The price of this product is <div>45</div> </div class='small'>.50</div> pounds")
    u'45.50'
    """
    ereg = re.compile(pattern, re.S)

    def _extractor(txt, htmlpage=None):
        m = ereg.search(txt)
        if m:
            return htmlregion(u"".join([g for g in m.groups() or m.group() if g]))

    _extractor.__name__ = "Regex: %s" % pattern.encode("utf-8")
    return _extractor

def create_type_extractor(type):
    types = FieldTypeManager()
    extractor = types.type_processor_class(type)()
    def _extractor(txt, htmlpage=None):
        data = extractor.extractor(txt)
        if data:
            return extractor.adapt(data, htmlpage)
    _extractor.__name__ = "Type Extractor: %s" % type
    return _extractor

class PipelineExtractor:
    def __init__(self, *extractors):
        self.extractors = extractors

    def __call__(self, value):
        for extractor in self.extractors:
            value = extractor(value) if value else value
        return value

    @property
    def __name__(self):
        return repr(self.extractors)


def apply_extractors(descriptor, template_extractors, extractors):
    field_type_manager = FieldTypeManager()
    if isinstance(template_extractors, dict):
        template_extractors = template_extractors.items()
    for field_name, field_extractors in template_extractors:
        equeue = []
        for eid in field_extractors:
            extractor_doc = extractors.get(eid, {})
            if "regular_expression" in extractor_doc:
                equeue.append(create_regex_extractor(extractor_doc["regular_expression"]))
            elif "type_extractor" in extractor_doc:  # overrides default one
                display_name = descriptor.attribute_map[field_name].description
                field_type = field_type_manager.type_processor_class(extractor_doc["type_extractor"])()
                descriptor.attribute_map[field_name] = SlybotFieldDescriptor(
                    field_name, display_name, field_type)
        if field_name not in descriptor.attribute_map:
            # if not defined type extractor, use text type by default, as it is by far the most commonly used
            descriptor.attribute_map[field_name] = SlybotFieldDescriptor(field_name,
                    field_name, field_type_manager.type_processor_class("text")())

        if equeue:
            equeue.insert(0, descriptor.attribute_map[field_name].extractor)
            descriptor.attribute_map[field_name].extractor = PipelineExtractor(*equeue)

def add_extractors_to_descriptors(descriptors, extractors):
    new_extractors = {}
    for _id, data in extractors.items():
        if "regular_expression" in data:
            extractor = create_regex_extractor(data['regular_expression'])
        else:
            extractor = create_type_extractor(data['type_extractor'])
        new_extractors[_id] = extractor
    for descriptor in descriptors.values():
        descriptor.extractors = new_extractors
