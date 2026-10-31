import pickle, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon, Rectangle, Circle, Wedge
plt.rcParams.update({'font.size':7,'font.family':'serif','axes.linewidth':.6})
d=pickle.load(open('out.pkl','rb')); roc=d['roc']; res=d['res']; cm=np.array(d['cm'])
# ---------- Fig1 architecture
fig,ax=plt.subplots(figsize=(7.1,2.75)); ax.set_xlim(0,100); ax.set_ylim(0,40); ax.axis('off')
def box(x,y,w,h,t,fc,ec='#333',fs=6.3,bold=False):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.25,rounding_size=1',fc=fc,ec=ec,lw=.7))
    ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=fs,fontweight='bold' if bold else 'normal')
def arr(x1,y1,x2,y2,c='#333',ls='-'):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle='-|>',mutation_scale=6,lw=.7,color=c,ls=ls))
# layer labels
for x,t in [(1,'Sensing'),(21,'Perception agents'),(44,'Reasoning agents'),(68,'Decision / action')]:
    ax.text(x+8,38.3,t,fontsize=7,fontweight='bold',color='#1f3b66',ha='center')
sens=['Visible camera','Thermal camera','Radar','Fence / fiber','RF / acoustic']
for i,s in enumerate(sens): box(1,31-i*6.3,15,4.6,s,'#e8eef7')
per=['Vision agent\n(detect, track)','Vehicle agent','Drone agent','Perimeter agent\n(fence, gate, zone)']
for i,s in enumerate(per): box(21,30-i*7.6,16,5.4,s,'#e6f4e6')
for i in range(5):
    for j in range(4):
        pass
for i in range(5): arr(16.3,33.3-i*6.3,20.7,[32.7,32.7,24.6,17,9.5][i] if False else 32.7-(min(i,3))*7.6*0.0 - 0 if False else 33-(min(i,3)*7.6) ,'#888')
box(44,24,17,8,'Fusion agent\n(multi-sensor +\ncontext)','#fff2d6')
box(44,12.5,17,8,'Behaviour agent\n(loitering, group,\ntrajectory)','#fff2d6')
box(44,1.5,17,8,'Risk agent\n(severity, proximity\n-> L/M/H/C)','#fff2d6')
for y in (33.5,25,17,9): arr(37.3,y,43.7,28 if y>20 else 16,'#888')
arr(52.5,23.8,52.5,20.9); arr(52.5,12.3,52.5,9.9)
box(68,22,16,12,'Orchestrator\n(controller)\nplan, policy check,\nroute, log','#fde0dc',bold=False)
arr(61.3,28,67.7,28); arr(61.3,16.5,67.5,24); arr(61.3,5.5,67.5,22.5)
box(68,8,16,8,'Alert agent\nconsole - digest\nSMS / radio','#f3e3f7')
arr(76,21.7,76,16.3)
box(88,22,11,12,'Human\noperator\n(approve /\noverride)','#ffffff',bold=True)
arr(84.3,28,87.7,28); arr(76,7.7,76,5.2,'#333'); 
box(68,0.8,16,4,'Audit log','#eeeeee')
arr(84.3,12,93.5,21.7,'#333'); ax.text(91.5,15,'confirm /\nrelabel',fontsize=5.5,color='#333')
ax.add_patch(FancyArrowPatch((93.5,21.7),(84.4,3),connectionstyle='arc3,rad=-0.0',arrowstyle='-|>',mutation_scale=0,lw=0))
ax.annotate('',xy=(61,3),xytext=(68,3),arrowprops=dict(arrowstyle='-|>',lw=.7,ls='--',color='#c0392b'))
ax.text(64.5,4.2,'retrain',fontsize=5.5,color='#c0392b',ha='center')
plt.savefig('figs/fig1_arch.pdf',bbox_inches='tight'); plt.close()
# ---------- Fig2 scene
fig,ax=plt.subplots(figsize=(3.45,3.0)); ax.set_xlim(0,100); ax.set_ylim(0,90); ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
ax.add_patch(Rectangle((0,0),100,90,fc='#efe9d8',ec='k',lw=.6))
ax.add_patch(Rectangle((0,48),100,14,fc='#f6d9d5',alpha=.7,ec='none')); ax.text(2,58.5,'Restricted zone',fontsize=5.5,color='#8a2b20')
ax.plot([0,100],[62,62],'k-',lw=1.6); ax.text(98,63.5,'Border fence',fontsize=5.5,ha='right')
ax.add_patch(Rectangle((45,60.5),10,3,fc='#888',ec='k',lw=.5)); ax.text(50,66,'Gate',fontsize=5.5,ha='center')
ax.add_patch(Rectangle((0,62),100,28,fc='#d9e6f2',alpha=.5,ec='none')); ax.text(3,85,'Foreign side',fontsize=5.5,color='#335')
for x,nm in [(15,'T1'),(50,'T2'),(85,'T3')]:
    ax.plot(x,40,'s',ms=5,color='#1f3b66'); ax.text(x,34.5,nm+'\ncam+thermal',fontsize=4.8,ha='center')
    ax.add_patch(Wedge((x,40),45,50,130,fc='#1f3b66',alpha=.07,ec='#1f3b66',lw=.4))
ax.plot(50,20,'^',ms=6,color='#2a7f2a'); ax.text(50,13,'Radar',fontsize=5,ha='center')
col={'C':'#b00020','H':'#e8742c','M':'#e6b800','L':'#4a9d4a'}
def track(pts,c,lab,ls='-'):
    p=np.array(pts); ax.plot(p[:,0],p[:,1],ls,color=col[c],lw=1.2); ax.plot(*p[-1],'o',color=col[c],ms=4); ax.text(p[-1][0]+1.5,p[-1][1]+1.5,lab,fontsize=5.2,color=col[c],fontweight='bold')
track([(22,86),(24,76),(26,67),(28,58),(30,50)],'C','')
ax.text(4,74,'Group x5 (C)',fontsize=5.2,color=col['C'],fontweight='bold')
track([(70,40),(68,45),(66,50),(60,54)],'H','Vehicle (H)')
track([(88,50),(92,55),(94,57)],'M','Loiter (M)')
track([(8,45),(10,48),(11,50)],'L','',':')
ax.text(2,41.5,'Animal (L)',fontsize=5.2,color=col['L'],fontweight='bold')
ax.plot(76,78,'x',color=col['H'],ms=6,mew=1.5); ax.text(78,79.5,'Drone (H)',fontsize=5.2,color=col['H'],fontweight='bold')
ax.plot(40,53,'D',color=col['C'],ms=4); ax.text(43,52,'Abandoned obj. (C)',fontsize=5.2,color=col['C'],fontweight='bold')
ax.plot(50,20,'^',ms=0)
import matplotlib.lines as ml
h=[ml.Line2D([],[],color=col[k],lw=2) for k in 'CHML']
ax.legend(h,['Critical','High','Medium','Low'],loc='lower right',fontsize=5,frameon=True,ncol=2,handlelength=1.2)
plt.savefig('figs/fig2_scene.pdf',bbox_inches='tight'); plt.close()
# ---------- Fig3 ROC + class recall
fig,axs=plt.subplots(1,2,figsize=(7.1,2.5))
ax=axs[0]; names={'cam':'Camera-only motion alarm','or':'Multi-sensor OR rule','prop':'Proposed agentic fusion'}; cs={'cam':'#999','or':'#e8742c','prop':'#1f3b66'}
for k in ['cam','or','prop']:
    f,t,a=roc[k]; ax.plot(f,t,color=cs[k],lw=1.3,label=f'{names[k]} (AUC={a:.3f})')
ax.plot([0,1],[0,1],'k:',lw=.5); ax.set_xlabel('False positive rate'); ax.set_ylabel('True positive rate'); ax.legend(fontsize=5.8,loc='lower right'); ax.grid(alpha=.25); ax.set_title('(a) ROC, threat vs. non-threat',fontsize=7)
ax=axs[1]; cl=['Person','Group','Loiter','Vehicle','Drone','Abandoned','Fence\nbreach']; x=np.arange(7); w=.27
for i,k in enumerate(['cam','or','prop']): ax.bar(x+(i-1)*w,res[k]['class_recall'],w,color=cs[k],label=names[k])
ax.set_xticks(x); ax.set_xticklabels(cl,fontsize=6); ax.set_ylabel('Recall'); ax.set_ylim(0,1.12); ax.grid(axis='y',alpha=.25); ax.set_title('(b) Per-threat-class recall at operating point',fontsize=7)
plt.tight_layout(); plt.savefig('figs/fig3_roc.pdf',bbox_inches='tight'); plt.close()
# ---------- Fig4 operations
fig,axs=plt.subplots(1,3,figsize=(7.1,2.3),gridspec_kw={'width_ratios':[1,1,.9]})
ks=['cam','or','prop']; lab=['Camera\nonly','Multi-\nsensor OR','Proposed']
ax=axs[0]; ax.bar(range(3),[res[k]['fa_per_day'] for k in ks],color=[cs[k] for k in ks]); ax.set_xticks(range(3)); ax.set_xticklabels(lab,fontsize=6)
for i,k in enumerate(ks): ax.text(i,res[k]['fa_per_day']+.6,f"{res[k]['fa_per_day']:.1f}",ha='center',fontsize=6)
ax.set_ylabel('False alarms per day'); ax.set_title('(a) False alarms',fontsize=7); ax.grid(axis='y',alpha=.25)
ax=axs[1]; ax.bar(range(3),[res[k]['interrupts_per_day'] for k in ks],color=[cs[k] for k in ks]); ax.set_xticks(range(3)); ax.set_xticklabels(lab,fontsize=6)
for i,k in enumerate(ks): ax.text(i,res[k]['interrupts_per_day']+.8,f"{res[k]['interrupts_per_day']:.1f}",ha='center',fontsize=6)
ax.set_ylabel('Operator interruptions per day'); ax.set_title('(b) Operator workload',fontsize=7); ax.grid(axis='y',alpha=.25)
ax=axs[2]; im=ax.imshow(cm,cmap='Blues'); L=['L','M','H','C']
ax.set_xticks(range(4)); ax.set_xticklabels(L); ax.set_yticks(range(4)); ax.set_yticklabels(L); ax.set_xlabel('Predicted risk'); ax.set_ylabel('True risk')
for i in range(4):
    for j in range(4): ax.text(j,i,cm[i,j],ha='center',va='center',fontsize=6,color='w' if cm[i,j]>cm.max()/2 else 'k')
ax.set_title('(c) Risk-level confusion',fontsize=7)
plt.tight_layout(); plt.savefig('figs/fig4_ops.pdf',bbox_inches='tight'); plt.close()
print('ok')
