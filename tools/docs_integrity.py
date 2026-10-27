"""Python documentation integrity checks; no Node.js required for these checks."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
MOJIBAKE=re.compile(r"\ufffd|\u00c2[\u0080-\u00bf]|\u00c3[\u0080-\u00bf]|\u00e2(?:[\u0080-\u00bf]|[\u2000-\u20ff])|Task details \?|Tasks \d+\?\d+|Task \d+ \? 20\d\d|Loading(?: task data| task count| the next planned task)?\?")


def post100_records(text):
    records=json.loads(text)['post100Tasks']
    if not isinstance(records,list): raise ValueError("Post-100 source must remain a literal record array")
    return records


class Identifiers(HTMLParser):
    def __init__(self): super().__init__(); self.values=[]; self.task_articles=[]
    def handle_starttag(self,tag,attrs):
        identifier=dict(attrs).get("id")
        if identifier: self.values.append(identifier)
        if tag == "article" and identifier:
            task=re.match(r"task-(\d+)(?:-|$)",identifier)
            if task: self.task_articles.append(int(task.group(1)))


def documentation_files(root=ROOT):
    result=[p for p in (root/"docs").rglob("*") if p.is_file() and p.suffix in {".md",".json",".mjs",".js",".html",".css"} and "node_modules" not in p.parts]
    result += [root/name for name in ["README.md","ARCHITECTURE.md","corporation_updates.json","desktop/README.md"]]
    return [p for p in result if p.exists()]


def check(root=ROOT):
    failures=[]
    for path in documentation_files(root):
        try: text=path.read_bytes().decode("utf-8",errors="strict")
        except UnicodeError: failures.append(f"{path.relative_to(root)}: invalid UTF-8"); continue
        for number,line in enumerate(text.splitlines(),1):
            if MOJIBAKE.search(line): failures.append(f"{path.relative_to(root)}:{number}: mojibake or damaged separator")
        if path.suffix==".html":
            parser=Identifiers(); parser.feed(text)
            for identifier,count in Counter(parser.values).items():
                if count>1: failures.append(f"{path.relative_to(root)}: duplicate HTML id {identifier}")
            for number,count in Counter(parser.task_articles).items():
                if count>1: failures.append(f"{path.relative_to(root)}: duplicate current task article {number}")
    records=post100_records((root/"docs/tasks-data.json").read_text(encoding="utf-8"))
    for number,count in Counter(item["number"] for item in records).items():
        if count>1: failures.append(f"Duplicate authoritative task {number}")
    updates=json.loads((root/"corporation_updates.json").read_text(encoding="utf-8"))["items"]
    numbers=[]
    for item in updates:
        match=re.match(r"^Task\s+(\d+)\b",item.get("title",""))
        if match: numbers.append(int(match.group(1)))
    for number,count in Counter(numbers).items():
        if count>1: failures.append(f"Duplicate current changelog task {number}; move milestones into history")
    return failures


if __name__=="__main__":
    errors=check()
    if errors: raise SystemExit("\n".join(errors))
    print("Documentation UTF-8, mojibake, canonical task and changelog uniqueness checks passed.")
