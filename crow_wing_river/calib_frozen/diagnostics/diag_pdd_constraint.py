import warnings
import numpy as np
from mnished import ScoringModel
warnings.filterwarnings('ignore')
B=dict(et=0.655, tsoil=1.525, tgw=2.444, fex=0.540, tlake=4.479, hsill=2.290, frout=0.400, fdd=2.259)
MOD={'snowpack':True,'frozen_ground':True,'rain_on_snow':True,'direct_runoff':False,'dtr_fgi_decay':False,'et_water_stress':False,'et_reservoir_draw':True}
land={'recession_coeff':[10**B['tsoil'],10**B['tgw']],'f_to_discharge':[B['fex'],1.0],'pdm_H0':[None,None]}
lake={'recession_coeff':[10**B['tlake']],'H_threshold':[10**B['hsill']],'f_route_lake':B['frout']}
sm=ScoringModel('../crow_wing_config_v6_2layer_frozen.yml', enforce_water_balance='none')
decs=[('1931','1940'),('1941','1950'),('1951','1960'),('1961','1970'),('1971','1980'),('1991','2000'),('2001','2010'),('2011','2020')]
def score(pdd, s, e):
    r=sm.score(sub_catchments=[land,land,lake], melt_factor=pdd, fdd_threshold=10**B['fdd'], snow_insulation_k=0.0,
        direct_runoff_fraction=0.0, baseflow_Q=0.0, et_scale=B['et'], et_alpha=None, routing_K=None, routing_N=2,
        initial_states=None, spin_up_cycles=1, start=f'{s}-01-01', end=f'{e}-12-31', metric='KGE_logKGE', modules=MOD)
    return r.score
print(f"{'PDD':>5} {'single-decade(2001-10)':>22} {'multi-decade mean(8)':>22}")
import time; t=time.time()
for pdd in [0.5,1.0,1.5,2.0,2.5,3.0,3.34,4.0,5.0,6.0,8.0,12.0]:
    single=score(pdd,'2001','2010')
    multi=np.mean([score(pdd,s,e) for s,e in decs])
    mark=' <- calibrated' if abs(pdd-3.34)<0.01 else ''
    print(f"{pdd:>5.2f} {single:>22.4f} {multi:>22.4f}{mark}")
print(f"\n(profiled in {time.time()-t:.1f}s thanks to ScoringModel)")
