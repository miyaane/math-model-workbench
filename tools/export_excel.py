"""Portable numeric fill of existing XLSX template cells (Python stdlib only).

Preserves every ZIP member and all worksheet text except targeted cell contents.
Formula-bearing templates are rejected: this tool is not a calculation engine.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import posixpath
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export_numeric(template, output, updates, number_format=None):
    """updates: {sheet_name: {existing_A1_address: finite_number}}."""
    template, output = Path(template), Path(output)
    if template.resolve() == output.resolve() or output.exists():
        raise ValueError('Output must be a new file, separate from the template')
    if template.suffix.lower() != '.xlsx' or output.suffix.lower() != '.xlsx':
        raise ValueError('Only .xlsx is supported')
    if not updates or not any(updates.values()):
        raise ValueError('No updates supplied')
    with zipfile.ZipFile(template) as src:
        infos = src.infolist()
        if len({x.filename for x in infos}) != len(infos):
            raise ValueError('Duplicate ZIP members')
        members = {i.filename: src.read(i.filename) for i in infos}
    if any(n.startswith('_xmlsignatures/') for n in members):
        raise ValueError('Signed templates must not be modified')
    rels = ET.fromstring(members['xl/_rels/workbook.xml.rels'])
    paths = {r.attrib['Id']: posixpath.normpath('xl/' + r.attrib['Target'])
             if not r.attrib['Target'].startswith('/') else r.attrib['Target'].lstrip('/')
             for r in rels if r.attrib.get('TargetMode') != 'External'}
    root = ET.fromstring(members['xl/workbook.xml'])
    sheets = {s.attrib['name']: paths[s.attrib[REL]]
              for s in root.findall('s:sheets/s:sheet', NS)}
    # Refuse cached formula results that could become stale on numeric changes.
    for name, raw in members.items():
        if name.startswith('xl/worksheets/') and name.endswith('.xml'):
            if ET.fromstring(raw).find('.//s:f', NS) is not None:
                raise ValueError('Formula templates require a separate recalculation engine')
    changed = {}
    style_map = {}
    if number_format is not None:
        from xml.sax.saxutils import escape
        if not isinstance(number_format,str) or not number_format:
            raise ValueError('number_format must be nonempty text')
        style_xml=members['xl/styles.xml'].decode('utf-8')
        fmt_id=max([163]+[int(x) for x in re.findall(r'numFmtId="(\d+)"',style_xml)])+1
        fmt=f'<numFmt numFmtId="{fmt_id}" formatCode="{escape(number_format, {chr(34): "&quot;"})}"/>'
        match=re.search(r'<numFmts\b[^>]*(?:/>|>.*?</numFmts>)',style_xml,re.S)
        if match:
            node=ET.fromstring(match[0]);children=''.join(re.findall(r'<numFmt\b[^>]*/>',match[0]))
            style_xml=style_xml[:match.start()]+f'<numFmts count="{len(node)+1}">'+children+fmt+'</numFmts>'+style_xml[match.end():]
        else:
            pos=style_xml.index('>',style_xml.index('<styleSheet'))+1
            style_xml=style_xml[:pos]+f'<numFmts count="1">{fmt}</numFmts>'+style_xml[pos:]
        match=re.search(r'<cellXfs\b[^>]*>(.*?)</cellXfs>',style_xml,re.S)
        if not match: raise ValueError('Unsupported styles table')
        xfs=re.findall(r'<xf\b[^>]*(?:/>|>.*?</xf>)',match[1],re.S)
        additions=[]
        for i,xf in enumerate(xfs):
            new=re.sub(r'numFmtId="\d+"',f'numFmtId="{fmt_id}"',xf,count=1)
            if 'numFmtId=' not in new:new=new.replace('<xf ',f'<xf numFmtId="{fmt_id}" ',1)
            new=re.sub(r'\s+applyNumberFormat="[^"]*"','',new)
            new=new.replace('<xf ', '<xf applyNumberFormat="1" ',1)
            style_map[i]=len(xfs)+len(additions);additions.append(new)
        style_xml=style_xml[:match.start()]+f'<cellXfs count="{len(xfs)+len(additions)}">'+match[1]+''.join(additions)+'</cellXfs>'+style_xml[match.end():]
        changed['xl/styles.xml']=style_xml.encode('utf-8')
    count = 0
    for sheet, values in updates.items():
        if sheet not in sheets:
            raise ValueError(f'Unknown sheet: {sheet}')
        member = sheets[sheet]
        xml = members[member].decode('utf-8')
        cells = {c.attrib['r']: c for c in ET.fromstring(xml).findall('.//s:sheetData/s:row/s:c', NS)}
        for addr, value in values.items():
            if not re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]*', addr) or addr not in cells:
                raise ValueError(f'Missing/invalid template cell: {sheet}!{addr}')
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f'Non-finite/non-numeric value: {sheet}!{addr}')
        seen = set()
        pattern = re.compile(r'<c\b([^>]*?)(?:\s*/>|>(.*?)</c>)', re.S)
        def replace(match):
            address = re.search(r'\br="([A-Z]+[0-9]+)"', match.group(1))
            if not address or address[1] not in values:
                return match[0]
            addr = address[1]
            if addr in seen:
                raise ValueError(f'Duplicated cell: {sheet}!{addr}')
            seen.add(addr)
            attrs = re.sub(r'\s+t="[^"]*"', '', match.group(1))
            if number_format is not None:
                old_style=int(cells[addr].attrib.get('s','0'))
                attrs=re.sub(r'\s+s="[^"]*"','',attrs)+f' s="{style_map[old_style]}"'
            return f'<c{attrs}><v>{repr(values[addr])}</v></c>'
        xml = pattern.sub(replace, xml)
        if seen != set(values):
            raise ValueError(f'Unsupported cell XML in sheet {sheet}')
        count += len(seen)
        changed[member] = xml.encode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.xlsx', delete=False) as f:
        temp = Path(f.name)
    try:
        with zipfile.ZipFile(temp, 'w') as dst:
            for info in infos:
                dst.writestr(info, changed.get(info.filename, members[info.filename]))
        with zipfile.ZipFile(temp) as check:
            if check.testzip() is not None:
                raise ValueError('Corrupt output ZIP')
            for name, raw in members.items():
                if name not in changed and check.read(name) != raw:
                    raise ValueError(f'Unexpected member change: {name}')
            for sheet, values in updates.items():
                cells = {c.attrib['r']: c for c in ET.fromstring(check.read(sheets[sheet])).findall('.//s:c', NS)}
                for addr, expected in values.items():
                    if float(cells[addr].find('s:v', NS).text) != expected:
                        raise ValueError(f'Readback mismatch: {sheet}!{addr}')
        # Exclusive creation also works on filesystems without hard-link support.
        import shutil
        with output.open('xb') as dest, temp.open('rb') as source:
            shutil.copyfileobj(source, dest)
    finally:
        temp.unlink(missing_ok=True)
    return dict(passed=True, checked_numeric_cells=count, template_sha256=sha(template),
                output_sha256=sha(output), unchanged_zip_members=len(members)-len(changed),
                engine='python-stdlib-ooxml', recalculation='not applicable: formula-free template')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest', type=Path)
    args = ap.parse_args()
    spec = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    base = args.manifest.resolve().parent
    report = export_numeric(base/spec['template'], base/spec['output'], spec['updates'], spec.get('number_format'))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
