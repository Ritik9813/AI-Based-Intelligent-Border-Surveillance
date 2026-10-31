import numpy as np, json
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_curve, auc, confusion_matrix
rng = np.random.default_rng(7)
T = ['person','group','loiter','vehicle','drone','abandoned','breach','animal','vegetation','patrol','weather']
NT = 7  # first 7 are threats
rate = [1.6,.7,1.0,.8,.5,.5,.9, 25,20,8,12]
# sensors: cam, thermal, radar, fence, rf
M = np.array([[.75,.80,.60,.20,0],[.80,.85,.70,.25,0],[.70,.75,.50,.30,0],[.80,.70,.85,.10,0],
 [.35,.40,.55,0,.85],[.55,.60,.10,0,0],[.50,.55,.30,.90,0],
 [.45,.60,.50,.25,0],[.50,.05,.40,.30,0],[.80,.80,.70,.15,0],[.40,.05,.35,.35,0]])
sev = np.array([.5,.8,.3,.8,.6,.9,.7])
DAYS=60
def gen():
    X=[];y=[];day=[];tmin=[];meta=[]
    for d in range(DAYS):
        for c in range(11):
            n = rng.poisson(rate[c])
            for _ in range(n):
                night = rng.random() < (0.6 if c<NT else 0.4)
                hour = rng.uniform(19,30)%24 if night else rng.uniform(6,19)
                bad = True if c==10 else rng.random()<0.2
                m = M[c].copy()
                sg = np.full(5,.15)
                if night: m[0]*=.45; sg[0]=.22
                if bad: m[0]*=.75; m[1]*=.9
                if c==10 and bad: m[2]+=.15
                s = np.clip(m+rng.normal(0,sg),0,1); s[4]=np.clip(m[4]+rng.normal(0,.1),0,1) if m[4]>0 else abs(rng.normal(0,.05))
                # behaviour
                sp = {0:(1.4,.5),1:(1.2,.4),2:(.2,.15),3:(8,3),4:(6,2),5:(.02,.02),6:(.8,.5),7:(2.5,1.5),8:(.3,.3),9:(5,3.5),10:(.3,.3)}[c]
                dw = {0:(40,20),1:(60,25),2:(600,250),3:(20,10),4:(120,60),5:(3000,1000),6:(90,40),7:(60,50),8:(10,10),9:(60,40),10:(10,10)}[c]
                gs = {1:rng.integers(3,9),2:rng.integers(1,4),3:rng.integers(1,3),7:rng.integers(1,5)}.get(c,1)
                hd = rng.normal(.6,.3) if c in (0,1,3) else rng.normal(0,.5 if c in (2,7,9) else .3)
                dist = min(rng.exponential(120),600) if c<NT else rng.uniform(0,800)
                auth = float(rng.random()<(.85 if c==9 else .02 if c<NT else 0))
                f = list(s)+[abs(rng.normal(*sp)),abs(rng.normal(*dw)),gs,np.clip(hd,-1,1),dist,float(night),float(bad),auth]
                X.append(f);y.append(c);day.append(d);tmin.append(d*1440+hour*60+rng.uniform(0,60)%60);meta.append(night)
    return np.array(X),np.array(y),np.array(day),np.array(tmin),np.array(meta)
X,y,day,tmin,night = gen()
tr = day<30; te = ~tr
Xtr,ytr,Xte,yte = X[tr],y[tr],X[te],y[te]
tt = tmin[te]; nte = night[te]
ytrue_thr = (yte<NT).astype(int)
days_te = DAYS-30
clf = HistGradientBoostingClassifier(max_iter=150,learning_rate=.08,random_state=0).fit(Xtr,ytr)
P = clf.predict_proba(Xte)
score_prop = P[:,:NT].sum(1)
score_cam = Xte[:,0]; score_or = Xte[:,:5].max(1)
from sklearn.model_selection import cross_val_predict
from sklearn.metrics import roc_curve as _rc
Pcv = cross_val_predict(HistGradientBoostingClassifier(max_iter=150,learning_rate=.08,random_state=0),Xtr,ytr,cv=5,method='predict_proba')
scv = Pcv[:,:NT].sum(1); f_,t_,th_ = _rc((ytr<NT).astype(int),scv)
thp = float(th_[np.where(t_>=0.92)[0][0]])
th = {'cam':.5,'or':.6,'prop':thp}
print('tuned prop threshold (train CV, recall>=0.92):',thp)
alert = {'cam':score_cam>th['cam'],'or':score_or>th['or'],'prop':score_prop>th['prop']}
sc = {'cam':score_cam,'or':score_or,'prop':score_prop}
res={'n_threat_test':int(ytrue_thr.sum()),'n_benign_test':int((1-ytrue_thr).sum()),'days':days_te}
roc={}
for k in sc:
    fpr,tpr,_=roc_curve(ytrue_thr,sc[k]); roc[k]=(fpr,tpr,auc(fpr,tpr))
    a=alert[k]; tp=(a&(ytrue_thr==1)).sum(); fp=(a&(ytrue_thr==0)).sum()
    res[k]={'auc':float(roc[k][2]),'recall':float(tp/ytrue_thr.sum()),'precision':float(tp/max(a.sum(),1)),
            'fa_per_day':float(fp/days_te),'alarms_per_day':float(a.sum()/days_te),
            'class_recall':[float((a&(yte==c)).sum()/(yte==c).sum()) for c in range(NT)]}
# risk
def mods(F,night_f): 
    return 1+.3*(F[:,7-0+0-0]>=4)  # placeholder replaced below
gsz,dist_,nt_ = Xte[:,7+0+0-0+0] if False else None,None,None
# feature idx: 0-4 sensors,5 speed,6 dwell,7 group,8 heading,9 dist,10 night,11 bad,12 auth
g=Xte[:,7]; ds=Xte[:,9]; ni=Xte[:,10]
mod = 1+.3*(g>=4)+.4*(ds<100)+.2*ni
def level(r): return np.digitize(r,[.45,.7,1.0])
true_r = np.where(yte<NT, sev[np.minimum(yte,NT-1)]*mod, 0)
Pthr = P[:,:NT]; 
est = (Pthr*sev).sum(1)/np.maximum(Pthr.sum(1),1e-9)*mod
tl = level(true_r); pl = level(est)
m = alert['prop']&(ytrue_thr==1)
cm = confusion_matrix(tl[m],pl[m],labels=[0,1,2,3])
res['risk_acc']=float((tl[m]==pl[m]).mean()); res['risk_within1']=float((abs(tl[m]-pl[m])<=1).mean())
res['risk_cm']=cm.tolist()
# queue sim
def queue(arr_t,prio,svc_mean,flag,seed):
    r=np.random.default_rng(seed); order=np.argsort(arr_t); t=0.;done={};pend=[];i=0;n=len(arr_t)
    S=r.exponential(svc_mean,n)
    import heapq
    h=[]; 
    while i<n or h:
        if not h and i<n and arr_t[order[i]]>t: t=arr_t[order[i]]
        while i<n and arr_t[order[i]]<=t:
            j=order[i]; heapq.heappush(h,(-prio[j] if flag else arr_t[j], arr_t[j], j)); i+=1
        _,_,j=heapq.heappop(h); done[j]=t-arr_t[j]; t+=S[j]
    return done
high = (tl>=2)&(ytrue_thr==1)
def qstats(idx,prio,flag,seed=3):
    d=queue(tt[idx],prio[idx],5.0,flag,seed)
    ids=np.where(idx)[0]; w=np.array([d[k] for k in range(len(ids))]); h=high[idx]
    return float(w[h].mean()) if h.any() else float('nan'), float((w[h]<=5).mean()) if h.any() else float('nan'), float(h.sum())
for k in ['cam','or']:
    idx=alert[k]; r=qstats(idx,np.zeros(len(yte)),False)
    res[k]['ack_mean']=r[0]; res[k]['ack5']=r[1]; res[k]['high_alerted']=r[2]; res[k]['high_total']=float(high.sum()); res[k]['interrupts_per_day']=res[k]['alarms_per_day']
rt = alert['prop']&(pl>=1)
r=qstats(rt,pl.astype(float)+score_prop*0.1,True)
res['prop']['ack_mean']=r[0]; res['prop']['ack5']=r[1]; res['prop']['high_alerted']=r[2]; res['prop']['high_total']=float(high.sum())
res['prop']['interrupts_per_day']=float(rt.sum()/days_te)
res['prop']['digest_per_day']=float((alert['prop']&(pl==0)).sum()/days_te)
# high-risk recall
for k in ['cam','or','prop']:
    a=alert[k]&(pl>=1) if k=='prop' else alert[k]
    res[k]['high_recall']=float((a&high).sum()/high.sum())
json.dump(res,open('res.json','w'),indent=1)
np.save('roc.npy',np.array([roc[k][:2] for k in roc],dtype=object),allow_pickle=True)
import pickle; pickle.dump({'roc':roc,'res':res,'cm':cm},open('out.pkl','wb'))
print(json.dumps({k:v for k,v in res.items() if k!='risk_cm'},indent=1)); print(cm)
