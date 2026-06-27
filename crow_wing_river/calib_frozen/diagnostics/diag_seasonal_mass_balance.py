import warnings, yaml
import numpy as np, pandas as pd
from mnished import run_and_score, Buckets
import mnished.mnished as _M
_M._numba_available=False
warnings.filterwarnings('ignore')
S,E=pd.Timestamp('2001-01-01'),pd.Timestamp('2010-12-31')
B=dict(PDD=3.337, et=0.655, tsoil=1.525, tgw=2.444, fex=0.540, tlake=4.479, hsill=2.290, frout=0.400, fdd=2.259)
MOD={'snowpack':True,'frozen_ground':True,'rain_on_snow':True,'direct_runoff':False,'dtr_fgi_decay':False,'et_water_stress':False,'et_reservoir_draw':True}

land_rec=[]; lake_rec=[]
_os=Buckets._advance_sub_catchment
def ps(self,ts,sc):
    r=_os(self,ts,sc)
    land_rec.append((ts,sc.name,sc.area_fraction,sc._routed_away_fraction,
                     sc.reservoirs[0].H_discharge, sc.reservoirs[1].H_discharge))
    return r
Buckets._advance_sub_catchment=ps
_ol=Buckets._advance_lake
def pl(self,ts,sc,ri=0.0):
    o=_ol(self,ts,sc,ri); lake_rec.append((ts,sc.area_fraction,o)); return o
Buckets._advance_lake=pl

land={'recession_coeff':[10**B['tsoil'],10**B['tgw']],'f_to_discharge':[B['fex'],1.0],'pdm_H0':[None,None]}
lake={'recession_coeff':[10**B['tlake']],'H_threshold':[10**B['hsill']],'f_route_lake':B['frout']}
r=run_and_score('../crow_wing_config_v6_2layer_frozen.yml',sub_catchments=[land,land,lake],
  melt_factor=B['PDD'],fdd_threshold=10**B['fdd'],snow_insulation_k=0.0,direct_runoff_fraction=0.0,baseflow_Q=0.0,
  et_scale=B['et'],et_alpha=None,routing_K=None,routing_N=2,enforce_water_balance='none',initial_states=None,
  spin_up_cycles=1,start='2001-01-01',end='2010-12-31',metric='KGE',modules=MOD)

hd=r.buckets.hydrodata.reset_index(drop=True); dts=pd.to_datetime(hd['Date']); inwin=((dts>=S)&(dts<=E)).values
P=pd.to_numeric(hd['Precipitation [mm/day]'],errors='coerce').values
ET=pd.to_numeric(hd['ET for model [mm/day]'],errors='coerce').values
obs=pd.to_numeric(hd['Specific Discharge [mm/day]'],errors='coerce').values
SWE=pd.to_numeric(hd['Snowpack (modeled) [mm SWE]'],errors='coerce').values
fr=B['frout']
def lm(rec): 
    d={}; [d.__setitem__((x[0],x[1]) if len(x)>3 else x[0], x) for x in rec]; return d
# per-ts source decomposition
L={}; 
for x in land_rec: L[(x[0],x[1])]=x
K={x[0]:x for x in lake_rec}
rows=[]
for ts in range(len(hd)):
    if not inwin[ts]: continue
    d=L.get((ts,'direct_land')); g=L.get((ts,'lake_basin_land')); lk=K.get(ts)
    if d is None or lk is None: continue
    a_d,_,sd,gd = d[2],d[3],d[4],d[5]
    a_g,_,sg,gg = g[2],g[3],g[4],g[5]
    a_l,out = lk[1],lk[2]
    fast = a_d*sd + a_g*sg*(1-fr)        # soil -> gauge (incl. frozen-ground freshet)
    slow = a_d*gd + a_g*gg*(1-fr)        # gw  -> gauge
    lake_c = a_l*out                      # lake outlet (buffered 40% + P-E + Q_gw)
    rows.append((dts.iloc[ts].month, P[ts], ET[ts], obs[ts], fast, slow, lake_c, fast+slow+lake_c))
D=pd.DataFrame(rows,columns=['mon','P','ET','obs','fast','slow','lake','mod'])

print("Seasonal means (mm/day), 2001-2010 — multi-decade best params:")
print(f"{'seas':<5}{'P':>6}{'ET':>6}{'obs':>6}{'mod':>6}{'mod/obs':>8}|{'fast':>6}{'slow':>6}{'lake':>6}")
for nm,M in [('DJF',[12,1,2]),('MAM',[3,4,5]),('JJA',[6,7,8]),('SON',[9,10,11])]:
    s=D[D.mon.isin(M)]
    print(f"{nm:<5}{s.P.mean():>6.2f}{s.ET.mean():>6.2f}{s.obs.mean():>6.3f}{s['mod'].mean():>6.3f}{s['mod'].mean()/s.obs.mean():>8.2f}|{s.fast.mean():>6.3f}{s.slow.mean():>6.3f}{s.lake.mean():>6.3f}")
print("\nMonthly SWE (mm) + ET (mm/d) — melt timing & summer ET:")
cl=D.groupby('mon').mean(numeric_only=True)
# SWE per month
swe_m=pd.DataFrame({'mon':dts.dt.month[inwin],'SWE':SWE[inwin]}).groupby('mon').mean()
for m in range(1,13):
    print(f"  m{m:>2}: SWE={swe_m.loc[m,'SWE']:>5.1f}  P={cl.loc[m,'P']:.2f}  ET={cl.loc[m,'ET']:.2f}  obsQ={cl.loc[m,'obs']:.2f}  modQ={cl.loc[m,'mod']:.2f}")
print(f"\nAnnual: P={D.P.mean():.2f}  ET={D.ET.mean():.2f}  obsQ={D.obs.mean():.3f}  modQ={D['mod'].mean():.3f}  (P-ET={D.P.mean()-D.ET.mean():.2f})")
