# Public edition of the lab client (see ../SANITIZATION.txt).
# usage: python3 client.py <port> <prompts.json> <out.jsonl>
# POST /completion, temperature 0, seed 1, cache_prompt false. Aborts if MemAvailable < 350 MB.
import json, os, sys, time, urllib.request
HOST = os.environ.get("JUPI_MODEL_HOST", "localhost")
def post(port, path, body, to=600):
    r = urllib.request.Request(f"http://{HOST}:{port}{path}", data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(r, timeout=to))
def meminfo():
    m={l.split(':')[0]:int(l.split()[1]) for l in open('/proc/meminfo')}
    return m['MemAvailable']//1024
def run(port, prompts, out, minmem=350):
    with open(out,"a") as f:
        for p in prompts:
            ma=meminfo()
            if ma<minmem: f.write(json.dumps({"id":p["id"],"abort":f"MemAvailable {ma}MB"})+"\n"); print("ABORT mem",ma); sys.exit(97)
            t0=time.time()
            d=post(port,"/completion",{"prompt":p["prompt"],"n_predict":p.get("n_predict",64),"temperature":0,"seed":1,"cache_prompt":False})
            rec={"id":p["id"],"utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"wall_s":round(time.time()-t0,2),"content":d["content"],
                 "n_prompt":d["timings"]["prompt_n"],"n_pred":d["timings"]["predicted_n"],"pp_tps":round(d["timings"]["prompt_per_second"],2),"tg_tps":round(d["timings"]["predicted_per_second"],2),"mem_avail_mb":ma}
            f.write(json.dumps(rec)+"\n"); f.flush(); print(rec["id"],rec["n_prompt"],rec["n_pred"],rec["tg_tps"],flush=True)
if __name__=="__main__":
    run(int(sys.argv[1]), json.load(open(sys.argv[2])), sys.argv[3])
