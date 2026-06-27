import warnings
import numpy as np, pandas as pd
from mnished import run_and_score, Buckets
warnings.filterwarnings('ignore')
S,E=pd.Timestamp('2001-01-01'),pd.Timestamp('2010-12-31')
B=dict(PDD=3.337, et=0.655, tsoil=1.525, tgw=2.444, fex=0.540, tlake=4.479, hsill=2.290, frout=0.400, fdd=2.259)
MOD={'snowpack':True,'frozen_ground':True,'rain_on_snow':True,'direct_runoff':False,'dtr_fgi_decay':False,'et_water_stress':False,'et_reservoir_draw':True}
# Northern mixed-forest leaf-out / LAI phenology factor on ET (kludge)
PHEN={1:.2,2:.2,3:.2,4:.35,5:.7,6:1.,7:1.,8:1.,9:.9,10:.6,11:.3,12:.3}

_orig=Buckets.compute_ET
def patched(self,*a,**k):
    _orig(self,*a,**k)
    mon=pd.to_datetime(self.hydrodata['Date']).dt.month.values
    et=pd.to_numeric(self.hydrodata['ET for model [mm/day]'],errors='coerce').values
    self.hydrodata['ET for model [mm/day]']=et*np.array([PHEN[m] for m in mon])

def run(phen):
    Buckets.compute_ET = patched if phen else _orig
    land={'recession_coeff':[10**B['tsoil'],10**B['tgw']],'f_to_discharge':[B['fex'],1.0],'pdm_H0':[None,None]}
    lake={'recession_coeff':[10**B['tlake']],'H_threshold':[10**B['hsill']],'f_route_lake':B['frout']}
    r=run_and_score('../crow_wing_config_v6_2layer_frozen.yml',sub_catchments=[land,land,lake],
      melt_factor=B['PDD'],fdd_threshold=10**B['fdd'],snow_insulation_k=0.0,direct_runoff_fraction=0.0,baseflow_Q=0.0,
      et_scale=B['et'],et_alpha=None,routing_K=None,routing_N=2,enforce_water_balance='none',initial_states=None,
      spin_up_cycles=1,start='2001-01-01',end='2010-12-31',metric='KGE',modules=MOD)
    hd=r.buckets.hydrodata.reset_index(drop=True); d=pd.to_datetime(hd['Date']); w=((d>=S)&(d<=E)).values
    obs=pd.to_numeric(hd['Specific Discharge [mm/day]'],errors='coerce').values
    mod=pd.to_numeric(hd['Specific Discharge (modeled) [mm/day]'],errors='coerce').values
    g=pd.DataFrame({'mon':d.dt.month,'obs':obs,'mod':mod})[w].dropna()
    sea={nm:g[g.mon.isin(M)]['mod'].mean()/g[g.mon.isin(M)]['obs'].mean() for nm,M in [('DJF',[12,1,2]),('MAM',[3,4,5]),('JJA',[6,7,8]),('SON',[9,10,11])]}
    return r.score, sea, g['mod'].mean(), g['obs'].mean()

print(f"{'case':<18}{'KGE':>7}{'annualQ':>9}  DJF  MAM  JJA  SON  (mod/obs)")
for tag,ph in [('baseline (Thornt.)',False),('+ leaf-out kludge',True)]:
    k,s,mq,oq=run(ph)
    print(f"{tag:<18}{k:>7.3f}{mq:>9.3f}  {s['DJF']:.2f} {s['MAM']:.2f} {s['JJA']:.2f} {s['SON']:.2f}")
print(f"obs annualQ = {oq:.3f}")
Buckets.compute_ET=_orig

print("\n=== phenology kludge ON, sweep et_scale to restore annual balance ===")
print(f"{'et_scale':>9}{'KGE':>7}{'annualQ':>9}  DJF  MAM  JJA  SON")
print(f"{'obs':>9}{'':>7}{0.472:>9.3f}  1.00 1.00 1.00 1.00")
for es in [0.655, 0.95, 1.15, 1.35]:
    B['et']=es
    k,s,mq,oq=run(True)
    print(f"{es:>9.2f}{k:>7.3f}{mq:>9.3f}  {s['DJF']:.2f} {s['MAM']:.2f} {s['JJA']:.2f} {s['SON']:.2f}")
B['et']=0.655
print("\n(baseline Thornthwaite, et=0.655: KGE 0.727  DJF 1.04 MAM 0.77 JJA 1.01 SON 1.21)")
