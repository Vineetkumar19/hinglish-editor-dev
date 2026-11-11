"""Replace incoming timeline XML parsing with entity-safe parsing; keep XML writers unchanged."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    changed=[]
    for folder in ROOT.glob('hinglish_*'):
        for file in folder.rglob('*.py'):
            source=file.read_text(encoding='utf-8')
            if 'ET.parse(' not in source:continue
            if 'import xml.etree.ElementTree as ET' not in source:raise RuntimeError('Review the XML import in '+str(file))
            source=source.replace('ET.parse(','SafeET.parse(')
            source=source.replace('import xml.etree.ElementTree as ET','import xml.etree.ElementTree as ET\nfrom defusedxml import ElementTree as SafeET')
            file.write_text(source,encoding='utf-8');changed.append(str(file.relative_to(ROOT)))
    print('Hardened incoming XML parsing in '+str(len(changed))+' modules.')


if __name__=='__main__':main()
