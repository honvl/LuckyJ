"""Compare the earlier policy model's probabilities with softmax(Q / temperature) from Mortal-S42.

    .venv/bin/python scripts/mortal_calibrate.py OUT.jsonl      (rows from scripts/mortal_two_models.py)

Per temperature: mean ln p of the played move, share of played moves under 10% and 25%, mean top probability and
entropy, KL and total variation from the policy model, and agreement of the two on the under-25% flag.
"""
import json, sys, numpy as np, collections
rows=[json.loads(l) for l in open(sys.argv[1])]
names=collections.Counter(r["name"] for r in rows); hero=names.most_common(1)[0][0]
print("decisions", len(rows), "hero", hero, names[hero])
def stats(sub, label):
    P=[np.array(r["p"]) for r in sub]; Q=[np.array(r["q"]) for r in sub]
    ai=[r["k"].index(r["a"]) for r in sub]
    ptop=np.array([p.argmax() for p in P]); qtop=np.array([q.argmax() for q in Q]); ai=np.array(ai)
    print(f"\n== {label}: n={len(sub)}  models agree on top choice {np.mean(ptop==qtop):.3f}   player=policy top {np.mean(ai==ptop):.3f}   player=S42 top {np.mean(ai==qtop):.3f}")
    pt=np.array([p[i] for p,i in zip(P,ai)])
    print(f"policy: mean ln p(taken) {np.mean(np.log(np.maximum(pt,1e-4))):.4f}  taken<10% {np.mean(pt<.10):.4f}  taken<25% {np.mean(pt<.25):.4f}  mean top prob {np.mean([p.max() for p in P]):.4f}  mean entropy {np.mean([-(p[p>0]*np.log(p[p>0])).sum() for p in P]):.4f}")
    print(" tau   lnp(taken)  <10%    <25%    topprob entropy  KL(pol||s42) TV    corr(ln p)  agree<25%")
    lp=np.log(np.maximum(pt,1e-4))
    for tau in (0.05,0.1,0.2,0.3,0.4,0.5,0.6,0.8,1.0,1.3,1.6,2.0):
        Sx=[]
        for q in Q:
            z=(q-q.max())/tau; e=np.exp(z); Sx.append(e/e.sum())
        st=np.array([s[i] for s,i in zip(Sx,ai)])
        kl=np.mean([ (p[p>1e-6]*(np.log(p[p>1e-6])-np.log(np.maximum(s[p>1e-6],1e-9)))).sum() for p,s in zip(P,Sx)])
        tv=np.mean([0.5*np.abs(p-s).sum() for p,s in zip(P,Sx)])
        ls=np.log(np.maximum(st,1e-4))
        print(f" {tau:4.2f}  {ls.mean():8.4f}   {np.mean(st<.10):.4f}  {np.mean(st<.25):.4f}  {np.mean([s.max() for s in Sx]):.4f}  {np.mean([-(s[s>0]*np.log(s[s>0])).sum() for s in Sx]):.4f}   {kl:.4f}      {tv:.4f}  {np.corrcoef(lp,ls)[0,1]:.3f}      {np.mean((pt<.25)==(st<.25)):.4f}")
stats(rows,"all seats, all decisions")
stats([r for r in rows if r["d"]],"all seats, discards")
stats([r for r in rows if r["name"]==hero],"hero, all decisions")
