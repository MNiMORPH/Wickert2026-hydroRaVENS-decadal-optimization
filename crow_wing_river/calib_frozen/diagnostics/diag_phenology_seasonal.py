import warnings
import numpy as np, pandas as pd
from mnished import run_and_score, Buckets
warnings.filterwarnings('ignore')
S,E=pd.Timestamp('2001-01-01'),pd.Timestamp('2010-12-31')
PHEN={1:.2,2:.2,3:.2,4:.35,5:.7,6:1.,7:1.,8:1.,9:.9,10:.6,11:.3,12:.3}
_orig=Buckets.compute_ET
def patched(self,*a,**k):
    _orig(self,*a,**k)
    mon=pd.to_datetime(self.hydrodata['Date']).dt.month.values
    et=pd.to_numeric(self.hydrodata['ET for model [mm/day]'],errors='coerce').values
    self.hydrodata['ET for model [mm/day]']=et*np.array([PHEN[m] for m in mon])
Buckets.compute_ET=patched
B=dict(PDD=5.683, et=0.783, tsoil=1.711, tgw=3.174, fex=0.691, tlake=4.272, hsill=3.312, frout=0.469, fdd=1.498)
MOD={'snowpack':True,'frozen_ground':True,'rain_on_snow':True,'direct_runoff':False,'dtr_fgi_decay':False,'et_water_stress':False,'et_reservoir_draw':True}
land={'recession_coeff':[10**B['tsoil'],10**B['tgw']],'f_to_discharge':[B['fex'],1.0],'pdm_H0':[None,None]}
lake={'recession_coeff':[10**B['tlake']],'H_threshold':[10**B['hsill']],'f_route_lake':B['frout']}
r=run_and_score('../crow_wing_config_v6_2layer_frozen.yml',sub_catchments=[land,land,lake],
  melt_factor=B['PDD'],fdd_threshold=10**B['fdd'],snow_insulation_k=0.0,direct_runoff_fraction=0.0,baseflow_Q=0.0,
  et_scale=B['et'],et_alpha=None,routing_K=None,routing_N=2,enforce_water_balance='none',initial_states=None,
  spin_up_cycles=1,start='2001-01-01',end='2010-12-31',metric='KGE',modules=MOD)
hd=r.buckets.hydrodata.reset_index(drop=True); d=pd.to_datetime(hd['Date']); w=((d>=S)&(d<=E)).values
obs=pd.to_numeric(hd['Specific Discharge [mm/day]'],errors='coerce').values
mod=pd.to_numeric(hd['Specific Discharge (modeled) [mm/day]'],errors='coerce').values
m=w&~(np.isnan(obs)|np.isnan(mod)); mo,mm=obs[m],mod[m]
g=pd.DataFrame({'mon':d.dt.month,'obs':obs,'mod':mod})[w].dropna()
print(f"pure KGE={r.score:.3f}  r={np.corrcoef(mm,mo)[0,1]:.3f}  top20={mm[np.argsort(mo)[-20:]].mean()/mo[np.argsort(mo)[-20:]].mean():.3f}")
print(f"{'seas':<5}{'obs':>7}{'mod':>7}{'mod/obs':>8}")
for nm,M in [('DJF',[12,1,2]),('MAM',[3,4,5]),('JJA',[6,7,8]),('SON',[9,10,11])]:
    s=g[g.mon.isin(M)]; print(f"{nm:<5}{s['obs'].mean():>7.3f}{s['mod'].mean():>7.3f}{s['mod'].mean()/s['obs'].mean():>8.2f}")
print("\nbaseline(no kludge):  DJF 1.04  MAM 0.77  JJA 1.01  SON 1.21")
Buckets.compute_ET=_orig
