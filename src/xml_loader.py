from bs4 import BeautifulSoup
from lxml import etree


def parse_xml_with_recovery(text):
    parser = etree.XMLParser(recover=True, huge_tree=True)
    try:
        root = etree.fromstring(text.encode("utf-8"), parser=parser)
        normalized_xml = etree.tostring(root, encoding="unicode")
        return BeautifulSoup(normalized_xml, "lxml-xml")
    except Exception:
        try:
            return BeautifulSoup(text, "lxml-xml")
        except Exception:
            return BeautifulSoup(text, "html.parser")
