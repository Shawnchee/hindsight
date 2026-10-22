import json
L=open("/Users/shawnchee/Desktop/projects/hindsight/m0/b2/spike/spike.part4.jsonl").read().splitlines()
assert len(L)==8
for l in L:
    d=json.loads(l); assert len(d["top5"])==5 and isinstance(d["exploitable_bug_found"],bool)
print("ok",len(L))
