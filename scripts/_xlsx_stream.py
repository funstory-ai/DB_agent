"""Minimal streaming xlsx reader (stdlib only) for very large files.

Parses xl/sharedStrings.xml, xl/workbook.xml (sheet name->rid) and
xl/_rels/workbook.xml.rels (rid->target), then streams each worksheet via
iterparse so we never hold the whole file in memory.
"""
import zipfile
import re
import xml.etree.ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _col_to_idx(ref):
    # 'A1' -> 0 ; 'AB12' -> 27
    m = re.match(r"([A-Z]+)(\d+)", ref)
    if not m:
        return 0
    letters = m.group(1)
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def read_shared_strings(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    data = z.read("xl/sharedStrings.xml")
    root = ET.fromstring(data)
    out = []
    for si in root.findall(f"{{{NS}}}si"):
        # concatenate all <t> text under this <si>
        txt = "".join(t.text or "" for t in si.iter(f"{{{NS}}}t"))
        out.append(txt)
    return out


def sheet_map(z):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {}
    for rel in rels:
        rid_to_target[rel.get("Id")] = rel.get("Target")
    name_to_file = {}
    for sh in wb.find(f"{{{NS}}}sheets"):
        name = sh.get("name")
        rid = sh.get(f"{{{RNS}}}id")
        tgt = rid_to_target.get(rid, "")
        if not tgt.startswith("xl/"):
            tgt = "xl/" + tgt.lstrip("/")
        name_to_file[name] = tgt
    return name_to_file


def _parse_value(c, shared):
    t = c.get("t")
    v = c.find(f"{{{NS}}}v")
    isn = c.find(f"{{{NS}}}is")
    if v is None and isn is None:
        return None
    if t == "s":
        if v is not None:
            return shared[int(v.text)]
        return None
    if t == "inlineStr":
        return "".join(tt.text or "" for tt in isn.iter(f"{{{NS}}}t"))
    if t == "b":
        return (v.text == "1")
    if v is not None:
        try:
            if "." in v.text:
                return float(v.text)
            return int(v.text)
        except (ValueError, TypeError):
            return v.text
    return None


def iter_sheet_rows(z, sheet_file, shared, max_rows=None):
    """Yield rows as lists of cell values (None for empty)."""
    data = z.read(sheet_file)
    cur_row = None
    cur_cells = {}
    row_no = 0
    max_c = 0
    for ev, el in ET.iterparse(z.open(sheet_file), events=("end",)):
        tag = el.tag
        if tag == f"{{{NS}}}c":
            ref = el.get("r")
            ci = _col_to_idx(ref) if ref else max_c
            val = _parse_value(el, shared)
            cur_cells[ci] = val
            max_c = max(max_c, ci + 1)
            el.clear()
        elif tag == f"{{{NS}}}row":
            row_no += 1
            n = (cur_row if cur_row else 0)
            # build contiguous list
            width = (max(cur_cells) + 1) if cur_cells else 0
            row_list = [cur_cells.get(i) for i in range(width)]
            cur_cells = {}
            max_c = 0
            yield row_list
            if max_rows and row_no >= max_rows:
                break
            el.clear()


def read_xlsx(path, sheets=None, max_rows=None):
    """Return {sheet_name: [rows...]} ; header is row 0."""
    with zipfile.ZipFile(path) as z:
        shared = read_shared_strings(z)
        smap = sheet_map(z)
        result = {}
        names = sheets if sheets else list(smap.keys())
        for name in names:
            f = smap.get(name)
            if not f or f not in z.namelist():
                continue
            rows = list(iter_sheet_rows(z, f, shared, max_rows))
            result[name] = rows
        return result


if __name__ == "__main__":
    import sys
    p = sys.argv[1]
    d = read_xlsx(p)
    for k, v in d.items():
        print(k, "rows:", len(v))
        if v:
            print("  header:", v[0])
            if len(v) > 1:
                print("  row1:", v[1])
