"""Conservative SFZ 1.x parser for library auditing.

Supports #include, #define (simple substitution), control/default_path,
global/master/group/region scope inheritance, quoted values, multiline
opcodes, note/velocity ranges and safe sample-path resolution.
It never edits SFZ files or sample files.
"""
from __future__ import annotations
import re
from pathlib import Path

TAG_RE = re.compile(r"<\s*([A-Za-z_][A-Za-z0-9_]*)\s*>")
OP_RE = re.compile(r"""([A-Za-z][A-Za-z0-9_]*)\s*=\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\s]+)""")
INCLUDE_RE = re.compile(r"""^\s*#include\s+["']([^"']+)["']""", re.I)
DEFINE_RE = re.compile(r"""^\s*#define\s+(\S+)\s+(.+?)\s*$""", re.I)

def _clean_line(line: str) -> str:
    # SFZ comments are // to end of line. Quoted strings are preserved.
    out=[]; quote=None; escaped=False; i=0
    while i < len(line):
        c=line[i]
        if quote:
            out.append(c)
            if escaped: escaped=False
            elif c == "\\": escaped=True
            elif c == quote: quote=None
            i+=1; continue
        if c in "\"'": quote=c; out.append(c); i+=1; continue
        if line.startswith("//", i): break
        out.append(c); i+=1
    return "".join(out)

def _unquote(value: str) -> str:
    value=value.strip()
    if len(value)>=2 and value[0]==value[-1] and value[0] in "\"'":
        return value[1:-1].replace(r'\"','"').replace(r"\'","'")
    return value

def _num(opcodes: dict, key: str):
    value=opcodes.get(key)
    if value is None: return None
    try: return int(float(value))
    except (TypeError, ValueError): return None

def parse_sfz_file(sfz_path: Path, library_root: Path) -> list[dict]:
    sfz_path=sfz_path.resolve()
    library_root=library_root.resolve()
    output=[]
    defines={}
    visited=set()
    region_counter=0

    def parse_file(path: Path, inherited: dict, default_path: str, include_stack: tuple):
        nonlocal region_counter
        path=path.resolve()
        if path in include_stack:
            output.append({"sfz_file":str(sfz_path),"source_sfz":str(path),
                           "region":"","sample_opcode":"","resolved_sample":"",
                           "status":"INCLUDE_CYCLE"})
            return
        if not path.is_file():
            output.append({"sfz_file":str(sfz_path),"source_sfz":str(path),
                           "region":"","sample_opcode":"","resolved_sample":"",
                           "status":"INCLUDE_MISSING"})
            return
        try: lines=path.read_text(encoding="utf-8-sig",errors="replace").splitlines()
        except OSError as exc:
            output.append({"sfz_file":str(sfz_path),"source_sfz":str(path),
                           "region":"","sample_opcode":"","resolved_sample":"",
                           "status":"SFZ_READ_ERROR:"+type(exc).__name__})
            return
        scopes={"global":{}, "master":{}, "group":{}, "region":{}}
        active=None
        local_default=default_path
        pending=""
        for raw in lines:
            line=_clean_line(raw).strip()
            if not line: continue
            inc=INCLUDE_RE.match(line)
            if inc:
                target=(path.parent / inc.group(1).replace("\\","/")).resolve()
                parse_file(target, {**inherited, **scopes["global"], **scopes["master"],
                                    **scopes["group"]}, local_default, include_stack+(path,))
                continue
            dm=DEFINE_RE.match(line)
            if dm:
                defines[dm.group(1)]=dm.group(2).strip()
                continue
            line=re.sub(r'\$[A-Za-z_][A-Za-z0-9_]*',
                        lambda m: defines.get(m.group(0),m.group(0)), line)
            pending += " " + line
            # Process any number of tags on this logical line.
            while True:
                tm=TAG_RE.search(pending)
                if not tm: break
                before=pending[:tm.start()].strip()
                if active and before:
                    scopes[active].update({k.lower():_unquote(v) for k,v in OP_RE.findall(before)})
                tag=tm.group(1).lower()
                active=tag if tag in scopes else None
                pending=pending[tm.end():]
            if active is None: continue
            # control/default_path is file-local and applies to later regions.
            ops={k.lower():_unquote(v) for k,v in OP_RE.findall(pending)}
            if active=="control" and "default_path" in ops:
                local_default=ops["default_path"]
            elif active in scopes:
                scopes[active].update(ops)
            pending=""
        if active and pending.strip():
            scopes[active].update({k.lower():_unquote(v) for k,v in OP_RE.findall(pending)})
        # The last region is represented by the accumulated region scope.
        region=scopes["region"]
        sample=region.get("sample","")
        if sample:
            merged={**inherited, **scopes["global"], **scopes["master"],
                    **scopes["group"], **region}
            sample=merged.get("sample",sample)
            raw_sample=sample.replace("\\","/")
            base=(path.parent / local_default.replace("\\","/")) if local_default else path.parent
            candidate=(base / raw_sample).resolve()
            try: candidate.relative_to(library_root); inside=True
            except ValueError: inside=False
            region_counter+=1
            def note_range(lo,hi):
                a=_num(merged,lo); b=_num(merged,hi)
                return (a if a is not None else b, b if b is not None else a)
            lokey,hikey=note_range("lokey","hikey")
            lovel,hivel=note_range("lovel","hivel")
            output.append({
                "sfz_file":str(sfz_path),"source_sfz":str(path),
                "region":region_counter,"sample_opcode":sample,
                "resolved_sample":str(candidate),
                "status":"FOUND" if candidate.is_file() else ("OUTSIDE_LIBRARY" if not inside else "MISSING"),
                "lokey":lokey if lokey is not None else "",
                "hikey":hikey if hikey is not None else "",
                "lovel":lovel if lovel is not None else "",
                "hivel":hivel if hivel is not None else "",
                "key_range_source":"SFZ" if lokey is not None or hikey is not None else "UNSPECIFIED",
                "velocity_range_source":"SFZ" if lovel is not None or hivel is not None else "UNSPECIFIED",
                "group_label":scopes["group"].get("group_label",""),
                "seq_position":merged.get("seq_position",""),
                "trigger":merged.get("trigger",""),
                "loop_mode":merged.get("loop_mode",""),
                "pitch_keycenter":merged.get("pitch_keycenter",""),
            })
    parse_file(sfz_path, {}, "", ())
    return output
