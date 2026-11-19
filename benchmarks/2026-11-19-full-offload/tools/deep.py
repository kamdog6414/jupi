# Public edition. Builds a ~2048-context prompt from deep_rows.json by binary search on /tokenize.
# usage: python3 deep.py <port> <target_tokens> <out.json>   (run from the data/ folder or pass DEEP_ROWS)
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from client import post
port=int(sys.argv[1]); target=int(sys.argv[2]); out=sys.argv[3]
d=json.load(open(os.environ.get("DEEP_ROWS","deep_rows.json"))); rows=d["rows"]
def build(n):
    return ("Below is a daily weather log for a river town.\n" + "\n".join(rows[:n]) +
            "\n\nQuestion: According to the log, what was the temperature on Day 37?\nAnswer: On Day 37 the temperature was")
def ntok(s): return len(post(port,"/tokenize",{"content":s})["tokens"])
lo,hi=40,len(rows)
while lo<hi:
    m=(lo+hi+1)//2
    if ntok(build(m))<=target: lo=m
    else: hi=m-1
p=build(lo); json.dump([{"id":"deep-2048","kind":"deep","prompt":p,"n_predict":120,"rows":lo,"answer":rows[36]}],open(out,"w"))
print("rows",lo,"tokens",ntok(p),"truth:",rows[36])
