import pandas as pd
from scripts.common import DATA,stamp,overwrite_rows
def run():
 p=DATA/'device_inventory.csv'
 if not p.exists(): return []
 df=pd.read_csv(p).fillna(''); out=[]
 for mac,g in df[df.mac.astype(str)!=''].groupby('mac'):
  ips=sorted(set(g.ip.astype(str)))
  if len(ips)>1: out.append({'timestamp':stamp(),'severity':'review','type':'MULTIPLE_IPS_SAME_MAC','subject':mac,'detail':'Aynı MAC birden fazla IP ile gözlemlendi: '+', '.join(ips)})
 for ip,g in df.groupby('ip'):
  if len(set(x for x in g.mac.astype(str) if x))>1: out.append({'timestamp':stamp(),'severity':'review','type':'MULTIPLE_MACS_SAME_IP','subject':ip,'detail':'Aynı IP için birden fazla MAC gözlemlendi.'})
 overwrite_rows(DATA/'behavior_findings.csv',out,['timestamp','severity','type','subject','detail']); return out
if __name__=='__main__': print(len(run()))
