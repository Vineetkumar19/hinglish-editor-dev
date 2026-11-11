"""Separate explicit screenplay notes from the supplied spoken dialogue."""
import re


def spoken_lines(text):
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    stage=lambda line:bool(re.fullmatch(r'\[[^\n]*\]',line))
    quoted=lambda line:len(line)>1 and ((line.startswith('“') and line.endswith('”')) or
                                      (line.startswith('"') and line.endswith('"')))
    # A document with camera directions and explicitly quoted dialogue has a
    # preamble (episode heading, title, reference instructions), not narration.
    screenplay=any(stage(line) for line in lines) and any(quoted(line) for line in lines)
    started=not screenplay
    result=[]
    for line in lines:
        if stage(line):
            started=True
            continue
        if not started and not quoted(line):continue
        started=True
        result.append(line[1:-1].strip() if quoted(line) else line)
    return result
