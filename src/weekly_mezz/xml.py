from bs4 import BeautifulSoup
from lxml import etree


def parse_xml_with_recovery(text: str):
    parser = etree.XMLParser(recover=True, encoding="utf-8")
    root = etree.fromstring(text.encode("utf-8", errors="ignore"), parser=parser)
    recovered_xml = etree.tostring(root, encoding="unicode")
    return BeautifulSoup(recovered_xml, "lxml-xml")

